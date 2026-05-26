"""Interactive CLI entry point."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from csw_agent import __version__
from csw_agent.ai.claude import (
    ClaudeRunner,
    build_exec_globals,
)
from csw_agent.ai.claude import (
    health_check as claude_health_check,
)
from csw_agent.client import CSWClient
from csw_agent.config import Settings
from csw_agent.queries import Query, QueryContext, build_registry
from csw_agent.tabulate_fallback import tabulate
from csw_agent.telemetry import Event, TelemetryLogHandler, get_telemetry

logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="csw-agent", description="Cisco Secure Workload OpenAPI agent")
    parser.add_argument("--endpoint", help="CSW API endpoint URL (overrides CSW_ENDPOINT)")
    parser.add_argument("--credentials", type=Path, help="Path to credentials JSON")
    parser.add_argument("--model", help="Claude model identifier")
    parser.add_argument("--insecure", action="store_true", help="Disable TLS verification (NOT recommended)")
    parser.add_argument(
        "--unsafe", action="store_true", help="Disable safe mode (no destructive-call confirmation)"
    )
    parser.add_argument("--verbose", "-v", action="count", default=0, help="Increase log verbosity")
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    sub = parser.add_subparsers(dest="command")
    dash = sub.add_parser("dashboard", help="Launch the web dashboard")
    dash.add_argument("--host", default="127.0.0.1", help="Bind host")
    dash.add_argument("--port", type=int, default=8765, help="Bind port")
    dash.add_argument("--reload", action="store_true", help="Enable auto-reload (development only)")
    return parser.parse_args(argv)


def configure_logging(verbosity: int, settings_level: str) -> None:
    if verbosity >= 2:
        level = logging.DEBUG
    elif verbosity == 1:
        level = logging.INFO
    else:
        level = getattr(logging, settings_level.upper(), logging.WARNING)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    handler = TelemetryLogHandler(get_telemetry(), level=level)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logging.getLogger().addHandler(handler)


def build_settings(args: argparse.Namespace) -> Settings:
    settings = Settings.from_env()
    if args.endpoint:
        settings.api_endpoint = args.endpoint
    if args.credentials:
        settings.credentials_file = args.credentials
    if args.model:
        settings.claude_model = args.model
    if args.insecure:
        settings.verify_tls = False
    if args.unsafe:
        settings.safe_mode = False
    return settings


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = build_settings(args)
    configure_logging(args.verbose, settings.log_level)

    if getattr(args, "command", None) == "dashboard":
        from csw_agent.dashboard.server import run as run_dashboard

        return run_dashboard(settings, host=args.host, port=args.port, reload=args.reload)

    print("=" * 70)
    print("  Cisco Secure Workload - OpenAPI Interactive Agent")
    print("=" * 70)

    client = _connect_client(settings)
    claude_runner = _connect_claude(settings)
    print(f"\n  Safe mode: {'ON' if settings.safe_mode else 'OFF'}")

    if client is None:
        print("\n  Aborting: CSW client could not be initialized.")
        return 1

    ctx = QueryContext(client=client, settings=settings, claude=claude_runner)
    registry = build_registry()
    return _run_loop(ctx, registry)


def _connect_client(settings: Settings) -> CSWClient | None:
    print("\n  Connecting to CSW...")
    try:
        client = CSWClient(settings)
    except FileNotFoundError as exc:
        print(f"  ✗ {exc}")
        return None
    if client.health_check():
        print(f"  ✓ Connected to {settings.api_endpoint}")
        return client
    print(f"  ✗ Could not connect to CSW at {settings.api_endpoint}")
    return client  # keep going so user can still inspect locally


def _connect_claude(settings: Settings) -> ClaudeRunner | None:
    if not claude_health_check(settings):
        print("  ✗ Claude AI not available (ensure ClaudeGate is running)")
        return None
    runner = ClaudeRunner(
        settings=settings,
        safe_mode=settings.safe_mode,
        confirm_callback=_confirm_destructive,
    )
    print(f"  ✓ Claude AI available via ClaudeGate ({settings.claudegate_url})")
    print(f"    Model: {settings.claude_model}")
    return runner


def _confirm_destructive(message: str) -> bool:
    try:
        answer = input(f"\n  ⚠ {message} [y/N]: ").strip().lower()
    except EOFError:
        return False
    return answer == "y"


def _run_loop(ctx: QueryContext, registry: list[Query]) -> int:
    has_claude = ctx.claude is not None
    ai_mode = has_claude
    while True:
        _print_command_menu(has_claude)
        try:
            cmd = input("\n  Command: ").strip().lower()
        except EOFError:
            print()
            return 0

        if cmd in ("quit", "exit", "q"):
            print("\n  Goodbye!")
            return 0
        if cmd == "info":
            _print_info(ctx, ai_mode)
        elif cmd == "safe":
            ctx.settings.safe_mode = not ctx.settings.safe_mode
            if ctx.claude:
                ctx.claude.safe_mode = ctx.settings.safe_mode
            print(f"  Safe mode: {'ON' if ctx.settings.safe_mode else 'OFF'}")
        elif cmd == "ai":
            if has_claude:
                ai_mode = True
                print("  Switched to Claude AI mode.")
            else:
                print("  Claude not available.")
        elif cmd == "local":
            ai_mode = False
            print("  Switched to local mode.")
        elif cmd == "query":
            _handle_query(ctx, registry, ai_mode and has_claude)
        else:
            print(f"  Unknown command: {cmd}")


def _print_command_menu(has_claude: bool) -> None:
    print(f"\n  {'─' * 60}")
    print("  Commands:")
    print("    [query]   Query CSW (AI or local mode)")
    if has_claude:
        print("    [ai]      Switch to Claude AI mode")
        print("    [local]   Switch to local mode (pre-built queries)")
    print("    [safe]    Toggle safe mode (confirm writes)")
    print("    [info]    Show connection info")
    print("    [quit]    Exit")
    print(f"  {'─' * 60}")


def _print_info(ctx: QueryContext, ai_mode: bool) -> None:
    print(f"\n  CSW Endpoint: {ctx.settings.api_endpoint}")
    print(f"  Credentials:  {ctx.settings.credentials_file}")
    print(f"  ClaudeGate:   {ctx.settings.claudegate_url}")
    print(f"  AI Mode:      {'Claude AI' if ai_mode else 'Local'}")
    print(f"  Safe Mode:    {'ON' if ctx.settings.safe_mode else 'OFF'}")


def _handle_query(ctx: QueryContext, registry: list[Query], use_ai: bool) -> None:
    if not ctx.client:
        print("  CSW not connected. Check credentials.")
        return
    if use_ai and ctx.claude:
        _run_ai_loop(ctx)
    else:
        _run_local_menu(ctx, registry)


def _run_ai_loop(ctx: QueryContext) -> None:
    print("\n  Claude AI Mode — ask anything about your CSW deployment")
    print("  Type 'back' to return, 'clear' to reset memory.\n")
    assert ctx.claude is not None
    ctx.claude.reset_history()
    exec_globals = build_exec_globals(ctx.client.call, ctx.client.rest, tabulate)
    while True:
        try:
            question = input("  You: ").strip()
        except EOFError:
            return
        lowered = question.lower()
        if lowered in ("back", "exit", "quit", "menu"):
            return
        if lowered == "clear":
            ctx.claude.reset_history()
            print("  ✓ Conversation memory cleared.")
            continue
        if not question:
            continue
        ctx.claude.ask(question, exec_globals)


def _run_local_menu(ctx: QueryContext, registry: list[Query]) -> None:
    print(f"\n  {'═' * 60}")
    print("  Available Queries:")
    print(f"  {'═' * 60}")
    for q in registry:
        print(f"  [{q.key:>2}] {q.label}")
    print(f"  {'═' * 60}")
    by_key = {q.key: q for q in registry}
    while True:
        try:
            choice = input("\n  Select query (or 'back'): ").strip()
        except EOFError:
            return
        if choice.lower() in ("back", "exit", "quit", "menu"):
            return
        query = by_key.get(choice)
        if not query:
            print("  Invalid choice.")
            continue
        print()
        started = time.perf_counter()
        success = False
        try:
            query.func(ctx)
            success = True
        except Exception as exc:
            logger.exception("Query %s failed", query.key)
            print(f"  ⚠ Query failed: {exc}")
        finally:
            get_telemetry().record_event(
                Event(
                    kind="query",
                    timestamp=time.time(),
                    duration_ms=(time.perf_counter() - started) * 1000,
                    success=success,
                    label=query.label,
                )
            )


if __name__ == "__main__":  # pragma: no cover
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n  Agent terminated. Goodbye!")
        sys.exit(0)
