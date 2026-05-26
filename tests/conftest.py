"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any
from unittest.mock import MagicMock

import pytest


class FakeResponse:
    def __init__(self, status_code: int, json_data: Any = None, content: bytes = b""):
        self.status_code = status_code
        self._json = json_data
        self.content = content if content else (b"" if json_data is None else b"{}")

    def json(self) -> Any:
        if self._json is None:
            raise ValueError("no JSON body")
        return self._json


class FakeRest:
    """Stand-in for tetpyclient.RestClient with scriptable responses."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, Any] | None, str | None]] = []
        self._handlers: dict[tuple[str, str], Callable[..., FakeResponse]] = {}
        self.default_response = FakeResponse(404, content=b"not found")

    def register(self, method: str, path: str, handler: Callable[..., FakeResponse]) -> None:
        self._handlers[(method.upper(), path)] = handler

    def _dispatch(self, method: str, path: str, *, params=None, json_body=None, **_kwargs) -> FakeResponse:
        self.calls.append((method, path, params, json_body))
        handler = self._handlers.get((method, path))
        if handler is None:
            return self.default_response
        return handler(params=params, json_body=json_body)

    def get(self, path: str, params=None, **kwargs) -> FakeResponse:
        return self._dispatch("GET", path, params=params, **kwargs)

    def post(self, path: str, json_body=None, **kwargs) -> FakeResponse:
        return self._dispatch("POST", path, json_body=json_body, **kwargs)

    def put(self, path: str, json_body=None, **kwargs) -> FakeResponse:
        return self._dispatch("PUT", path, json_body=json_body, **kwargs)

    def delete(self, path: str, **kwargs) -> FakeResponse:
        return self._dispatch("DELETE", path, **kwargs)


@pytest.fixture
def fake_rest() -> FakeRest:
    return FakeRest()


@pytest.fixture
def csw_client(fake_rest: FakeRest, tmp_path, monkeypatch):
    from csw_agent.client import CSWClient
    from csw_agent.config import Settings

    creds = tmp_path / "creds.json"
    creds.write_text('{"api_key":"x","api_secret":"y"}')
    settings = Settings(credentials_file=creds, verify_tls=True)

    fake_module = MagicMock()
    fake_module.RestClient = MagicMock(return_value=fake_rest)
    monkeypatch.setitem(__import__("sys").modules, "tetpyclient", fake_module)

    return CSWClient(settings)
