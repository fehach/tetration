"""Agent enforcement queries (deduplicated from the original 4 variants)."""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from csw_agent.csv_tools import write_csv
from csw_agent.queries._helpers import (
    build_hostname_to_workspace,
    fetch_all_sensors,
    percentage,
    primary_ip,
    timestamped_path,
)
from csw_agent.tabulate_fallback import tabulate

if TYPE_CHECKING:
    from csw_agent.queries import QueryContext


# ─── Parameterized core ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class EnforcementReport:
    """Configuration for an enforcement-style CSV report."""

    output_basename: str
    summary_title: str
    enabled_filter: bool
    workspace_filter: Callable[[bool], bool]


def _run_enforcement_report(ctx: QueryContext, report: EnforcementReport) -> Path | None:
    """Execute a parameterized enforcement report. Returns the CSV path written."""
    print("  Fetching all agents...")
    sensors, error = fetch_all_sensors(ctx.client)
    if error:
        print(f"  Error: {error}")
        return None
    target = [s for s in sensors if bool(s.get("enforcement_enabled")) == report.enabled_filter]
    print(f"  Total agents: {len(sensors):,}")
    print(f"  Enforcement {'enabled' if report.enabled_filter else 'disabled'}: {len(target):,}")

    hostname_to_ws = ctx.workspace_cache.get_or_compute(
        lambda: build_hostname_to_workspace(ctx.client),
    )
    if hostname_to_ws[0] is None:
        return None
    mapping, total_ws, enf_ws = hostname_to_ws

    columns = [
        "hostname",
        "ip_address",
        "current_sw_version",
        "enforcement_enabled",
        "workspace_enforcement_enabled",
        "workspace_name",
    ]
    rows: list[dict[str, Any]] = []
    matched = 0
    in_enforced_ws = 0
    for agent in target:
        host = agent.get("host_name", "") or ""
        ws = mapping.get(host.lower())
        ws_enforcement = bool(ws.get("enforcement_enabled")) if ws else False
        ws_name = ws["name"] if ws else ""
        if ws_name:
            matched += 1
        if ws_enforcement:
            in_enforced_ws += 1
        if not report.workspace_filter(ws_enforcement):
            continue
        rows.append(
            {
                "hostname": host,
                "ip_address": primary_ip(agent),
                "current_sw_version": agent.get("current_sw_version", "") or "",
                "enforcement_enabled": agent.get("enforcement_enabled", False),
                "workspace_enforcement_enabled": ws_enforcement,
                "workspace_name": ws_name,
            }
        )

    filepath = timestamped_path(report.output_basename)
    written = write_csv(filepath, columns, rows)
    print(f"\n  Successfully wrote {written} rows to {filepath.name}")
    print(f"  Agents matched to a workspace: {matched}")
    print(f"  Agents in enforced workspaces (overall): {in_enforced_ws}")

    _print_summary(report.summary_title, len(sensors), target, total_ws, enf_ws, matched, written, filepath)
    ctx.last_generated_csv = filepath
    return filepath


def _print_summary(
    title: str,
    total_sensors: int,
    target_sensors: list[dict[str, Any]],
    total_ws: int,
    enf_ws: int,
    matched: int,
    written: int,
    filepath: Path,
) -> None:
    sep = "=" * 70
    print(f"\n  {sep}\n  {title}\n  {sep}")
    print(f"  Total Sensors:                    {total_sensors}")
    print(f"  Sensors in this group:            {len(target_sensors)}")
    print(f"  Total Workspaces:                 {total_ws}")
    print(f"  Workspaces with Enforcement:      {enf_ws}")
    print(f"  Agents Matched to Workspace:      {matched}")
    print(f"  Rows Written:                     {written}")
    print(f"  Output File:                      {filepath.name}")
    print(f"  {sep}")


# ─── Public query functions ─────────────────────────────────────────────────


def enforcement_status(ctx: QueryContext) -> None:
    """Show enforcement enabled/disabled split with per-platform breakdown."""
    print("  Fetching all agents...")
    sensors, error = fetch_all_sensors(ctx.client)
    if error:
        print(f"  Error: {error}")
        return
    enabled = [s for s in sensors if s.get("enforcement_enabled")]
    disabled = [s for s in sensors if not s.get("enforcement_enabled")]
    total = len(sensors)
    print(f"\n  Total agents: {total:,}")
    print(f"  Enforcement enabled:  {len(enabled):,} ({percentage(len(enabled), total)})")
    print(f"  Enforcement disabled: {len(disabled):,} ({percentage(len(disabled), total)})")

    hostname_to_ws = ctx.workspace_cache.get_or_compute(
        lambda: build_hostname_to_workspace(ctx.client),
    )
    mapping = hostname_to_ws[0] or {}

    if enabled:
        platforms = Counter(s.get("platform") or "Unknown" for s in enabled)
        rows = [[name, f"{count:,}"] for name, count in platforms.most_common()]
        print("\n  Enforcement Enabled — by Platform:")
        print(tabulate(rows, headers=["Platform", "Count"], tablefmt="grid"))

    if disabled:
        rows = []
        for s in disabled[:20]:
            ws = mapping.get((s.get("host_name") or "").lower())
            rows.append(
                [
                    s.get("host_name", ""),
                    s.get("platform", ""),
                    s.get("current_sw_version", ""),
                    ws["name"] if ws else "",
                ]
            )
        print("\n  Enforcement Disabled — first 20 agents:")
        print(tabulate(rows, headers=["Hostname", "Platform", "Version", "Workspace"], tablefmt="grid"))
        if len(disabled) > 20:
            print(f"  ... and {len(disabled) - 20} more")

        columns = ["host_name", "platform", "current_sw_version", "config_profile_name", "workspace_name"]
        csv_rows = [
            {
                "host_name": s.get("host_name", ""),
                "platform": s.get("platform", ""),
                "current_sw_version": s.get("current_sw_version", ""),
                "config_profile_name": s.get("config_profile_name", ""),
                "workspace_name": (mapping.get((s.get("host_name") or "").lower()) or {}).get("name", ""),
            }
            for s in disabled
        ]
        path = timestamped_path("enforcement_disabled")
        written = write_csv(path, columns, csv_rows)
        print(f"\n  ✓ Exported {written} enforcement-disabled agents to:\n    {path}")
        ctx.last_generated_csv = path


def no_enf_no_workspace(ctx: QueryContext) -> None:
    """Agents without enforcement that are NOT covered by any enforced workspace."""
    _run_enforcement_report(
        ctx,
        EnforcementReport(
            output_basename="agents_no_enf_no_workspace",
            summary_title="SUMMARY: agents without enforcement & not in enforcement workspace",
            enabled_filter=False,
            workspace_filter=lambda ws_enforced: not ws_enforced,
        ),
    )


def enf_in_workspace(ctx: QueryContext) -> None:
    """Agents with enforcement enabled, listed alongside their workspace status."""
    _run_enforcement_report(
        ctx,
        EnforcementReport(
            output_basename="agents_enforcement_enabled",
            summary_title="SUMMARY: agents with enforcement enabled",
            enabled_filter=True,
            workspace_filter=lambda _ws: True,
        ),
    )
    if ctx.last_generated_csv and ctx.claude:
        try:
            answer = input("\n  Ask Claude about this CSV now? [y/N]: ").strip().lower()
        except EOFError:
            answer = "n"
        if answer == "y":
            from csw_agent.queries.csv_chat import chat_about_csv

            chat_about_csv(ctx, ctx.last_generated_csv)


def no_enf_in_enf_workspace(ctx: QueryContext) -> None:
    """Agents without enforcement that ARE covered by an enforced workspace."""
    _run_enforcement_report(
        ctx,
        EnforcementReport(
            output_basename="agents_no_enf_in_enf_workspace",
            summary_title="SUMMARY: agents without enforcement & in enforcement workspace",
            enabled_filter=False,
            workspace_filter=lambda ws_enforced: ws_enforced,
        ),
    )
