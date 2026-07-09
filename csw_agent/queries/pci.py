"""Deterministic PCI-DSS v4.0.1 readiness assessment built from CSW evidence.

Maps live Cisco Secure Workload data to a verifiable subset of PCI-DSS
requirements (1, 6/11.3, 7, 10, 11.4.4). The engine is deliberately
deterministic — same inputs, same score — so its output can be attached as
audit evidence. Any AI narrative is generated *from* this output, never the
other way around.

This is a readiness view, not an official assessment (which requires a QSA).
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from csw_agent.csv_tools import write_csv
from csw_agent.queries import QueryContext
from csw_agent.queries._helpers import (
    fetch_all_sensors,
    fetch_scopes,
    fetch_workspaces,
    timestamped_path,
)

logger = logging.getLogger(__name__)

CheckStatus = Literal["pass", "warn", "fail"]

# Engine bounds so a huge scope cannot stall the dashboard.
MAX_INVENTORY_PAGES = 50
MAX_VULN_AGENTS = 200
CHECKIN_FRESH_SECONDS = 24 * 3600
CRITICAL_CVSS_THRESHOLD = 7.0
TABLE_ROW_LIMIT = 50


@dataclass(frozen=True)
class PciCheck:
    """A single evidence-backed check inside a requirement."""

    title: str
    status: CheckStatus
    detail: str

    def to_dict(self) -> dict[str, Any]:
        return {"title": self.title, "status": self.status, "detail": self.detail}


@dataclass(frozen=True)
class RequirementScore:
    """Scored result for one PCI-DSS requirement."""

    req_id: str
    title: str
    points: float
    max_points: float
    checks: tuple[PciCheck, ...]

    @property
    def status(self) -> CheckStatus:
        ratio = self.points / self.max_points if self.max_points else 0.0
        if ratio >= 0.85:
            return "pass"
        if ratio >= 0.4:
            return "warn"
        return "fail"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.req_id,
            "title": self.title,
            "status": self.status,
            "points": round(self.points, 1),
            "max_points": self.max_points,
            "checks": [c.to_dict() for c in self.checks],
        }


@dataclass
class PciAssessment:
    """Full assessment result for one scope."""

    scope_name: str
    requirements: list[RequirementScore]
    workspaces: list[dict[str, Any]]
    critical_cves: list[dict[str, Any]]
    no_agent: list[dict[str, Any]]
    workloads_total: int
    workloads_with_agent: int
    evidence_file: str | None = None
    generated_at: float = field(default_factory=time.time)

    @property
    def score(self) -> float:
        return round(sum(r.points for r in self.requirements), 1)

    @property
    def level(self) -> tuple[str, CheckStatus]:
        if self.score >= 85:
            return "Compliant posture", "pass"
        if self.score >= 60:
            return "Partial — action required", "warn"
        return "Non-compliant signals", "fail"

    def to_dict(self) -> dict[str, Any]:
        label, tone = self.level
        coverage = (
            round(100 * self.workloads_with_agent / self.workloads_total, 1) if self.workloads_total else 0.0
        )
        return {
            "scope_name": self.scope_name,
            "generated_at": datetime.fromtimestamp(self.generated_at, tz=timezone.utc).isoformat(),
            "score": self.score,
            "max_score": 100,
            "level": {"label": label, "tone": tone},
            "kpis": {
                "workloads_total": self.workloads_total,
                "workloads_with_agent": self.workloads_with_agent,
                "coverage_pct": coverage,
                "critical_cves": len(self.critical_cves),
                "cve_hosts": len({c["host"] for c in self.critical_cves}),
                "workspaces_total": len(self.workspaces),
                "workspaces_enforced": sum(1 for w in self.workspaces if w["enforcement_enabled"]),
            },
            "requirements": [r.to_dict() for r in self.requirements],
            "tables": {
                "workspaces": self.workspaces[:TABLE_ROW_LIMIT],
                "critical_cves": self.critical_cves[:TABLE_ROW_LIMIT],
                "no_agent": self.no_agent[:TABLE_ROW_LIMIT],
            },
            "evidence_file": self.evidence_file,
        }


# ── Data gathering ──────────────────────────────────────────────────────────


@dataclass
class _Evidence:
    """Raw evidence collected from CSW before scoring."""

    scope_name: str
    workspaces: list[dict[str, Any]] = field(default_factory=list)
    inventory_total: int = 0
    matched_agents: list[dict[str, Any]] = field(default_factory=list)
    no_agent: list[dict[str, Any]] = field(default_factory=list)
    critical_cves: list[dict[str, Any]] = field(default_factory=list)
    vuln_scanned: int = 0


def _descendant_scope_ids(scopes: list[dict[str, Any]], root_id: str) -> set[str]:
    """Return the root scope id plus every descendant id (BFS on child ids)."""
    by_id = {s.get("id"): s for s in scopes}
    ids: set[str] = set()
    queue = [root_id]
    while queue:
        current = queue.pop()
        if current in ids or current not in by_id:
            continue
        ids.add(current)
        queue.extend(by_id[current].get("child_app_scope_ids") or [])
    return ids


def _workspace_evidence(ctx: QueryContext, workspace: dict[str, Any]) -> dict[str, Any]:
    """Fetch policies for one workspace and derive the fields the checks need."""
    data, error = ctx.client.call("GET", f"/applications/{workspace.get('id')}/policies")
    policies: list[dict[str, Any]] = []
    catch_all = ""
    if not error and isinstance(data, dict):
        policies = list(data.get("absolute_policies") or []) + list(data.get("default_policies") or [])
        catch_all = str(data.get("catch_all_action") or "")
    explicit = sum(1 for p in policies if _has_explicit_l4(p))
    any_allow = sum(
        1 for p in policies if str(p.get("action", "")).upper() == "ALLOW" and not _has_explicit_l4(p)
    )
    deny = sum(1 for p in policies if str(p.get("action", "")).upper() == "DENY")
    return {
        "name": workspace.get("name", ""),
        "enforcement_enabled": bool(workspace.get("enforcement_enabled")),
        "catch_all": catch_all,
        "policy_count": len(policies),
        "deny_count": deny,
        "explicit_l4_count": explicit,
        "any_allow_count": any_allow,
        "analysis_enabled": bool(workspace.get("analysis_enabled")),
        "analyzed_version": int(workspace.get("analyzed_version") or 0),
        "enforced_version": int(workspace.get("enforced_version") or 0),
        "status": _workspace_status(workspace, catch_all),
    }


def _workspace_status(workspace: dict[str, Any], catch_all: str) -> CheckStatus:
    if not workspace.get("enforcement_enabled"):
        return "fail"
    if catch_all.upper() != "DENY":
        return "warn"
    return "pass"


def _has_explicit_l4(policy: dict[str, Any]) -> bool:
    """True when the policy pins at least one concrete protocol (not ANY)."""
    l4_params = policy.get("l4_params") or []
    return any(param.get("proto") not in (None, -1) for param in l4_params)


def _fetch_scope_inventory(ctx: QueryContext, scope_name: str) -> list[dict[str, Any]]:
    """Paginate POST /inventory/search for the scope (bounded)."""
    items: list[dict[str, Any]] = []
    offset: Any = None
    for _ in range(MAX_INVENTORY_PAGES):
        body: dict[str, Any] = {"scopeName": scope_name, "limit": 100}
        if offset:
            body["offset"] = offset
        data, error = ctx.client.call("POST", "/inventory/search", json_body=body)
        if error or not isinstance(data, dict):
            break
        items.extend(data.get("results") or [])
        offset = data.get("offset")
        if not offset:
            break
    return items


def _match_agents(
    inventory: list[dict[str, Any]], sensors: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split inventory into (matched agents, items without agent)."""
    by_host: dict[str, dict[str, Any]] = {}
    by_ip: dict[str, dict[str, Any]] = {}
    for sensor in sensors:
        host = (sensor.get("host_name") or "").lower()
        if host:
            by_host.setdefault(host, sensor)
        for iface in sensor.get("interfaces") or []:
            if isinstance(iface, dict) and iface.get("ip"):
                by_ip.setdefault(iface["ip"], sensor)
        if sensor.get("client_ip"):
            by_ip.setdefault(sensor["client_ip"], sensor)

    matched: dict[str, dict[str, Any]] = {}
    missing: list[dict[str, Any]] = []
    for item in inventory:
        host = (item.get("host_name") or item.get("hostname") or "").lower()
        agent = by_host.get(host) or by_ip.get(item.get("ip", ""))
        if agent is not None:
            matched.setdefault(agent.get("uuid", host), agent)
        else:
            missing.append(
                {
                    "host": item.get("host_name") or item.get("hostname") or "(unknown)",
                    "ip": item.get("ip", ""),
                    "os": item.get("os", ""),
                    "vrf": item.get("vrf_name", ""),
                }
            )
    return list(matched.values()), missing


def _cvss_score(vuln: dict[str, Any]) -> float:
    for key in ("cvss_v3", "v3_score", "cvss_v2", "v2_score"):
        raw = vuln.get(key)
        if raw is None:
            continue
        try:
            return float(raw)
        except (TypeError, ValueError):
            continue
    return 0.0


def _fetch_critical_cves(ctx: QueryContext, agents: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Collect CVEs with CVSS >= threshold across agents. Returns (rows, scanned)."""

    def fetch_one(agent: dict[str, Any]) -> list[dict[str, Any]]:
        uuid = agent.get("uuid", "")
        data, error = ctx.client.call("GET", f"/workload/{uuid}/vulnerabilities")
        if error or not isinstance(data, list):
            raise RuntimeError(error or "unexpected response")
        host = agent.get("host_name", "")
        return [
            {
                "host": host,
                "cve_id": v.get("cve_id", ""),
                "cvss": _cvss_score(v),
                "severity": "Critical" if _cvss_score(v) >= 9.0 else "High",
                "package": v.get("package_name", ""),
                "fixed_version": v.get("fixed_version", ""),
            }
            for v in data
            if _cvss_score(v) >= CRITICAL_CVSS_THRESHOLD
        ]

    rows: list[dict[str, Any]] = []
    scanned = 0
    subset = agents[:MAX_VULN_AGENTS]
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(fetch_one, agent) for agent in subset]
        for future in as_completed(futures):
            try:
                rows.extend(future.result())
                scanned += 1
            except Exception as exc:
                logger.debug("Vulnerability fetch failed: %s", exc)
    rows.sort(key=lambda r: r["cvss"], reverse=True)
    return rows, scanned


def _gather(ctx: QueryContext, scope_name: str) -> _Evidence:
    scopes, error = fetch_scopes(ctx.client)
    if error:
        raise RuntimeError(f"Could not list scopes: {error}")
    scope = next((s for s in scopes if s.get("name") == scope_name), None)
    if scope is None:
        raise ValueError(f"Scope not found: {scope_name}")

    scope_ids = _descendant_scope_ids(scopes, scope.get("id", ""))
    workspaces, ws_error = fetch_workspaces(ctx.client)
    if ws_error:
        raise RuntimeError(f"Could not list workspaces: {ws_error}")
    in_scope = [w for w in workspaces if w.get("app_scope_id") in scope_ids]

    evidence = _Evidence(scope_name=scope_name)
    evidence.workspaces = [_workspace_evidence(ctx, w) for w in in_scope]

    inventory = _fetch_scope_inventory(ctx, scope_name)
    evidence.inventory_total = len(inventory)
    sensors, sensor_error = fetch_all_sensors(ctx.client)
    if sensor_error:
        logger.warning("Sensor fetch incomplete: %s", sensor_error)
    evidence.matched_agents, evidence.no_agent = _match_agents(inventory, sensors)
    evidence.critical_cves, evidence.vuln_scanned = _fetch_critical_cves(ctx, evidence.matched_agents)
    return evidence


# ── Scoring ─────────────────────────────────────────────────────────────────


def _ratio_check(
    title: str,
    part: int,
    whole: int,
    max_points: float,
    *,
    pass_at: float = 0.9,
    warn_at: float = 0.5,
    detail: str | None = None,
) -> tuple[PciCheck, float]:
    """Score ``part/whole`` linearly against ``max_points`` with status bands."""
    if whole <= 0:
        return PciCheck(title, "fail", detail or "no data in scope"), 0.0
    ratio = part / whole
    status: CheckStatus = "pass" if ratio >= pass_at else ("warn" if ratio >= warn_at else "fail")
    return PciCheck(title, status, detail or f"{part}/{whole}"), max_points * ratio


def _score_req1(ev: _Evidence) -> RequirementScore:
    total = len(ev.workspaces)
    enforced = sum(1 for w in ev.workspaces if w["enforcement_enabled"])
    deny = sum(1 for w in ev.workspaces if w["catch_all"].upper() == "DENY")
    with_policies = sum(1 for w in ev.workspaces if w["policy_count"] >= 10)
    c1, p1 = _ratio_check("Enforcement enabled", enforced, total, 10)
    c2, p2 = _ratio_check("Catch-all action = DENY", deny, total, 10)
    c3, p3 = _ratio_check("≥ 10 policies defined", with_policies, total, 5)
    return RequirementScore("Req 1", "Network security controls", p1 + p2 + p3, 25, (c1, c2, c3))


def _score_req6(ev: _Evidence) -> RequirementScore:
    if not ev.matched_agents:
        no_data = PciCheck("No critical CVEs (CVSS ≥ 7)", "fail", "no agent data in scope")
        checks = (
            no_data,
            PciCheck("Fix available for open criticals", "fail", "no agent data in scope"),
            PciCheck("Vulnerability scan coverage", "fail", "no agent data in scope"),
        )
        return RequirementScore("Req 6 · 11.3", "Vulnerability management", 0.0, 20, checks)
    criticals = len(ev.critical_cves)
    hosts = len({c["host"] for c in ev.critical_cves})
    if criticals == 0:
        c1 = PciCheck("No critical CVEs (CVSS ≥ 7)", "pass", "0 found")
        p1 = 12.0
    elif criticals <= 3:
        c1 = PciCheck("No critical CVEs (CVSS ≥ 7)", "warn", f"{criticals} found on {hosts} hosts")
        p1 = 6.0
    else:
        c1 = PciCheck("No critical CVEs (CVSS ≥ 7)", "fail", f"{criticals} found on {hosts} hosts")
        p1 = 0.0
    fixable = sum(1 for c in ev.critical_cves if c["fixed_version"])
    if criticals == 0:
        c2, p2 = PciCheck("Fix available for open criticals", "pass", "nothing open"), 4.0
    else:
        c2, p2 = _ratio_check(
            "Fix available for open criticals",
            fixable,
            criticals,
            4,
            detail=f"{fixable}/{criticals} CVEs have a fix version",
        )
        c2 = PciCheck(c2.title, "warn" if fixable else "fail", c2.detail)
    c3, p3 = _ratio_check(
        "Vulnerability scan coverage",
        ev.vuln_scanned,
        min(len(ev.matched_agents), MAX_VULN_AGENTS),
        4,
        detail=f"{ev.vuln_scanned} agents reported CVE data",
    )
    return RequirementScore("Req 6 · 11.3", "Vulnerability management", p1 + p2 + p3, 20, (c1, c2, c3))


def _score_req7(ev: _Evidence) -> RequirementScore:
    policies = sum(w["policy_count"] for w in ev.workspaces)
    if policies == 0:
        checks = tuple(
            PciCheck(title, "fail", "no policies in scope")
            for title in (
                "Protocol/port specificity",
                "DENY rules present",
                "No any-protocol ALLOW rules",
            )
        )
        return RequirementScore("Req 7", "Need-to-know access", 0.0, 20, checks)
    explicit = sum(w["explicit_l4_count"] for w in ev.workspaces)
    deny_rules = sum(w["deny_count"] for w in ev.workspaces)
    any_allow = sum(w["any_allow_count"] for w in ev.workspaces)
    c1, p1 = _ratio_check(
        "Protocol/port specificity",
        explicit,
        policies,
        10,
        pass_at=0.7,
        warn_at=0.4,
        detail=f"{explicit}/{policies} policies pin a protocol",
    )
    if deny_rules:
        c2, p2 = PciCheck("DENY rules present", "pass", f"{deny_rules} DENY policies"), 5.0
    else:
        c2, p2 = PciCheck("DENY rules present", "fail", "no DENY policies"), 0.0
    if any_allow == 0:
        c3, p3 = PciCheck("No any-protocol ALLOW rules", "pass", "none found"), 5.0
    elif any_allow <= 2:
        c3, p3 = PciCheck("No any-protocol ALLOW rules", "warn", f"{any_allow} found"), 2.5
    else:
        c3, p3 = PciCheck("No any-protocol ALLOW rules", "fail", f"{any_allow} found"), 0.0
    return RequirementScore("Req 7", "Need-to-know access", p1 + p2 + p3, 20, (c1, c2, c3))


def _score_req10(ev: _Evidence) -> RequirementScore:
    matched = len(ev.matched_agents)
    c1, p1 = _ratio_check(
        "Agent coverage",
        matched,
        ev.inventory_total,
        10,
        pass_at=0.95,
        warn_at=0.85,
        detail=f"{matched}/{ev.inventory_total} workloads · target ≥ 95%",
    )
    now = time.time()
    fresh = sum(
        1 for a in ev.matched_agents if (a.get("last_config_fetch_at") or 0) >= now - CHECKIN_FRESH_SECONDS
    )
    c2, p2 = _ratio_check("Agent check-in < 24 h", fresh, matched, 5, pass_at=0.95, warn_at=0.85)
    telemetry = sum(1 for a in ev.matched_agents if not a.get("data_plane_disabled"))
    c3, p3 = _ratio_check("Flow telemetry enabled", telemetry, matched, 5, pass_at=0.95, warn_at=0.85)
    return RequirementScore("Req 10", "Monitoring & logging", p1 + p2 + p3, 20, (c1, c2, c3))


def _score_req11(ev: _Evidence) -> RequirementScore:
    total = len(ev.workspaces)
    analysis = sum(1 for w in ev.workspaces if w["analysis_enabled"])
    analyzed = sum(1 for w in ev.workspaces if w["analyzed_version"] > 0)
    enforced_current = sum(1 for w in ev.workspaces if w["enforcement_enabled"] and w["enforced_version"] > 0)
    c1, p1 = _ratio_check("Policy analysis enabled", analysis, total, 5)
    c2, p2 = _ratio_check("Analyzed version present", analyzed, total, 5)
    c3, p3 = _ratio_check("Enforced version current", enforced_current, total, 5)
    return RequirementScore("Req 11.4.4", "Segmentation verification", p1 + p2 + p3, 15, (c1, c2, c3))


# ── Evidence export ─────────────────────────────────────────────────────────

_EVIDENCE_COLUMNS = [
    "record_type",
    "name",
    "host",
    "ip",
    "os",
    "vrf",
    "enforcement_enabled",
    "catch_all",
    "policy_count",
    "analyzed_version",
    "enforced_version",
    "cve_id",
    "severity",
    "cvss",
    "package",
    "fixed_version",
]


def _write_evidence(assessment: PciAssessment) -> str | None:
    rows: list[dict[str, Any]] = []
    for w in assessment.workspaces:
        rows.append({"record_type": "workspace", **w})
    for c in assessment.critical_cves:
        rows.append({"record_type": "critical_cve", **c})
    for n in assessment.no_agent:
        rows.append({"record_type": "workload_no_agent", **n})
    if not rows:
        return None
    filepath = timestamped_path("pci_evidence")
    try:
        write_csv(filepath, _EVIDENCE_COLUMNS, rows)
    except OSError as exc:
        logger.warning("Could not write evidence CSV: %s", exc)
        return None
    return filepath.name


# ── Public entry point ──────────────────────────────────────────────────────


def assess_scope(ctx: QueryContext, scope_name: str) -> PciAssessment:
    """Run the full deterministic assessment for ``scope_name``.

    Raises ``ValueError`` if the scope does not exist and ``RuntimeError`` when
    the CSW API cannot provide the base evidence.
    """
    evidence = _gather(ctx, scope_name)
    requirements = [
        _score_req1(evidence),
        _score_req6(evidence),
        _score_req7(evidence),
        _score_req10(evidence),
        _score_req11(evidence),
    ]
    assessment = PciAssessment(
        scope_name=scope_name,
        requirements=requirements,
        workspaces=evidence.workspaces,
        critical_cves=evidence.critical_cves,
        no_agent=evidence.no_agent,
        workloads_total=evidence.inventory_total,
        workloads_with_agent=len(evidence.matched_agents),
    )
    assessment.evidence_file = _write_evidence(assessment)
    if assessment.evidence_file:
        ctx.last_generated_csv = Path.cwd() / assessment.evidence_file
    return assessment
