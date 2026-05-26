"""Inventory, VRF, and service health queries."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from csw_agent.tabulate_fallback import tabulate

if TYPE_CHECKING:
    from csw_agent.queries import QueryContext

_IP_PATTERN = re.compile(r"^\d+\.\d+\.\d+\.\d+")


def search_inventory(ctx: QueryContext) -> None:
    """Interactive inventory search by hostname or IP."""
    search = input("  Enter hostname or IP to search: ").strip()
    if not search:
        return
    filter_q = _build_filter(search)
    body = {"filter": filter_q, "limit": 20}
    data, error = ctx.client.call("POST", "/inventory/search", json_body=body)
    if error:
        print(f"  Error: {error}")
        return
    results = data.get("results", []) if isinstance(data, dict) else []
    if not results:
        print(f"  No inventory items found for '{search}'")
        return
    rows = [
        [
            r.get("hostname", ""),
            r.get("ip", ""),
            r.get("os", ""),
            r.get("os_version", ""),
            r.get("vrf_name", ""),
        ]
        for r in results
    ]
    print(f"\n  Found {len(results)} inventory item(s):")
    print(tabulate(rows, headers=["Hostname", "IP", "OS", "OS Version", "VRF"], tablefmt="grid"))


def list_vrfs(ctx: QueryContext) -> None:
    """List configured VRFs."""
    print("  Fetching VRFs...")
    data, error = ctx.client.call("GET", "/vrfs")
    if error:
        print(f"  Error: {error}")
        return
    vrfs = _normalize_list(data)
    rows = [[v.get("name", ""), v.get("id", ""), v.get("vrf_id", ""), v.get("tenant_name", "")] for v in vrfs]
    print(tabulate(rows, headers=["Name", "ID", "VRF ID", "Tenant"], tablefmt="grid"))


def service_health(ctx: QueryContext) -> None:
    """Print CSW service status output."""
    print("  Checking service health...")
    data, error = ctx.client.call("GET", "/service_status")
    if error:
        print(f"  Error: {error}")
        return
    if isinstance(data, list):
        rows = [[s.get("name", ""), s.get("status", ""), s.get("description", "")] for s in data[:20]]
        print(tabulate(rows, headers=["Service", "Status", "Description"], tablefmt="grid"))
    else:
        print(f"  Response: {json.dumps(data, indent=2)[:2000]}")


def _build_filter(search: str) -> dict[str, Any]:
    if _IP_PATTERN.match(search):
        if "/" in search:
            return {"type": "subnet", "field": "ip", "value": search}
        return {"type": "eq", "field": "ip", "value": search}
    return {"type": "contains", "field": "hostname", "value": search}


def _normalize_list(data: Any) -> list[dict[str, Any]]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return data.get("results") or []
    return []
