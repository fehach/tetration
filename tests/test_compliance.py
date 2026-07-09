"""Tests for the deterministic PCI-DSS assessment engine and its API."""

from __future__ import annotations

import pytest

from csw_agent.queries import QueryContext
from csw_agent.queries.pci import (
    PciCheck,
    RequirementScore,
    _has_explicit_l4,
    _match_agents,
    _ratio_check,
    assess_scope,
)
from tests.conftest import FakeResponse

# ── Fixture data ────────────────────────────────────────────────────────────

SCOPES = [
    {"id": "sc-root", "name": "MyOrg", "child_app_scope_ids": ["sc-cde"]},
    {"id": "sc-cde", "name": "MyOrg:PCI-CDE", "child_app_scope_ids": []},
    {"id": "sc-other", "name": "MyOrg:OTHER", "child_app_scope_ids": []},
]

WORKSPACES = [
    {
        "id": "ws-1",
        "name": "CDE-Payments",
        "app_scope_id": "sc-cde",
        "enforcement_enabled": True,
        "analysis_enabled": True,
        "analyzed_version": 4,
        "enforced_version": 3,
    },
    {
        "id": "ws-2",
        "name": "CDE-Reporting",
        "app_scope_id": "sc-cde",
        "enforcement_enabled": False,
        "analysis_enabled": False,
        "analyzed_version": 0,
        "enforced_version": 0,
    },
    {
        "id": "ws-out",
        "name": "Unrelated",
        "app_scope_id": "sc-other",
        "enforcement_enabled": False,
        "analysis_enabled": False,
        "analyzed_version": 0,
        "enforced_version": 0,
    },
]

POLICIES_WS1 = {
    "catch_all_action": "DENY",
    "absolute_policies": [
        {"action": "ALLOW", "l4_params": [{"proto": 6, "port": [443, 443]}]} for _ in range(8)
    ],
    "default_policies": [
        {"action": "DENY", "l4_params": [{"proto": 6, "port": [22, 22]}]},
        {"action": "ALLOW", "l4_params": []},  # any-protocol allow
        {"action": "ALLOW", "l4_params": [{"proto": 17, "port": [53, 53]}]},
    ],
}

POLICIES_WS2 = {"catch_all_action": "ALLOW", "absolute_policies": [], "default_policies": []}

INVENTORY = [
    {"host_name": "cde-web-01", "ip": "10.0.0.1", "os": "Ubuntu", "vrf_name": "PROD"},
    {"host_name": "cde-db-01", "ip": "10.0.0.2", "os": "RHEL", "vrf_name": "PROD"},
    {"host_name": "cde-orphan", "ip": "10.0.0.9", "os": "Windows", "vrf_name": "PROD"},
]

NOW_MS_FRESH = 32_000_000_000  # far future epoch so check-in is always fresh in tests

SENSORS = {
    "results": [
        {
            "uuid": "agent-1",
            "host_name": "cde-web-01",
            "client_ip": "10.0.0.1",
            "interfaces": [{"ip": "10.0.0.1"}],
            "last_config_fetch_at": NOW_MS_FRESH,
            "data_plane_disabled": False,
        },
        {
            "uuid": "agent-2",
            "host_name": "cde-db-01",
            "client_ip": "10.0.0.2",
            "interfaces": [{"ip": "10.0.0.2"}],
            "last_config_fetch_at": NOW_MS_FRESH,
            "data_plane_disabled": False,
        },
    ]
}

VULNS_AGENT1 = [
    {"cve_id": "CVE-2025-0001", "cvss_v3": 9.8, "package_name": "openssl", "fixed_version": "3.0.9"},
    {"cve_id": "CVE-2025-0002", "cvss_v3": 5.0, "package_name": "vim", "fixed_version": "9.1"},
]


def _register_scope_endpoints(fake_rest, tmp_path) -> None:
    fake_rest.register("GET", "/app_scopes", lambda **_: FakeResponse(200, SCOPES))
    fake_rest.register("GET", "/applications", lambda **_: FakeResponse(200, WORKSPACES))
    fake_rest.register("GET", "/applications/ws-1/policies", lambda **_: FakeResponse(200, POLICIES_WS1))
    fake_rest.register("GET", "/applications/ws-2/policies", lambda **_: FakeResponse(200, POLICIES_WS2))
    fake_rest.register("POST", "/inventory/search", lambda **_: FakeResponse(200, {"results": INVENTORY}))
    fake_rest.register("GET", "/sensors", lambda **_: FakeResponse(200, SENSORS))
    fake_rest.register(
        "GET", "/workload/agent-1/vulnerabilities", lambda **_: FakeResponse(200, VULNS_AGENT1)
    )
    fake_rest.register("GET", "/workload/agent-2/vulnerabilities", lambda **_: FakeResponse(200, []))


@pytest.fixture
def ctx(csw_client, fake_rest, tmp_path, monkeypatch) -> QueryContext:
    from csw_agent.config import Settings

    monkeypatch.chdir(tmp_path)  # evidence CSV lands in tmp
    _register_scope_endpoints(fake_rest, tmp_path)
    return QueryContext(client=csw_client, settings=Settings(credentials_file=tmp_path / "c.json"))


# ── Engine tests ────────────────────────────────────────────────────────────


def test_assess_scope_unknown_scope_raises(ctx):
    with pytest.raises(ValueError, match="Scope not found"):
        assess_scope(ctx, "NOPE")


def test_assess_scope_scores_and_tables(ctx):
    assessment = assess_scope(ctx, "MyOrg:PCI-CDE")

    assert assessment.scope_name == "MyOrg:PCI-CDE"
    assert 0 < assessment.score < 100
    # Only the two in-scope workspaces are assessed.
    assert {w["name"] for w in assessment.workspaces} == {"CDE-Payments", "CDE-Reporting"}
    # One critical CVE (9.8); the 5.0 CVE is filtered out.
    assert [c["cve_id"] for c in assessment.critical_cves] == ["CVE-2025-0001"]
    assert assessment.critical_cves[0]["severity"] == "Critical"
    # cde-orphan has no matching agent.
    assert [n["host"] for n in assessment.no_agent] == ["cde-orphan"]
    assert assessment.workloads_total == 3
    assert assessment.workloads_with_agent == 2


def test_assess_scope_requirement_breakdown(ctx):
    assessment = assess_scope(ctx, "MyOrg:PCI-CDE")
    by_id = {r.req_id: r for r in assessment.requirements}

    assert set(by_id) == {"Req 1", "Req 6 · 11.3", "Req 7", "Req 10", "Req 11.4.4"}
    assert sum(r.max_points for r in assessment.requirements) == 100
    # Req 1: 1/2 enforced, 1/2 DENY catch-all, 1/2 with >=10 policies -> half points.
    assert by_id["Req 1"].points == pytest.approx(12.5)
    # Req 7 sees 10 explicit of 11 policies, 1 deny, 1 any-allow.
    req7 = by_id["Req 7"]
    assert req7.checks[2].status == "warn"  # 1 any-protocol ALLOW


def test_assess_scope_writes_evidence_csv(ctx, tmp_path):
    assessment = assess_scope(ctx, "MyOrg:PCI-CDE")
    assert assessment.evidence_file is not None
    content = (tmp_path / assessment.evidence_file).read_text()
    assert "workspace" in content
    assert "critical_cve" in content
    assert "workload_no_agent" in content
    assert ctx.last_generated_csv is not None


def test_to_dict_shape(ctx):
    payload = assess_scope(ctx, "MyOrg:PCI-CDE").to_dict()
    assert payload["max_score"] == 100
    assert payload["level"]["tone"] in ("pass", "warn", "fail")
    assert payload["kpis"]["workloads_total"] == 3
    assert payload["kpis"]["coverage_pct"] == pytest.approx(66.7)
    assert len(payload["requirements"]) == 5
    assert set(payload["tables"]) == {"workspaces", "critical_cves", "no_agent"}
    for requirement in payload["requirements"]:
        assert {"id", "title", "status", "points", "max_points", "checks"} <= set(requirement)


def test_empty_scope_fails_gracefully(ctx, fake_rest):
    fake_rest.register("GET", "/applications", lambda **_: FakeResponse(200, []))
    fake_rest.register("POST", "/inventory/search", lambda **_: FakeResponse(200, {"results": []}))
    assessment = assess_scope(ctx, "MyOrg:PCI-CDE")
    assert assessment.score == 0.0
    assert assessment.level[1] == "fail"
    assert all(check.status == "fail" for r in assessment.requirements for check in r.checks)


# ── Unit tests for helpers ──────────────────────────────────────────────────


def test_ratio_check_zero_denominator():
    check, points = _ratio_check("x", 1, 0, 10)
    assert check.status == "fail"
    assert points == 0.0


def test_ratio_check_bands():
    assert _ratio_check("x", 95, 100, 10)[0].status == "pass"
    assert _ratio_check("x", 60, 100, 10)[0].status == "warn"
    assert _ratio_check("x", 10, 100, 10)[0].status == "fail"
    assert _ratio_check("x", 5, 10, 10)[1] == pytest.approx(5.0)


def test_has_explicit_l4():
    assert _has_explicit_l4({"l4_params": [{"proto": 6}]})
    assert not _has_explicit_l4({"l4_params": [{"proto": -1}]})
    assert not _has_explicit_l4({"l4_params": []})
    assert not _has_explicit_l4({})


def test_match_agents_by_ip_fallback():
    inventory = [{"host_name": "renamed-host", "ip": "10.1.1.1"}]
    sensors = [{"uuid": "a1", "host_name": "old-name", "client_ip": "10.1.1.1", "interfaces": []}]
    matched, missing = _match_agents(inventory, sensors)
    assert len(matched) == 1
    assert missing == []


def test_requirement_status_bands():
    checks = (PciCheck("c", "pass", "d"),)
    assert RequirementScore("R", "t", 22, 25, checks).status == "pass"
    assert RequirementScore("R", "t", 12, 25, checks).status == "warn"
    assert RequirementScore("R", "t", 2, 25, checks).status == "fail"
    assert RequirementScore("R", "t", 0, 0, checks).status == "fail"


# ── API tests ───────────────────────────────────────────────────────────────


@pytest.fixture
def offline_api(tmp_path):
    from fastapi.testclient import TestClient

    from csw_agent.config import Settings
    from csw_agent.dashboard.app import create_app
    from csw_agent.dashboard.state import DashboardState

    creds = tmp_path / "creds.json"
    creds.write_text("{}")
    settings = Settings(credentials_file=creds)
    state = DashboardState(settings=settings, client=None)
    return TestClient(create_app(settings, state=state))


@pytest.fixture
def live_api(csw_client, fake_rest, tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from csw_agent.config import Settings
    from csw_agent.dashboard.app import create_app
    from csw_agent.dashboard.state import DashboardState

    monkeypatch.chdir(tmp_path)  # evidence CSV lands in tmp
    _register_scope_endpoints(fake_rest, tmp_path)
    creds = tmp_path / "creds.json"
    creds.write_text("{}")
    settings = Settings(credentials_file=creds)
    state = DashboardState(settings=settings, client=csw_client)
    return TestClient(create_app(settings, state=state))


def test_scopes_offline_returns_503(offline_api):
    assert offline_api.get("/api/compliance/scopes").status_code == 503


def test_assess_offline_returns_503(offline_api):
    resp = offline_api.post("/api/compliance/assess", json={"scope_name": "X"})
    assert resp.status_code == 503


def test_scopes_lists_and_suggests(live_api):
    body = live_api.get("/api/compliance/scopes").json()
    names = [s["name"] for s in body]
    assert set(names) == {"MyOrg", "MyOrg:PCI-CDE", "MyOrg:OTHER"}
    # Suggested scopes (name contains pci/cde) sort first.
    assert body[0]["name"] == "MyOrg:PCI-CDE"
    assert body[0]["suggested"] is True


def test_assess_blank_scope_returns_422(live_api):
    resp = live_api.post("/api/compliance/assess", json={"scope_name": "   "})
    assert resp.status_code == 422


def test_assess_unknown_scope_returns_404(live_api):
    resp = live_api.post("/api/compliance/assess", json={"scope_name": "NOPE"})
    assert resp.status_code == 404


def test_summary_empty_assessment_returns_422(offline_api):
    resp = offline_api.post("/api/compliance/summary", json={"assessment": {}})
    assert resp.status_code == 422


def test_summary_prompt_embeds_assessment():
    from csw_agent.dashboard.compliance_api import build_summary_prompt

    prompt = build_summary_prompt({"scope_name": "MyOrg:PCI-CDE", "score": 72.0})
    assert "MyOrg:PCI-CDE" in prompt
    assert "{assessment}" not in prompt
    assert "readiness" in prompt.lower()


def test_summary_streams_error_when_claude_unreachable(offline_api, monkeypatch):
    # Force the anthropic import inside stream_summary to fail so the endpoint
    # degrades to an SSE error frame instead of hanging on a network call.
    import builtins

    real_import = builtins.__import__

    def failing_import(name, *args, **kwargs):
        if name == "anthropic":
            raise ImportError("anthropic not available")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", failing_import)
    with offline_api.stream("POST", "/api/compliance/summary", json={"assessment": {"score": 1}}) as resp:
        assert resp.status_code == 200
        body = b"".join(resp.iter_bytes()).decode()
    assert '"type": "error"' in body
    assert '"type": "done"' in body


def test_assess_returns_full_payload(live_api):
    resp = live_api.post("/api/compliance/assess", json={"scope_name": "MyOrg:PCI-CDE"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["scope_name"] == "MyOrg:PCI-CDE"
    assert len(body["requirements"]) == 5
    assert body["kpis"]["critical_cves"] == 1
    assert body["evidence_file"] is not None
    # The evidence CSV is downloadable through the existing files route.
    download = live_api.get(f"/api/files/{body['evidence_file']}")
    assert download.status_code == 200
    assert download.headers["content-type"].startswith("text/csv")
