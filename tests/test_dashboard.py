"""Tests for the dashboard FastAPI app."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from csw_agent.config import Settings
from csw_agent.dashboard.app import create_app
from csw_agent.dashboard.prompt_history import reset_for_tests as reset_history
from csw_agent.dashboard.queries_api import build_web_catalog
from csw_agent.dashboard.state import DashboardState
from csw_agent.telemetry import reset_for_tests
from tests.conftest import FakeResponse


@pytest.fixture(autouse=True)
def _reset_state(tmp_path_factory):
    reset_for_tests()
    reset_history(tmp_path_factory.mktemp("prompt-history") / "history.jsonl")
    yield
    reset_for_tests()
    reset_history(tmp_path_factory.mktemp("prompt-history") / "history.jsonl")


@pytest.fixture
def offline_state(tmp_path) -> DashboardState:
    creds = tmp_path / "creds.json"
    creds.write_text("{}")
    settings = Settings(credentials_file=creds)
    return DashboardState(settings=settings, client=None)


@pytest.fixture
def offline_client(offline_state: DashboardState) -> TestClient:
    app = create_app(offline_state.settings, state=offline_state)
    return TestClient(app)


@pytest.fixture
def live_state(tmp_path, fake_rest, monkeypatch) -> DashboardState:
    """Build a state with an injected CSW client backed by FakeRest."""
    from csw_agent.client import CSWClient

    creds = tmp_path / "creds.json"
    creds.write_text("{}")
    settings = Settings(credentials_file=creds)
    fake_module = MagicMock()
    fake_module.RestClient = MagicMock(return_value=fake_rest)
    monkeypatch.setitem(__import__("sys").modules, "tetpyclient", fake_module)
    client = CSWClient(settings)
    return DashboardState(settings=settings, client=client)


@pytest.fixture
def live_client(live_state: DashboardState) -> TestClient:
    app = create_app(live_state.settings, state=live_state)
    return TestClient(app)


# ── Health & config ────────────────────────────────────────────────────────


def test_health_offline(offline_client: TestClient):
    body = offline_client.get("/api/health").json()
    assert body["csw_connected"] is False
    assert "model" in body


def test_config_patch(offline_client: TestClient):
    resp = offline_client.patch("/api/config", json={"safe_mode": False})
    assert resp.status_code == 200
    assert resp.json()["safe_mode"] is False


# ── Queries ────────────────────────────────────────────────────────────────


def test_queries_catalog_shape(offline_client: TestClient):
    catalog = offline_client.get("/api/queries").json()
    keys = {q["key"] for q in catalog}
    assert {"agent_summary", "search_workspace", "vulnerability_report"}.issubset(keys)
    sw = next(q for q in catalog if q["key"] == "search_workspace")
    assert sw["inputs"][0]["name"] == "name"
    assert sw["result_kind"] == "stdout"


def test_queries_catalog_categories():
    catalog = build_web_catalog()
    categories = {q.category for q in catalog}
    assert {"Agents", "Workspaces", "Inventory", "Enforcement"}.issubset(categories)


def test_unknown_query_returns_404(offline_client: TestClient):
    assert offline_client.post("/api/queries/bogus/run", json={"inputs": {}}).status_code == 404


def test_query_offline_returns_503(offline_client: TestClient):
    resp = offline_client.post("/api/queries/agent_summary/run", json={"inputs": {}})
    assert resp.status_code == 503


def test_query_missing_input_returns_422(live_client: TestClient):
    resp = live_client.post("/api/queries/search_workspace/run", json={"inputs": {}})
    assert resp.status_code == 422


def test_structured_agent_summary(live_client: TestClient, fake_rest):
    pages = iter(
        [
            FakeResponse(
                200,
                {
                    "results": [
                        {"platform": "Linux", "agent_type_str": "Deep"},
                        {"platform": "Linux", "agent_type_str": "Light"},
                        {"platform": "Windows", "agent_type_str": "Deep"},
                    ]
                },
            )
        ]
    )
    fake_rest.register("GET", "/sensors", lambda **_: next(pages))
    resp = live_client.post("/api/queries/agent_summary/run", json={"inputs": {}})
    assert resp.status_code == 200
    body = resp.json()
    assert body["kind"] == "structured"
    summary = body["data"]["summary"]
    assert summary["total_agents"] == 3
    tables = body["data"]["tables"]
    assert any("Linux" in str(t["rows"]) for t in tables)


def test_structured_workspace_summary(live_client: TestClient, fake_rest):
    fake_rest.register(
        "GET",
        "/applications",
        lambda **_: FakeResponse(
            200,
            [
                {"analysis_enabled": True, "enforcement_enabled": True},
                {"analysis_enabled": False, "enforcement_enabled": False},
            ],
        ),
    )
    body = live_client.post("/api/queries/workspace_summary/run", json={"inputs": {}}).json()
    assert body["data"]["summary"]["total_workspaces"] == 2
    assert body["data"]["summary"]["analysis_enabled"] == 1


def test_stdout_query_captures_output(live_client: TestClient, fake_rest):
    fake_rest.register(
        "GET",
        "/applications",
        lambda **_: FakeResponse(
            200,
            [{"name": "PROD-A", "analysis_enabled": True, "enforcement_enabled": True, "id": "x" * 12}],
        ),
    )
    resp = live_client.post(
        "/api/queries/search_workspace/run",
        json={"inputs": {"name": "prod"}},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["kind"] == "stdout"
    assert "PROD-A" in body["data"]["stdout"]
    assert body["data"]["success"] is True


def test_stdout_query_handles_failure(live_client: TestClient, fake_rest):
    fake_rest.register("GET", "/applications", lambda **_: FakeResponse(500, content=b"down"))
    body = live_client.post(
        "/api/queries/search_workspace/run",
        json={"inputs": {"name": "x"}},
    ).json()
    assert "Error" in body["data"]["stdout"]


# ── Files ──────────────────────────────────────────────────────────────────


def test_file_download_rejects_traversal_and_bad_suffix(offline_client: TestClient):
    # Backslash and literal '..' inside the filename are rejected by the handler.
    assert offline_client.get("/api/files/..hidden.csv").status_code == 400
    assert offline_client.get("/api/files/secret.txt").status_code == 400


def test_file_download_404_for_missing(offline_client: TestClient):
    assert offline_client.get("/api/files/missing.csv").status_code == 404


def test_file_download_serves_csv(offline_client: TestClient, tmp_path, monkeypatch):
    csv = tmp_path / "report.csv"
    csv.write_text("a,b\n1,2\n")
    monkeypatch.chdir(tmp_path)
    resp = offline_client.get("/api/files/report.csv")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")


# ── Chat ───────────────────────────────────────────────────────────────────


def test_chat_empty_message_returns_422(offline_client: TestClient):
    resp = offline_client.post("/api/chat", json={"message": "   "})
    assert resp.status_code == 422


def test_chat_reset_and_history(offline_client: TestClient):
    assert offline_client.post("/api/chat/reset").json() == {"ok": True}
    assert offline_client.get("/api/chat/history").json() == []


def test_prompt_history_endpoints(offline_client: TestClient):
    from csw_agent.dashboard.prompt_history import get_history

    get_history().add("how many agents?")
    get_history().add("show workspaces")
    resp = offline_client.get("/api/chat/prompts").json()
    assert [r["message"] for r in resp] == ["show workspaces", "how many agents?"]

    cleared = offline_client.delete("/api/chat/prompts").json()
    assert cleared == {"ok": True}
    assert offline_client.get("/api/chat/prompts").json() == []


def test_chat_offline_streams_error(offline_client: TestClient):
    with offline_client.stream("POST", "/api/chat", json={"message": "hi"}) as resp:
        assert resp.status_code == 200
        body = b"".join(resp.iter_bytes()).decode()
    assert '"type": "error"' in body
    assert "CSW is not connected" in body
    assert '"type": "done"' in body
