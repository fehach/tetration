"""Web-friendly query catalog.

Each query is described by metadata (inputs the user needs to provide, expected
result shape) plus an executor. There are two flavors of executor:

- ``structured``: returns a typed dict the frontend renders as a native table.
- ``stdout``: runs the existing CLI query function with a captured stdout stream
  and returns the textual output plus any generated CSV files.
"""

from __future__ import annotations

import contextlib
import io
import logging
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from csw_agent.queries import QueryContext
from csw_agent.queries._helpers import (
    build_hostname_to_workspace,
    fetch_all_sensors,
    fetch_workspaces,
    primary_ip,
)

logger = logging.getLogger(__name__)

ResultKind = Literal["structured", "stdout"]


@dataclass(frozen=True)
class QueryInput:
    """Schema for a single user-provided input field."""

    name: str
    label: str
    placeholder: str = ""
    required: bool = True


@dataclass(frozen=True)
class WebQuery:
    """Definition of a query exposed via the dashboard."""

    key: str
    label: str
    description: str
    category: str
    result_kind: ResultKind
    inputs: tuple[QueryInput, ...] = ()
    needs_csw: bool = True
    structured_fn: Callable[..., dict[str, Any]] | None = None
    stdout_fn: Callable[..., dict[str, Any]] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "description": self.description,
            "category": self.category,
            "result_kind": self.result_kind,
            "needs_csw": self.needs_csw,
            "inputs": [
                {
                    "name": i.name,
                    "label": i.label,
                    "placeholder": i.placeholder,
                    "required": i.required,
                }
                for i in self.inputs
            ],
        }


# ── Structured query implementations ───────────────────────────────────────


def _structured_agent_summary(ctx: QueryContext) -> dict[str, Any]:
    sensors, error = fetch_all_sensors(ctx.client)
    if error:
        return {"error": error}
    platforms = Counter(s.get("platform") or "Unknown" for s in sensors)
    types = Counter(s.get("agent_type_str") or "Unknown" for s in sensors)
    return {
        "summary": {"total_agents": len(sensors)},
        "tables": [
            {
                "title": "By platform",
                "columns": [
                    {"key": "platform", "label": "Platform"},
                    {"key": "count", "label": "Count", "numeric": True},
                ],
                "rows": [{"platform": name, "count": count} for name, count in platforms.most_common()],
            },
            {
                "title": "By agent type",
                "columns": [
                    {"key": "agent_type", "label": "Agent type"},
                    {"key": "count", "label": "Count", "numeric": True},
                ],
                "rows": [{"agent_type": name, "count": count} for name, count in types.most_common()],
            },
        ],
    }


def _structured_workspace_summary(ctx: QueryContext) -> dict[str, Any]:
    workspaces, error = fetch_workspaces(ctx.client)
    if error:
        return {"error": error}
    total = len(workspaces)
    analyzed = sum(1 for w in workspaces if w.get("analysis_enabled"))
    enforced = sum(1 for w in workspaces if w.get("enforcement_enabled"))
    return {
        "summary": {
            "total_workspaces": total,
            "analysis_enabled": analyzed,
            "enforcement_enabled": enforced,
            "neither": max(total - analyzed, 0),
            "analysis_pct": _pct(analyzed, total),
            "enforcement_pct": _pct(enforced, total),
        }
    }


def _structured_enforcement_status(ctx: QueryContext) -> dict[str, Any]:
    sensors, error = fetch_all_sensors(ctx.client)
    if error:
        return {"error": error}
    enabled = [s for s in sensors if s.get("enforcement_enabled")]
    disabled = [s for s in sensors if not s.get("enforcement_enabled")]
    mapping_result = ctx.workspace_cache.get_or_compute(
        lambda: build_hostname_to_workspace(ctx.client),
    )
    mapping = mapping_result[0] or {}

    platforms_enabled = Counter(s.get("platform") or "Unknown" for s in enabled)
    return {
        "summary": {
            "total": len(sensors),
            "enforced": len(enabled),
            "not_enforced": len(disabled),
            "enforced_pct": _pct(len(enabled), len(sensors)),
        },
        "tables": [
            {
                "title": "Enforced agents by platform",
                "columns": [
                    {"key": "platform", "label": "Platform"},
                    {"key": "count", "label": "Count", "numeric": True},
                ],
                "rows": [
                    {"platform": name, "count": count} for name, count in platforms_enabled.most_common()
                ],
            },
            {
                "title": "Disabled agents (first 50)",
                "columns": [
                    {"key": "host_name", "label": "Hostname"},
                    {"key": "platform", "label": "Platform"},
                    {"key": "current_sw_version", "label": "Version"},
                    {"key": "workspace", "label": "Workspace"},
                    {"key": "ip", "label": "IP"},
                ],
                "rows": [
                    {
                        "host_name": s.get("host_name", "") or "",
                        "platform": s.get("platform", "") or "",
                        "current_sw_version": s.get("current_sw_version", "") or "",
                        "workspace": (mapping.get((s.get("host_name") or "").lower()) or {}).get("name", ""),
                        "ip": primary_ip(s),
                    }
                    for s in disabled[:50]
                ],
            },
        ],
    }


def _structured_agent_versions(ctx: QueryContext) -> dict[str, Any]:
    sensors, error = fetch_all_sensors(ctx.client)
    if error:
        return {"error": error}
    versions = Counter(s.get("current_sw_version") or "Unknown" for s in sensors)
    rows = [
        {
            "version": version,
            "count": count,
            "pct": _pct(count, len(sensors)),
        }
        for version, count in versions.most_common()
    ]
    mismatches = [
        {
            "host_name": s.get("host_name", ""),
            "current": s.get("current_sw_version", ""),
            "desired": s.get("desired_sw_version", ""),
        }
        for s in sensors
        if s.get("desired_sw_version") and s.get("desired_sw_version") != s.get("current_sw_version")
    ]
    return {
        "summary": {"total_agents": len(sensors), "pending_upgrade": len(mismatches)},
        "tables": [
            {
                "title": "Version distribution",
                "columns": [
                    {"key": "version", "label": "Version"},
                    {"key": "count", "label": "Count", "numeric": True},
                    {"key": "pct", "label": "%", "numeric": True},
                ],
                "rows": rows,
            },
            {
                "title": "Pending upgrades",
                "columns": [
                    {"key": "host_name", "label": "Hostname"},
                    {"key": "current", "label": "Current"},
                    {"key": "desired", "label": "Desired"},
                ],
                "rows": mismatches[:50],
            },
        ],
    }


# ── Stdout adapters ────────────────────────────────────────────────────────


@dataclass
class StdoutCapture:
    """Helper that captures generated CSV files in addition to stdout."""

    output_dir: Path
    files_before: set[str] = field(default_factory=set)

    def __enter__(self) -> StdoutCapture:
        self.files_before = {p.name for p in self.output_dir.glob("*.csv")}
        return self

    def __exit__(self, *exc_info: Any) -> None:
        return None

    def new_files(self) -> list[str]:
        return sorted({p.name for p in self.output_dir.glob("*.csv")} - self.files_before)


def _stdout_runner(
    label: str,
    runner: Callable[[QueryContext], None],
) -> Callable[..., dict[str, Any]]:
    """Wrap a CLI-style query function to capture stdout + new CSV files."""

    def adapter(ctx: QueryContext, **_: Any) -> dict[str, Any]:
        buffer = io.StringIO()
        capture = StdoutCapture(output_dir=Path.cwd())
        with capture, contextlib.redirect_stdout(buffer):
            try:
                runner(ctx)
                success = True
                err = None
            except Exception as exc:
                logger.exception("Query %s failed", label)
                success = False
                err = str(exc)
        return {
            "stdout": buffer.getvalue(),
            "files": capture.new_files(),
            "success": success,
            "error": err,
        }

    return adapter


def _stdout_with_args(
    runner: Callable[..., None],
) -> Callable[..., dict[str, Any]]:
    """Stdout runner whose function takes a single keyword input."""

    def adapter(ctx: QueryContext, **inputs: Any) -> dict[str, Any]:
        buffer = io.StringIO()
        capture = StdoutCapture(output_dir=Path.cwd())
        with capture, contextlib.redirect_stdout(buffer):
            try:
                runner(ctx, **inputs)
                success = True
                err = None
            except Exception as exc:
                success = False
                err = str(exc)
        return {
            "stdout": buffer.getvalue(),
            "files": capture.new_files(),
            "success": success,
            "error": err,
        }

    return adapter


# ── Web-friendly versions of input-driven queries ──────────────────────────


def _run_search_workspace(ctx: QueryContext, *, name: str) -> None:
    from csw_agent.tabulate_fallback import tabulate

    workspaces, error = fetch_workspaces(ctx.client)
    if error:
        print(f"Error: {error}")
        return
    matches = [w for w in workspaces if name.lower() in (w.get("name") or "").lower()]
    if not matches:
        print(f"No workspaces matching '{name}'")
        return
    rows = [
        [
            w.get("name", ""),
            "Yes" if w.get("analysis_enabled") else "No",
            "Yes" if w.get("enforcement_enabled") else "No",
            (w.get("id", "") or "")[:12] + "...",
        ]
        for w in matches[:30]
    ]
    print(f"Found {len(matches)} matching workspace(s):")
    print(tabulate(rows, headers=["Name", "Analysis", "Enforcement", "ID"], tablefmt="grid"))


def _run_search_inventory(ctx: QueryContext, *, search: str) -> None:
    import re

    from csw_agent.tabulate_fallback import tabulate

    if re.match(r"^\d+\.\d+\.\d+\.\d+", search):
        filter_q = (
            {"type": "subnet", "field": "ip", "value": search}
            if "/" in search
            else {"type": "eq", "field": "ip", "value": search}
        )
    else:
        filter_q = {"type": "contains", "field": "hostname", "value": search}
    body = {"filter": filter_q, "limit": 30}
    data, error = ctx.client.call("POST", "/inventory/search", json_body=body)
    if error:
        print(f"Error: {error}")
        return
    results = data.get("results", []) if isinstance(data, dict) else []
    if not results:
        print(f"No inventory items found for '{search}'")
        return
    rows = [[r.get("hostname", ""), r.get("ip", ""), r.get("os", ""), r.get("vrf_name", "")] for r in results]
    print(f"Found {len(results)} inventory item(s):")
    print(tabulate(rows, headers=["Hostname", "IP", "OS", "VRF"], tablefmt="grid"))


def _run_vulnerability_report(ctx: QueryContext, *, hostname: str) -> None:
    from csw_agent.csv_tools import write_csv
    from csw_agent.queries._helpers import timestamped_path

    sensors, error = fetch_all_sensors(ctx.client)
    if error:
        print(f"Error: {error}")
        return
    matches = [s for s in sensors if hostname.lower() in (s.get("host_name") or "").lower()]
    if not matches:
        print(f"Agent '{hostname}' not found among {len(sensors)} agents.")
        return
    if len(matches) > 1:
        names = ", ".join((m.get("host_name") or "")[:24] for m in matches[:5])
        print(f"Multiple matches ({len(matches)}); using first. Others: {names}")
    agent = matches[0]
    agent_uuid = agent.get("uuid", "")
    name = agent.get("host_name", "unknown")
    print(f"Agent: {name} (UUID: {agent_uuid})")

    data, vuln_error = ctx.client.call("GET", f"/workload/{agent_uuid}/vulnerabilities")
    if vuln_error:
        print(f"Error fetching vulnerabilities: {vuln_error}")
        return
    vulns = data if isinstance(data, list) else []
    if not vulns:
        print(f"No vulnerabilities found for {name}.")
        return
    print(f"Found {len(vulns)} vulnerabilities")
    counts = Counter(
        str(v.get("severity") or v.get("v3_severity") or v.get("v2_severity") or "Unknown") for v in vulns
    )
    for severity, count in sorted(counts.items()):
        print(f"  {severity}: {count}")

    columns = ["cve_id", "severity", "package_name", "package_version", "fixed_version"]
    rows = [{col: v.get(col, "") for col in columns} for v in vulns]
    filepath = timestamped_path(f"vulnerabilities_{name}")
    written = write_csv(filepath, columns, rows)
    print(f"Exported {written} rows to {filepath.name}")


# ── Catalog ────────────────────────────────────────────────────────────────


def _pct(part: int, whole: int) -> float:
    return round((part / whole) * 100, 1) if whole else 0.0


def build_web_catalog() -> list[WebQuery]:
    """Return the ordered list of web queries shown on the Queries page."""
    from csw_agent.queries import (
        agents,
        enforcement,
        inventory,
        workspaces,
    )

    return [
        WebQuery(
            key="agent_summary",
            label="Agent summary",
            description="Total agents, broken down by platform and agent type.",
            category="Agents",
            result_kind="structured",
            structured_fn=_structured_agent_summary,
        ),
        WebQuery(
            key="workspace_summary",
            label="Workspace summary",
            description="Counts of workspaces with analysis and enforcement enabled.",
            category="Workspaces",
            result_kind="structured",
            structured_fn=_structured_workspace_summary,
        ),
        WebQuery(
            key="enforcement_status",
            label="Enforcement status",
            description="Enforced vs. not-enforced agents, with workspace mapping.",
            category="Enforcement",
            result_kind="structured",
            structured_fn=_structured_enforcement_status,
        ),
        WebQuery(
            key="agent_versions",
            label="Agent versions",
            description="Software version distribution and pending upgrades.",
            category="Agents",
            result_kind="structured",
            structured_fn=_structured_agent_versions,
        ),
        WebQuery(
            key="scope_tree",
            label="Scope hierarchy",
            description="List of scopes with parent/child relationships.",
            category="Workspaces",
            result_kind="stdout",
            stdout_fn=_stdout_runner("scope_tree", workspaces.scope_tree),
        ),
        WebQuery(
            key="search_workspace",
            label="Search workspace by name",
            description="Find workspaces whose name contains the given text.",
            category="Workspaces",
            result_kind="stdout",
            inputs=(QueryInput("name", "Workspace name", placeholder="e.g. PROD"),),
            stdout_fn=_stdout_with_args(_run_search_workspace),
        ),
        WebQuery(
            key="search_inventory",
            label="Search inventory",
            description="Search inventory by hostname or IP.",
            category="Inventory",
            result_kind="stdout",
            inputs=(QueryInput("search", "Hostname or IP", placeholder="10.0.0.1 or web01"),),
            stdout_fn=_stdout_with_args(_run_search_inventory),
        ),
        WebQuery(
            key="list_vrfs",
            label="List VRFs",
            description="Configured VRFs with tenant info.",
            category="Inventory",
            result_kind="stdout",
            stdout_fn=_stdout_runner("list_vrfs", inventory.list_vrfs),
        ),
        WebQuery(
            key="service_health",
            label="Service health",
            description="CSW service status check.",
            category="Inventory",
            result_kind="stdout",
            stdout_fn=_stdout_runner("service_health", inventory.service_health),
        ),
        WebQuery(
            key="recent_agents",
            label="Recent agents (30d)",
            description="Agents created/deleted/uninstalled in the last 30 days.",
            category="Agents",
            result_kind="stdout",
            stdout_fn=_stdout_runner("recent_agents", agents.recent_agents),
        ),
        WebQuery(
            key="workspaces_by_scope",
            label="Workspaces by scope (CSV)",
            description="Export every workspace and its scope to CSV.",
            category="Workspaces",
            result_kind="stdout",
            stdout_fn=_stdout_runner("workspaces_by_scope", workspaces.workspaces_by_scope),
        ),
        WebQuery(
            key="enforcement_disabled_csv",
            label="Enforcement disabled (CSV)",
            description="Enforcement status overview + CSV export of disabled agents.",
            category="Enforcement",
            result_kind="stdout",
            stdout_fn=_stdout_runner("enforcement_status_csv", enforcement.enforcement_status),
        ),
        WebQuery(
            key="enf_in_workspace_csv",
            label="Enforced agents in workspaces (CSV)",
            description="Agents with enforcement enabled, with workspace status.",
            category="Enforcement",
            result_kind="stdout",
            stdout_fn=_stdout_runner("enf_in_workspace", enforcement.enf_in_workspace),
        ),
        WebQuery(
            key="no_enf_no_workspace_csv",
            label="Uncovered agents (CSV)",
            description="Agents without enforcement and not covered by an enforced workspace.",
            category="Enforcement",
            result_kind="stdout",
            stdout_fn=_stdout_runner("no_enf_no_workspace", enforcement.no_enf_no_workspace),
        ),
        WebQuery(
            key="no_enf_in_enf_workspace_csv",
            label="Gap: agents w/o enforcement in enforced workspace (CSV)",
            description="Agents without enforcement that ARE covered by an enforced workspace.",
            category="Enforcement",
            result_kind="stdout",
            stdout_fn=_stdout_runner("no_enf_in_enf_workspace", enforcement.no_enf_in_enf_workspace),
        ),
        WebQuery(
            key="vulnerability_report",
            label="Vulnerability report (CSV)",
            description="Export the vulnerability report for an agent.",
            category="Agents",
            result_kind="stdout",
            inputs=(QueryInput("hostname", "Agent hostname", placeholder="DCCIWA01"),),
            stdout_fn=_stdout_with_args(_run_vulnerability_report),
        ),
    ]


def execute_query(query: WebQuery, ctx: QueryContext, inputs: dict[str, Any]) -> dict[str, Any]:
    """Run ``query`` and return a JSON-serializable result envelope."""
    started = datetime.utcnow().isoformat() + "Z"
    if query.result_kind == "structured":
        if query.structured_fn is None:
            raise RuntimeError(f"Structured query {query.key!r} missing structured_fn")
        data = query.structured_fn(ctx)
        return {"started_at": started, "kind": "structured", "data": data}
    if query.stdout_fn is None:
        raise RuntimeError(f"Stdout query {query.key!r} missing stdout_fn")
    data = query.stdout_fn(ctx, **inputs)
    return {"started_at": started, "kind": "stdout", "data": data}
