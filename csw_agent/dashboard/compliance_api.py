"""Dashboard glue for the PCI-DSS compliance assessment."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator
from typing import Any

from csw_agent.ai.claude import load_prompt
from csw_agent.config import Settings
from csw_agent.dashboard.state import DashboardState
from csw_agent.queries import QueryContext
from csw_agent.queries._helpers import fetch_scopes
from csw_agent.queries.pci import assess_scope
from csw_agent.telemetry import Event, get_telemetry

logger = logging.getLogger(__name__)

# Scope names containing one of these tokens are surfaced as CDE suggestions.
SUGGEST_TOKENS = ("pci", "cde")


def list_scopes(state: DashboardState) -> list[dict[str, Any]]:
    """Return scope names for the CDE selector, suggested ones first (cached)."""

    def compute() -> list[dict[str, Any]]:
        assert state.client is not None
        scopes, error = fetch_scopes(state.client)
        if error:
            raise RuntimeError(f"Could not list scopes: {error}")
        names = sorted({s.get("name", "") for s in scopes if s.get("name")})
        entries = [
            {"name": name, "suggested": any(token in name.lower() for token in SUGGEST_TOKENS)}
            for name in names
        ]
        entries.sort(key=lambda e: (not e["suggested"], e["name"]))
        return entries

    return state.scopes_cache.get_or_compute(compute)


def run_assessment(ctx: QueryContext, scope_name: str) -> dict[str, Any]:
    """Run the deterministic assessment and return the JSON payload."""
    return assess_scope(ctx, scope_name).to_dict()


def build_summary_prompt(assessment: dict[str, Any]) -> str:
    """Render the executive-summary system prompt with the assessment JSON."""
    payload = json.dumps(assessment, ensure_ascii=False, sort_keys=True)
    return load_prompt("pci_summary.md").replace("{assessment}", payload)


async def stream_summary(settings: Settings, assessment: dict[str, Any]) -> AsyncIterator[bytes]:
    """Stream a Claude-generated executive summary as Server-Sent Events.

    The deterministic assessment is the source of truth; this endpoint only
    narrates it, so no code is generated or executed (no sandbox involved).
    """
    try:
        import anthropic
    except ImportError:
        yield _sse({"type": "error", "message": "Claude (anthropic) package not installed."})
        yield _sse({"type": "done"})
        return

    system = build_summary_prompt(assessment)
    client = anthropic.Anthropic(
        api_key=settings.claudegate_api_key,
        base_url=settings.claudegate_url,
    )
    chunks: list[str] = []
    started = time.perf_counter()
    usage_in = 0
    usage_out = 0
    stop_reason: str | None = None

    def stream_blocking() -> None:
        nonlocal stop_reason, usage_in, usage_out
        with client.messages.stream(
            model=settings.claude_model,
            max_tokens=settings.max_tokens_summary,
            system=system,
            messages=[
                {
                    "role": "user",
                    "content": "Generate the executive summary and prioritized recommendations.",
                }
            ],
        ) as stream:
            for text in stream.text_stream:
                chunks.append(text)
            final = stream.get_final_message()
            stop_reason = final.stop_reason
            usage = getattr(final, "usage", None)
            if usage:
                usage_in = getattr(usage, "input_tokens", 0) or 0
                usage_out = getattr(usage, "output_tokens", 0) or 0

    yield _sse({"type": "thinking"})
    try:
        loop = asyncio.get_event_loop()
        pending = loop.run_in_executor(None, stream_blocking)
        last_seen = 0
        while not pending.done():
            await asyncio.sleep(0.1)
            if len(chunks) > last_seen:
                yield _sse({"type": "text", "chunk": "".join(chunks[last_seen:])})
                last_seen = len(chunks)
        await pending
        if last_seen < len(chunks):
            yield _sse({"type": "text", "chunk": "".join(chunks[last_seen:])})
        if stop_reason == "max_tokens":
            yield _sse({"type": "warning", "message": "Summary was truncated (token limit hit)."})
    except Exception as exc:
        logger.exception("Compliance summary failed")
        yield _sse({"type": "error", "message": str(exc)})
    finally:
        get_telemetry().record_event(
            Event(
                kind="claude",
                timestamp=time.time(),
                duration_ms=(time.perf_counter() - started) * 1000,
                success=stop_reason in (None, "end_turn", "stop_sequence"),
                label=settings.claude_model,
                detail=f"pci summary: {assessment.get('scope_name', '')}"[:140],
                tokens_in=usage_in,
                tokens_out=usage_out,
            )
        )
    yield _sse({"type": "done"})


def _sse(payload: dict[str, Any]) -> bytes:
    """Format a payload as a Server-Sent Events ``data:`` frame."""
    return f"data: {json.dumps(payload)}\n\n".encode()
