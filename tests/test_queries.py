"""Tests for query helpers and registry behavior."""

from __future__ import annotations

from csw_agent.cache import TTLCache
from csw_agent.queries import build_registry
from csw_agent.queries._helpers import (
    extract_hostnames,
    fetch_all_sensors,
    non_loopback_ips,
    percentage,
    primary_ip,
)
from tests.conftest import FakeResponse


def test_registry_keys_are_unique():
    registry = build_registry()
    keys = [q.key for q in registry]
    assert len(keys) == len(set(keys))


def test_percentage_handles_zero():
    assert percentage(5, 0) == "0.0%"
    assert percentage(1, 4) == "25.0%"


def test_extract_hostnames_recursive():
    query = {
        "type": "and",
        "filters": [
            {"field": "host_name", "value": "WEB01"},
            {
                "type": "or",
                "filters": [
                    {"field": "host_name", "value": "DB02"},
                    {"field": "ip", "value": "10.0.0.1"},
                ],
            },
        ],
    }
    assert extract_hostnames(query) == ["web01", "db02"]


def test_non_loopback_ips_filters():
    interfaces = [
        {"ip": "127.0.0.1"},
        {"ip": "::1"},
        {"ip": "10.0.0.1"},
        "not a dict",
        {"ip": None},
    ]
    assert non_loopback_ips(interfaces) == ["10.0.0.1"]


def test_primary_ip_falls_back_to_client_ip():
    agent = {"interfaces": [{"ip": "127.0.0.1"}], "client_ip": "1.2.3.4"}
    assert primary_ip(agent) == "1.2.3.4"


def test_fetch_all_sensors_paginates(csw_client, fake_rest):
    pages = iter(
        [
            FakeResponse(200, {"results": [{"id": 1}], "offset": "abc"}),
            FakeResponse(200, {"results": [{"id": 2}]}),
        ]
    )
    fake_rest.register("GET", "/sensors", lambda **_: next(pages))
    sensors, error = fetch_all_sensors(csw_client)
    assert error is None
    assert [s["id"] for s in sensors] == [1, 2]


def test_ttl_cache_reuses_value():
    cache: TTLCache[int] = TTLCache(ttl_seconds=60)
    counter = {"n": 0}

    def factory() -> int:
        counter["n"] += 1
        return counter["n"]

    assert cache.get_or_compute(factory) == 1
    assert cache.get_or_compute(factory) == 1
    cache.invalidate()
    assert cache.get_or_compute(factory) == 2
