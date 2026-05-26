"""Tests for CSWClient and the api_call wrapper."""

from __future__ import annotations

from tests.conftest import FakeResponse


def test_call_get_returns_data(csw_client, fake_rest):
    fake_rest.register("GET", "/sensors", lambda **_: FakeResponse(200, {"results": []}))
    data, error = csw_client.call("GET", "/sensors", params={"limit": 1})
    assert error is None
    assert data == {"results": []}


def test_call_serializes_dict_body(csw_client, fake_rest):
    captured = {}

    def handler(*, params, json_body):
        captured["body"] = json_body
        return FakeResponse(200, {"ok": True})

    fake_rest.register("POST", "/inventory/search", handler)
    csw_client.call("POST", "/inventory/search", json_body={"limit": 5})
    assert captured["body"] == '{"limit": 5}'


def test_call_returns_error_on_non_200(csw_client, fake_rest):
    fake_rest.register("GET", "/x", lambda **_: FakeResponse(404, content=b"missing"))
    data, error = csw_client.call("GET", "/x")
    assert data is None
    assert error is not None
    assert "404" in error


def test_call_returns_text_when_not_json(csw_client, fake_rest):
    fake_rest.register("GET", "/raw", lambda **_: FakeResponse(200, json_data=None, content=b"plain text"))
    data, error = csw_client.call("GET", "/raw")
    assert error is None
    assert data == "plain text"


def test_unsupported_method(csw_client):
    data, error = csw_client.call("OPTIONS", "/x")
    assert data is None
    assert error is not None
    assert "Unsupported" in error


def test_health_check(csw_client, fake_rest):
    fake_rest.register("GET", "/sensors", lambda **_: FakeResponse(200, {"results": []}))
    assert csw_client.health_check() is True


def test_health_check_failure(csw_client, fake_rest):
    fake_rest.register("GET", "/sensors", lambda **_: FakeResponse(500, content=b"down"))
    assert csw_client.health_check() is False
