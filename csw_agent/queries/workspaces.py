"""Workspace and scope queries."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

from csw_agent.csv_tools import write_csv
from csw_agent.queries._helpers import (
    fetch_scopes,
    fetch_workspaces,
    percentage,
    timestamped_path,
)
from csw_agent.tabulate_fallback import tabulate

if TYPE_CHECKING:
    from csw_agent.queries import QueryContext


def workspace_summary(ctx: QueryContext) -> None:
    """High-level workspace counts (analysis/enforcement)."""
    print("  Fetching workspaces...")
    workspaces, error = fetch_workspaces(ctx.client)
    if error:
        print(f"  Error: {error}")
        return
    total = len(workspaces)
    analyzed = sum(1 for w in workspaces if w.get("analysis_enabled"))
    enforced = sum(1 for w in workspaces if w.get("enforcement_enabled"))
    summary = [
        ["Total workspaces", f"{total:,}"],
        ["Analysis enabled", f"{analyzed:,} ({percentage(analyzed, total)})"],
        ["Enforcement enabled", f"{enforced:,} ({percentage(enforced, total)})"],
        ["Neither", f"{max(total - analyzed, 0):,}"],
    ]
    print(tabulate(summary, headers=["Metric", "Value"], tablefmt="grid"))


def scope_tree(ctx: QueryContext) -> None:
    """Show scope hierarchy."""
    print("  Fetching scopes...")
    scopes, error = fetch_scopes(ctx.client)
    if error:
        print(f"  Error: {error}")
        return
    rows = [
        [
            s.get("short_name", "") or "",
            s.get("name", "") or "",
            (s.get("id", "") or "")[:12] + "...",
            len(s.get("child_app_scope_ids") or []),
        ]
        for s in sorted(scopes, key=lambda x: (x.get("name") or "").lower())
    ]
    if len(rows) > 30:
        print(f"  Showing first 30 of {len(rows)} scopes:")
        rows = rows[:30]
    print(tabulate(rows, headers=["Short Name", "Full Name", "ID", "Children"], tablefmt="grid"))


def search_workspace(ctx: QueryContext) -> None:
    """Interactive: search workspaces by partial name."""
    name = input("  Enter workspace name (partial): ").strip()
    if not name:
        return
    workspaces, error = fetch_workspaces(ctx.client)
    if error:
        print(f"  Error: {error}")
        return
    matches = [w for w in workspaces if name.lower() in (w.get("name") or "").lower()]
    if not matches:
        print(f"  No workspaces matching '{name}'")
        return
    rows = [
        [
            w.get("name", ""),
            "Yes" if w.get("analysis_enabled") else "No",
            "Yes" if w.get("enforcement_enabled") else "No",
            (w.get("id", "") or "")[:12] + "...",
        ]
        for w in matches[:20]
    ]
    print(f"\n  Found {len(matches)} matching workspace(s):")
    print(tabulate(rows, headers=["Name", "Analysis", "Enforcement", "ID"], tablefmt="grid"))


def workspaces_by_scope(ctx: QueryContext) -> None:
    """Export every workspace and its scope to a CSV file."""
    print("  Fetching workspaces and scopes...")
    workspaces, ws_err = fetch_workspaces(ctx.client)
    if ws_err:
        print(f"  Error fetching workspaces: {ws_err}")
        return
    scopes, sc_err = fetch_scopes(ctx.client)
    if sc_err:
        print(f"  Error fetching scopes: {sc_err}")
        return

    scope_map = {s["id"]: s.get("name") or s.get("short_name") or "Unknown" for s in scopes}
    print(f"  ✓ Found {len(workspaces)} workspaces across {len(scopes)} scopes")

    rows = sorted(
        (_workspace_row(w, scope_map) for w in workspaces),
        key=lambda r: ((r["scope_name"] or "").lower(), (r["workspace_name"] or "").lower()),
    )

    columns = [
        "workspace_name",
        "workspace_id",
        "scope_name",
        "scope_id",
        "primary",
        "analysis_enabled",
        "enforcement_enabled",
        "author",
        "latest_adm_version",
        "analyzed_version",
        "enforced_version",
        "created_at",
        "description",
    ]
    filepath = timestamped_path("workspaces_by_scope")
    written = write_csv(filepath, columns, rows)
    print(f"  ✓ Exported {written} workspaces to:\n    {filepath}")
    ctx.last_generated_csv = filepath

    analyzed = sum(1 for r in rows if r["analysis_enabled"] is True)
    enforced = sum(1 for r in rows if r["enforcement_enabled"] is True)
    unique_scopes = len({r["scope_name"] for r in rows})
    print("\n  Summary:")
    print(f"    Total workspaces: {len(rows)}")
    print(f"    Unique scopes:    {unique_scopes}")
    print(f"    Analysis enabled: {analyzed}")
    print(f"    Enforcement enabled: {enforced}")


def _workspace_row(workspace: dict[str, Any], scope_map: dict[str, str]) -> dict[str, Any]:
    sid = workspace.get("app_scope_id", "")
    return {
        "workspace_name": workspace.get("name", ""),
        "workspace_id": workspace.get("id", ""),
        "scope_name": scope_map.get(sid, sid),
        "scope_id": sid,
        "primary": workspace.get("primary", ""),
        "analysis_enabled": workspace.get("analysis_enabled", ""),
        "enforcement_enabled": workspace.get("enforcement_enabled", ""),
        "author": workspace.get("author", ""),
        "latest_adm_version": workspace.get("latest_adm_version", ""),
        "analyzed_version": workspace.get("analyzed_version", ""),
        "enforced_version": workspace.get("enforced_version", ""),
        "created_at": _format_ts(workspace.get("created_at")),
        "description": workspace.get("description", ""),
    }


def _format_ts(value: float | None) -> str:
    if not value:
        return ""
    try:
        return datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError, OSError):
        return str(value)
