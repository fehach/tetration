"""Claude integration: streaming, prompt assembly, sandboxed execution."""

from __future__ import annotations

import logging
import sys
import time
from collections import Counter, defaultdict
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from importlib import resources
from typing import Any

from csw_agent.ai.sandbox import SandboxReport, validate
from csw_agent.config import Settings
from csw_agent.telemetry import Event, Telemetry, get_telemetry

logger = logging.getLogger(__name__)


def load_prompt(name: str) -> str:
    """Read a prompt from the packaged ``ai/prompts`` directory."""
    return resources.files("csw_agent.ai.prompts").joinpath(name).read_text(encoding="utf-8")


def extract_code_block(text: str) -> str | None:
    """Return the first fenced code block in ``text`` (preferring ```python)."""
    if "```python" in text:
        return text.split("```python", 1)[1].split("```", 1)[0].strip()
    if "```" in text:
        return text.split("```", 1)[1].split("```", 1)[0].strip()
    return None


@dataclass
class ClaudeRunner:
    """Send messages to Claude and execute returned code in a sandbox."""

    settings: Settings
    safe_mode: bool
    confirm_callback: Callable[[str], bool] = field(default=lambda msg: False)
    telemetry: Telemetry = field(default_factory=get_telemetry)
    history: list[dict[str, str]] = field(default_factory=list)
    _client: Any = field(default=None, init=False)

    def __post_init__(self) -> None:
        import anthropic

        self._client = anthropic.Anthropic(
            api_key=self.settings.claudegate_api_key,
            base_url=self.settings.claudegate_url,
        )

    def reset_history(self) -> None:
        self.history.clear()

    def stream(self, system: str, max_tokens: int) -> tuple[str, str | None]:
        """Stream a response. Returns (full_text, stop_reason)."""
        chunks: list[str] = []
        sys.stdout.write("  Thinking")
        sys.stdout.flush()
        started = time.perf_counter()
        usage_in = 0
        usage_out = 0
        success = False
        question_preview = self.history[-1]["content"][:140] if self.history else ""
        try:
            with self._client.messages.stream(
                model=self.settings.claude_model,
                max_tokens=max_tokens,
                system=system,
                messages=self.history,
            ) as stream:
                for text in stream.text_stream:
                    chunks.append(text)
                    sys.stdout.write(".")
                    sys.stdout.flush()
                final = stream.get_final_message()
                stop_reason = final.stop_reason
                usage = getattr(final, "usage", None)
                if usage:
                    usage_in = getattr(usage, "input_tokens", 0) or 0
                    usage_out = getattr(usage, "output_tokens", 0) or 0
            success = stop_reason in (None, "end_turn", "stop_sequence")
        finally:
            sys.stdout.write("\n")
            self.telemetry.record_event(
                Event(
                    kind="claude",
                    timestamp=time.time(),
                    duration_ms=(time.perf_counter() - started) * 1000,
                    success=success,
                    label=self.settings.claude_model,
                    detail=question_preview,
                    tokens_in=usage_in,
                    tokens_out=usage_out,
                )
            )
        return "".join(chunks), stop_reason

    def ask(self, question: str, exec_globals: Mapping[str, Any]) -> None:
        """Ask Claude a question and execute the returned code if any."""
        system = load_prompt("system.md") + "\n\n" + load_prompt("api_reference.md")
        self._append_user(question)
        self._chat(system, exec_globals, max_tokens=self.settings.max_tokens_code, attempt=0)

    def ask_csv(self, question: str, csv_context: str, exec_globals: Mapping[str, Any]) -> None:
        """Ask Claude a CSV-related question."""
        system = load_prompt("csv_system.md").replace("{context}", csv_context)
        self._append_user(question)
        self._chat(system, exec_globals, max_tokens=self.settings.max_tokens_csv, attempt=0)

    def _chat(
        self,
        system: str,
        exec_globals: Mapping[str, Any],
        max_tokens: int,
        attempt: int,
    ) -> None:
        try:
            answer, stop_reason = self.stream(system, max_tokens)
        except Exception as exc:
            logger.error("Claude request failed: %s", exc)
            self._pop_user()
            return

        if stop_reason == "max_tokens":
            print("\n  ⚠ Response was truncated (hit token limit). Try a narrower question.")
            self._pop_user()
            return

        code = extract_code_block(answer)
        if not code:
            print(f"\n  {answer}")
            self.history.append({"role": "assistant", "content": answer})
            self._truncate_history()
            return

        self._print_code(code)
        report = validate(code, allow_destructive=not self.safe_mode)
        if not report.is_safe:
            self._handle_unsafe(report, system, exec_globals, max_tokens, attempt, answer)
            return

        if (
            report.has_destructive_intent
            and self.safe_mode
            and not self.confirm_callback("This code performs a destructive operation. Execute?")
        ):
            print("  Cancelled.")
            self._pop_user()
            return

        try:
            exec(code, dict(exec_globals))
        except Exception as exc:
            logger.exception("Generated code raised an exception")
            print(f"  ⚠ Code raised: {exc}")

        self.history.append({"role": "assistant", "content": answer})
        self._truncate_history()

    def _handle_unsafe(
        self,
        report: SandboxReport,
        system: str,
        exec_globals: Mapping[str, Any],
        max_tokens: int,
        attempt: int,
        previous_answer: str,
    ) -> None:
        print(f"\n  ⚠ Code rejected by sandbox: {report.reason()}")
        if attempt >= self.settings.syntax_retry_limit:
            print("  Retry limit reached; aborting.")
            self._pop_user()
            return
        print("  Asking Claude to regenerate safer code...")
        self.history.append({"role": "assistant", "content": previous_answer})
        self._append_user(
            "Your previous code was rejected by the sandbox: "
            f"{report.reason()}. Please regenerate the COMPLETE corrected code that "
            "avoids those constructs."
        )
        self._chat(system, exec_globals, max_tokens, attempt + 1)

    def _append_user(self, content: str) -> None:
        self.history.append({"role": "user", "content": content})

    def _pop_user(self) -> None:
        if self.history and self.history[-1]["role"] == "user":
            self.history.pop()

    def _truncate_history(self) -> None:
        max_messages = self.settings.max_history_turns * 2
        if len(self.history) > max_messages:
            self.history[:] = self.history[-max_messages:]

    @staticmethod
    def _print_code(code: str) -> None:
        print("\n  [Claude generated code]")
        print(f"  {'─' * 70}")
        for line in code.split("\n"):
            print(f"  {line}")
        print(f"  {'─' * 70}")


def build_exec_globals(
    api_call: Callable[..., Any], rest_client: Any, tabulate_fn: Callable[..., str]
) -> dict[str, Any]:
    """Globals available to Claude-generated code in the API context."""
    return {
        "restclient": rest_client,
        "api_call": api_call,
        "json": __import__("json"),
        "tabulate": tabulate_fn,
        "datetime": datetime,
        "time": __import__("time"),
    }


def build_csv_globals(rows: list[dict[str, Any]], tabulate_fn: Callable[..., str]) -> dict[str, Any]:
    """Globals available to Claude-generated code in the CSV context."""
    from csw_agent import csv_tools

    return {
        "rows": rows,
        "tabulate": tabulate_fn,
        "json": __import__("json"),
        "Counter": Counter,
        "defaultdict": defaultdict,
        "to_bool": csv_tools.to_bool,
        "is_blank": csv_tools.is_blank,
        "display_value": csv_tools.display_value,
        "to_number": csv_tools.to_number,
        "safe_pct": csv_tools.safe_pct,
    }


def health_check(settings: Settings) -> bool:
    """Verify Claude connectivity without consuming significant tokens."""
    try:
        import anthropic
    except ImportError:
        logger.warning("anthropic package is not installed.")
        return False
    try:
        client = anthropic.Anthropic(
            api_key=settings.claudegate_api_key,
            base_url=settings.claudegate_url,
        )
        client.messages.create(
            model=settings.claude_model,
            max_tokens=1,
            messages=[{"role": "user", "content": "."}],
        )
        return True
    except Exception as exc:
        logger.warning("Claude health check failed: %s", exc)
        return False
