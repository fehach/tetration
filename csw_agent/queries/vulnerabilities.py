"""Vulnerability export query."""

from __future__ import annotations

import json
from collections import Counter
from typing import TYPE_CHECKING, Any

from csw_agent.csv_tools import write_csv
from csw_agent.queries._helpers import fetch_all_sensors, timestamped_path

if TYPE_CHECKING:
    from csw_agent.queries import QueryContext


def vulnerability_report(ctx: QueryContext) -> None:
    """Interactive vulnerability export: pick an agent, dump its CVEs to CSV."""
    search_term = input("  Enter agent hostname (or partial name): ").strip()
    if not search_term:
        print("  No hostname provided.")
        return

    print(f"  Searching for agent matching '{search_term}'...")
    sensors, error = fetch_all_sensors(ctx.client)
    if error:
        print(f"  Error fetching sensors: {error}")
        return

    matches = [s for s in sensors if search_term.lower() in (s.get("host_name") or "").lower()]
    if not matches:
        print(f"  Agent '{search_term}' not found among {len(sensors)} agents.")
        return
    agent = _pick_agent(matches)
    agent_uuid = agent.get("uuid", "")
    hostname = agent.get("host_name", "unknown")
    print(f"  ✓ Agent: {hostname} (UUID: {agent_uuid})")

    print(f"  Fetching vulnerabilities for {hostname}...")
    data, vuln_error = ctx.client.call("GET", f"/workload/{agent_uuid}/vulnerabilities")
    if vuln_error:
        print(f"  Error: {vuln_error}")
        return
    vulnerabilities = data if isinstance(data, list) else []
    if not vulnerabilities:
        print(f"  No vulnerabilities found for {hostname}.")
        return
    print(f"  ✓ Found {len(vulnerabilities)} vulnerabilities")

    columns = _vuln_columns(vulnerabilities)
    rows = [_flatten_vuln_row(v, columns) for v in vulnerabilities]

    filepath = timestamped_path(f"vulnerabilities_{hostname}")
    written = write_csv(filepath, columns, rows)
    print(f"  ✓ Exported {written} vulnerabilities to:\n    {filepath}")
    ctx.last_generated_csv = filepath
    _print_severity_summary(vulnerabilities)


def _pick_agent(matches: list[dict[str, Any]]) -> dict[str, Any]:
    if len(matches) == 1:
        return matches[0]
    print(f"  Found {len(matches)} matching agents:")
    for i, m in enumerate(matches[:10], 1):
        print(
            f"    {i}. {m.get('host_name', '')} (UUID: {(m.get('uuid') or '')[:12]}... IP: {m.get('client_ip', '')})"
        )
    if len(matches) > 10:
        print(f"    ... and {len(matches) - 10} more")
    choice = input("  Select agent number [1]: ").strip()
    if choice.isdigit() and 0 < int(choice) <= len(matches):
        return matches[int(choice) - 1]
    return matches[0]


def _vuln_columns(vulnerabilities: list[dict[str, Any]]) -> list[str]:
    all_keys: set[str] = set()
    for v in vulnerabilities:
        all_keys.update(v.keys())
    priority = [
        "cve_id",
        "severity",
        "cvss_v2",
        "cvss_v3",
        "package_name",
        "package_version",
        "fixed_version",
        "description",
        "v2_score",
        "v3_score",
    ]
    columns = [c for c in priority if c in all_keys]
    columns += sorted(all_keys - set(columns))
    return columns


def _flatten_vuln_row(vuln: dict[str, Any], columns: list[str]) -> dict[str, Any]:
    row: dict[str, Any] = {}
    for col in columns:
        value = vuln.get(col, "")
        row[col] = json.dumps(value) if isinstance(value, (dict, list)) else value
    return row


def _print_severity_summary(vulnerabilities: list[dict[str, Any]]) -> None:
    counts = Counter(
        str(v.get("severity") or v.get("v3_severity") or v.get("v2_severity") or "Unknown")
        for v in vulnerabilities
    )
    if not counts:
        return
    print("\n  Severity Summary:")
    for sev in sorted(counts):
        print(f"    {sev}: {counts[sev]}")
