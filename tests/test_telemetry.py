"""Tests for the telemetry module."""

from __future__ import annotations

import time

from csw_agent.telemetry import Event, Telemetry


def _make_event(kind: str, ms: float, success: bool = True) -> Event:
    return Event(
        kind=kind,  # type: ignore[arg-type]
        timestamp=time.time(),
        duration_ms=ms,
        success=success,
        label="test",
    )


def test_summary_handles_empty():
    t = Telemetry()
    s = t.summary()
    assert s["api"]["total"] == 0
    assert s["api"]["success_rate"] == 1.0
    assert "uptime_seconds" in s


def test_summary_aggregates_by_kind():
    t = Telemetry()
    t.record_event(_make_event("api", 10.0))
    t.record_event(_make_event("api", 20.0))
    t.record_event(_make_event("api", 30.0, success=False))
    t.record_event(_make_event("claude", 100.0))
    s = t.summary()
    assert s["api"]["total"] == 3
    assert 0.66 < s["api"]["success_rate"] < 0.67
    assert s["api"]["avg_ms"] == 20.0
    assert s["claude"]["total"] == 1


def test_events_filter_by_kind():
    t = Telemetry()
    t.record_event(_make_event("api", 5))
    t.record_event(_make_event("claude", 5))
    assert len(t.events("api")) == 1
    assert len(t.events("claude")) == 1
    assert len(t.events()) == 2


def test_alerts_acknowledge():
    t = Telemetry()
    a = t.add_alert("warn", "Test alert")
    assert any(not a.acknowledged for a in t.alerts(include_acknowledged=False))
    assert t.acknowledge(a.id)
    assert not any(not x.acknowledged for x in t.alerts(include_acknowledged=False))


def test_acknowledge_unknown_returns_false():
    t = Telemetry()
    assert t.acknowledge("missing") is False


def test_timeseries_buckets():
    t = Telemetry()
    t.record_event(_make_event("api", 10))
    t.record_event(_make_event("api", 20))
    series = t.timeseries("api", minutes=5)
    assert len(series) == 5
    assert sum(b["count"] for b in series) == 2


def test_ring_buffer_caps_events():
    t = Telemetry(max_events=3)
    for _ in range(5):
        t.record_event(_make_event("api", 1))
    assert len(t.events()) == 3


def test_percentiles_monotonic():
    t = Telemetry()
    for ms in (5, 10, 20, 50, 100, 200, 500, 1000):
        t.record_event(_make_event("api", ms))
    s = t.summary()["api"]
    assert s["p50_ms"] <= s["p95_ms"] <= s["p99_ms"]
