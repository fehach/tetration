"""Streaming Claude chat endpoint backed by the existing sandbox/runner."""

from __future__ import annotations

import asyncio
import contextlib
import io
import json
import logging
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from csw_agent.ai.claude import build_exec_globals, extract_code_block, load_prompt
from csw_agent.ai.sandbox import validate
from csw_agent.config import Settings
from csw_agent.dashboard.prompt_history import get_history
from csw_agent.dashboard.state import DashboardState
from csw_agent.tabulate_fallback import tabulate
from csw_agent.telemetry import Event, get_telemetry

logger = logging.getLogger(__name__)


@dataclass
class ChatSession:
    """Per-process chat history. (Single-user assumption for v1.)"""

    history: list[dict[str, str]] = field(default_factory=list)

    def reset(self) -> None:
        self.history.clear()


_GLOBAL_SESSION = ChatSession()


def session() -> ChatSession:
    return _GLOBAL_SESSION


async def stream_chat(state: DashboardState, message: str) -> AsyncIterator[bytes]:
    """Stream Server-Sent Events for a single chat turn."""
    settings = state.settings
    chat = session()

    if state.client is None:
        yield _sse({"type": "error", "message": "CSW is not connected; chat requires a live client."})
        yield _sse({"type": "done"})
        return

    try:
        import anthropic
    except ImportError:
        yield _sse({"type": "error", "message": "Claude (anthropic) package not installed."})
        yield _sse({"type": "done"})
        return

    chat.history.append({"role": "user", "content": message})
    get_history().add(message)
    try:
        async for chunk in _run_turn(settings, state, chat, anthropic, message):
            yield chunk
    except Exception as exc:
        logger.exception("Chat turn failed")
        yield _sse({"type": "error", "message": str(exc)})
        if chat.history and chat.history[-1]["role"] == "user":
            chat.history.pop()
    yield _sse({"type": "done"})


async def _run_turn(
    settings: Settings,
    state: DashboardState,
    chat: ChatSession,
    anthropic_module: Any,
    user_message: str,
) -> AsyncIterator[bytes]:
    system = load_prompt("system.md") + "\n\n" + load_prompt("api_reference.md")
    client = anthropic_module.Anthropic(
        api_key=settings.claudegate_api_key,
        base_url=settings.claudegate_url,
    )
    answer_chunks: list[str] = []
    stop_reason: str | None = None
    usage_in = 0
    usage_out = 0
    started = time.perf_counter()
    success = False

    def stream_blocking() -> tuple[str, str | None, int, int]:
        nonlocal stop_reason, usage_in, usage_out
        with client.messages.stream(
            model=settings.claude_model,
            max_tokens=settings.max_tokens_code,
            system=system,
            messages=chat.history,
        ) as stream:
            for text in stream.text_stream:
                answer_chunks.append(text)
            final = stream.get_final_message()
            stop_reason = final.stop_reason
            usage = getattr(final, "usage", None)
            if usage:
                usage_in = getattr(usage, "input_tokens", 0) or 0
                usage_out = getattr(usage, "output_tokens", 0) or 0
        return "".join(answer_chunks), stop_reason, usage_in, usage_out

    yield _sse({"type": "thinking"})

    loop = asyncio.get_event_loop()
    pending = loop.run_in_executor(None, stream_blocking)

    last_seen = 0
    while not pending.done():
        await asyncio.sleep(0.1)
        if len(answer_chunks) > last_seen:
            new_text = "".join(answer_chunks[last_seen:])
            last_seen = len(answer_chunks)
            yield _sse({"type": "text", "chunk": new_text})

    answer, stop_reason, usage_in, usage_out = await pending

    if last_seen < len(answer_chunks):
        yield _sse({"type": "text", "chunk": "".join(answer_chunks[last_seen:])})

    chat.history.append({"role": "assistant", "content": answer})

    get_telemetry().record_event(
        Event(
            kind="claude",
            timestamp=time.time(),
            duration_ms=(time.perf_counter() - started) * 1000,
            success=stop_reason in (None, "end_turn", "stop_sequence"),
            label=settings.claude_model,
            detail=user_message[:140],
            tokens_in=usage_in,
            tokens_out=usage_out,
        )
    )
    yield _sse({"type": "usage", "tokens_in": usage_in, "tokens_out": usage_out})

    if stop_reason == "max_tokens":
        yield _sse({"type": "warning", "message": "Response was truncated (token limit hit)."})
        return

    code = extract_code_block(answer)
    if not code:
        success = True
        return

    yield _sse({"type": "code", "code": code})
    report = validate(code, allow_destructive=not settings.safe_mode)
    yield _sse(
        {
            "type": "sandbox",
            "is_safe": report.is_safe,
            "has_destructive_intent": report.has_destructive_intent,
            "violations": report.violations,
        }
    )
    if not report.is_safe:
        return

    buffer = io.StringIO()
    exec_globals = build_exec_globals(state.client.call, state.client.rest, tabulate)  # type: ignore[union-attr]
    with contextlib.redirect_stdout(buffer):
        try:
            exec(code, exec_globals)
            exec_error = None
        except Exception as exc:
            exec_error = str(exc)
    output = buffer.getvalue()
    yield _sse(
        {
            "type": "output",
            "stdout": output,
            "error": exec_error,
            "iso_time": datetime.utcnow().isoformat() + "Z",
        }
    )
    success = exec_error is None
    _ = success  # currently unused; reserved for future telemetry hook


def _sse(payload: dict[str, Any]) -> bytes:
    """Format a payload as a Server-Sent Events ``data:`` frame."""
    return f"data: {json.dumps(payload)}\n\n".encode()
