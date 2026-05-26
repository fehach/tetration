"""Shared helpers for pre-built queries."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Any

from csw_agent.client import CSWClient

logger = logging.getLogger(__name__)


def fetch_all_sensors(client: CSWClient, page_size: int = 500) -> tuple[list[dict[str, Any]], str | None]:
    """Paginate through GET /sensors. Returns (sensors, error)."""
    sensors: list[dict[str, Any]] = []
    offset: str | None = None
    while True:
        params: dict[str, Any] = {"limit": page_size}
        if offset:
            params["offset"] = offset
        data, error = client.call("GET", "/sensors", params=params)
        if error:
            return sensors, error
        if isinstance(data, dict) and "results" in data:
            sensors.extend(data["results"])
            offset = data.get("offset") or None
            if not offset:
                break
        elif isinstance(data, list):
            sensors.extend(data)
            break
        else:
            break
    return sensors, None


def fetch_workspaces(client: CSWClient) -> tuple[list[dict[str, Any]], str | None]:
    """GET /applications. Returns (workspaces, error)."""
    data, error = client.call("GET", "/applications")
    if error:
        return [], error
    return data if isinstance(data, list) else [], None


def fetch_scopes(client: CSWClient) -> tuple[list[dict[str, Any]], str | None]:
    """GET /app_scopes. Returns (scopes, error)."""
    data, error = client.call("GET", "/app_scopes")
    if error:
        return [], error
    return data if isinstance(data, list) else [], None


def extract_hostnames(query: dict[str, Any] | None) -> list[str]:
    """Recursively pull host_name values from a scope short_query filter tree."""
    if not query:
        return []
    hostnames: list[str] = []
    if query.get("field") == "host_name" and query.get("value"):
        hostnames.append(str(query["value"]).lower())
    if query.get("type") in ("and", "or"):
        for sub in query.get("filters", []):
            hostnames.extend(extract_hostnames(sub))
    return hostnames


def build_hostname_to_workspace(
    client: CSWClient,
    max_workers: int = 10,
) -> tuple[dict[str, dict[str, Any]], int, int] | tuple[None, int, int]:
    """Map hostnames to workspace metadata. Returns (mapping, total_ws, enforced_ws)."""
    workspaces, error = fetch_workspaces(client)
    if error:
        print(f"  Error fetching workspaces: {error}")
        return None, 0, 0
    print(f"  Found {len(workspaces):,} workspaces. Fetching details (this may take a moment)...")

    details = _fetch_all_workspace_details(client, workspaces, max_workers)
    mapping: dict[str, dict[str, Any]] = {}
    enforced = 0
    for ws in details:
        if ws["enforcement_enabled"]:
            enforced += 1
        for host in ws["hostnames"]:
            mapping[host] = ws

    print(f"  Enforcement-enabled workspaces: {enforced:,}")
    print(f"  Hostnames mapped to workspaces: {len(mapping):,}")
    return mapping, len(details), enforced


def _fetch_all_workspace_details(
    client: CSWClient,
    workspaces: list[dict[str, Any]],
    max_workers: int,
) -> list[dict[str, Any]]:
    def fetch_one(ws: dict[str, Any]) -> dict[str, Any]:
        ws_id = ws["id"]
        data, error = client.call("GET", f"/applications/{ws_id}/details")
        if error or not isinstance(data, dict):
            return {
                "name": ws.get("name", ""),
                "enforcement_enabled": ws.get("enforcement_enabled", False),
                "hostnames": [],
            }
        short_query = (data.get("app_scope") or {}).get("short_query") or {}
        return {
            "name": ws.get("name", ""),
            "enforcement_enabled": data.get("enforcement_enabled", False),
            "hostnames": extract_hostnames(short_query),
        }

    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(fetch_one, w): w for w in workspaces}
        for completed, future in enumerate(as_completed(futures), start=1):
            try:
                results.append(future.result())
            except Exception as exc:
                logger.debug("Workspace detail fetch failed: %s", exc)
            if completed % 200 == 0:
                print(f"    ... {completed}/{len(workspaces)} workspaces processed")
    return results


def non_loopback_ips(interfaces: Iterable[dict[str, Any]] | None) -> list[str]:
    """Return non-loopback IPs from an agent's interface list."""
    if not interfaces:
        return []
    out = []
    for iface in interfaces:
        if not isinstance(iface, dict):
            continue
        ip = iface.get("ip")
        if ip and not ip.startswith("127.") and not ip.startswith("::") and ip != "::1":
            out.append(ip)
    return out


def primary_ip(agent: dict[str, Any]) -> str:
    """Best-effort single IP for an agent (joined non-loopback or client_ip)."""
    ips = non_loopback_ips(agent.get("interfaces") or [])
    return ", ".join(ips) if ips else (agent.get("client_ip") or "")


def timestamped_path(basename: str, suffix: str = ".csv", directory: Path | None = None) -> Path:
    """Build a path like ``basename_YYYYMMDD_HHMMSS.csv`` in cwd or ``directory``."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    base = directory or Path.cwd()
    return base / f"{basename}_{ts}{suffix}"


def percentage(part: int, whole: int, decimals: int = 1) -> str:
    """Format a percentage; returns ``0.0%`` when ``whole`` is zero."""
    if whole <= 0:
        return f"{0:.{decimals}f}%"
    return f"{(part / whole) * 100:.{decimals}f}%"
