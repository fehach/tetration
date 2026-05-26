"""Thin wrapper around tetpyclient.RestClient with structured error handling."""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import urllib3

from csw_agent.config import Settings
from csw_agent.telemetry import Event, Telemetry, get_telemetry

logger = logging.getLogger(__name__)

ApiResult = tuple[Any | None, str | None]


class CSWClient:
    """Authenticated REST client for Cisco Secure Workload."""

    def __init__(self, settings: Settings, telemetry: Telemetry | None = None):
        self._settings = settings
        self._telemetry = telemetry or get_telemetry()
        if not settings.verify_tls:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            logger.warning("TLS verification disabled — connections are not secure.")
        # Imported lazily so tests can mock without the dependency installed.
        from tetpyclient import RestClient

        credentials = settings.resolve_credentials()
        self._rest = RestClient(
            settings.api_endpoint,
            credentials_file=str(credentials),
            verify=settings.verify_tls,
        )

    @property
    def rest(self) -> Any:
        """Underlying tetpyclient RestClient. Exposed for sandboxed code execution."""
        return self._rest

    def health_check(self) -> bool:
        """Return True if the API responds successfully to a minimal request."""
        try:
            resp = self._rest.get("/sensors", params={"limit": 1})
            return resp.status_code == 200
        except Exception as exc:
            logger.error("CSW health check failed: %s", exc)
            return False

    def call(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | str | None = None,
    ) -> ApiResult:
        """Execute an API call. Returns (data, error). Either is None."""
        body = json.dumps(json_body) if isinstance(json_body, dict) else json_body
        method_upper = method.upper()
        started = time.perf_counter()
        try:
            resp = self._dispatch(method_upper, path, params=params, json_body=body)
        except Exception as exc:
            logger.exception("API call %s %s raised", method_upper, path)
            self._record(method_upper, path, started, success=False, detail=str(exc))
            return None, str(exc)

        if resp.status_code != 200:
            preview = resp.content.decode("utf-8", errors="replace")[:500]
            self._record(method_upper, path, started, success=False, detail=f"HTTP {resp.status_code}")
            return None, f"HTTP {resp.status_code}: {preview}"
        self._record(method_upper, path, started, success=True)
        try:
            return resp.json(), None
        except ValueError:
            return resp.content.decode("utf-8", errors="replace"), None

    def _record(self, method: str, path: str, started: float, success: bool, detail: str = "") -> None:
        self._telemetry.record_event(
            Event(
                kind="api",
                timestamp=time.time(),
                duration_ms=(time.perf_counter() - started) * 1000,
                success=success,
                label=f"{method} {path}",
                detail=detail,
            )
        )

    def _dispatch(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None,
        json_body: str | None,
    ) -> Any:
        timeout = self._settings.request_timeout_seconds
        if method == "GET":
            return self._rest.get(path, params=params, timeout=timeout)
        if method == "POST":
            return self._rest.post(path, json_body=json_body, timeout=timeout)
        if method == "PUT":
            return self._rest.put(path, json_body=json_body, timeout=timeout)
        if method == "DELETE":
            return self._rest.delete(path, timeout=timeout)
        raise ValueError(f"Unsupported HTTP method: {method}")
