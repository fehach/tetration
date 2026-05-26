"""Agent-focused queries: summary, version distribution, recent activity."""

from __future__ import annotations

import time
from collections import Counter
from datetime import datetime
from typing import TYPE_CHECKING, Any

from csw_agent.queries._helpers import fetch_all_sensors, percentage
from csw_agent.tabulate_fallback import tabulate

if TYPE_CHECKING:
    from csw_agent.queries import QueryContext


def agent_summary(ctx: QueryContext) -> None:
    """Show agent counts grouped by platform and agent type."""
    print("  Fetching all agents...")
    sensors, error = fetch_all_sensors(ctx.client)
    if error:
        print(f"  Error: {error}")
        return
    print(f"  Total agents: {len(sensors):,}")

    platforms = Counter(s.get("platform") or "Unknown" for s in sensors)
    types = Counter(s.get("agent_type_str") or "Unknown" for s in sensors)
    _print_counter("By Platform", "Platform", platforms)
    _print_counter("By Agent Type", "Agent Type", types)


def agent_versions(ctx: QueryContext) -> None:
    """Show agent software version distribution and pending upgrades."""
    print("  Fetching all agents...")
    sensors, error = fetch_all_sensors(ctx.client)
    if error:
        print(f"  Error: {error}")
        return
    print(f"  Total agents: {len(sensors):,}\n")

    versions = Counter(s.get("current_sw_version") or "Unknown" for s in sensors)
    rows = [
        [version, f"{count:,}", percentage(count, len(sensors))] for version, count in versions.most_common()
    ]
    print("  Agent Version Distribution:")
    print(tabulate(rows, headers=["Version", "Count", "%"], tablefmt="grid"))

    mismatches = [
        s
        for s in sensors
        if s.get("desired_sw_version") and s.get("desired_sw_version") != s.get("current_sw_version")
    ]
    if not mismatches:
        return
    print(f"\n  ⚠ {len(mismatches)} agents with pending upgrade (desired != current):")
    rows = [
        [s.get("host_name", ""), s.get("current_sw_version", ""), s.get("desired_sw_version", "")]
        for s in mismatches[:15]
    ]
    print(tabulate(rows, headers=["Hostname", "Current", "Desired"], tablefmt="grid"))
    if len(mismatches) > 15:
        print(f"  ... and {len(mismatches) - 15} more")


def recent_agents(ctx: QueryContext) -> None:
    """Show agents created/deleted/uninstalled in the last 30 days."""
    print("  Fetching all agents...")
    sensors, error = fetch_all_sensors(ctx.client)
    if error:
        print(f"  Error: {error}")
        return

    cutoff = time.time() - 30 * 24 * 3600
    _show_recent(sensors, "created_at", "Created", cutoff)
    _show_recent(sensors, "deleted_at", "Deleted", cutoff)
    _show_recent(sensors, "uninstalled_at", "Uninstalled", cutoff)


def _show_recent(sensors: list[dict[str, Any]], field: str, label: str, cutoff: float) -> None:
    matches = [s for s in sensors if s.get(field) and s[field] > cutoff]
    matches.sort(key=lambda x: x.get(field, 0), reverse=True)
    print(f"\n  Agents {label.lower()} in the last 30 days: {len(matches)}")
    if not matches:
        return

    def _fmt_ts(value: float | None) -> str:
        if not value:
            return "N/A"
        try:
            return datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M")
        except (TypeError, ValueError, OSError):
            return str(value)

    rows = [[s.get("host_name", ""), s.get("platform", ""), _fmt_ts(s.get(field))] for s in matches[:20]]
    print(tabulate(rows, headers=["Hostname", "Platform", label], tablefmt="grid"))
    if len(matches) > 20:
        print(f"  ... and {len(matches) - 20} more")


def _print_counter(title: str, label: str, counter: Counter) -> None:
    rows = [[name, f"{count:,}"] for name, count in counter.most_common()]
    print(f"\n  {title}:")
    print(tabulate(rows, headers=[label, "Count"], tablefmt="grid"))
