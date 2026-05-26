"""Conversational CSV analysis (delegates to Claude)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from csw_agent.ai.claude import build_csv_globals
from csw_agent.csv_tools import csv_context, load_csv_rows
from csw_agent.tabulate_fallback import tabulate

if TYPE_CHECKING:
    from csw_agent.queries import QueryContext


def chat_about_last_csv(ctx: QueryContext) -> None:
    """Open a CSV chat session against the last exported CSV."""
    if not ctx.last_generated_csv:
        print("  No CSV has been generated in this session yet.")
        return
    chat_about_csv(ctx, ctx.last_generated_csv)


def chat_about_csv(ctx: QueryContext, filepath: Path) -> None:
    """REPL: ask Claude questions about a CSV file."""
    if not ctx.claude:
        print("  Claude not available.")
        return
    if not filepath.exists():
        print("  CSV file not found.")
        return
    try:
        rows = load_csv_rows(filepath)
    except Exception as exc:
        print(f"  Error loading CSV: {exc}")
        return

    print(f"\n  Claude CSV Mode — {filepath.name}")
    print(f"  Rows loaded: {len(rows):,}")
    print("  Ask questions about this CSV. Type 'back' to return, 'clear' to reset memory.\n")

    context = csv_context(filepath, rows)
    csv_history = ctx.claude.history
    saved_history = list(csv_history)
    csv_history.clear()
    try:
        while True:
            try:
                question = input("  CSV You: ").strip()
            except EOFError:
                break
            lowered = question.lower()
            if lowered in ("back", "exit", "quit", "menu"):
                break
            if lowered == "clear":
                csv_history.clear()
                print("  ✓ Conversation memory cleared.")
                continue
            if not question:
                continue
            ctx.claude.ask_csv(question, context, build_csv_globals(rows, tabulate))
    finally:
        csv_history.clear()
        csv_history.extend(saved_history)
