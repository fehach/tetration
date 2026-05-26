"""In-memory telemetry: API calls, Claude requests, logs, alerts.

The dashboard reads from this module. Buffers are bounded ring buffers so the
process never grows unbounded; aggregations are computed on demand.
"""

from __future__ import annotations

import contextlib
import logging
import time
from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Literal

EventKind = Literal["api", "claude", "query"]
Severity = Literal["info", "warn", "error", "critical"]


@dataclass(slots=True)
class Event:
    """A single telemetry event (API call, Claude request, query run)."""

    kind: EventKind
    timestamp: float
    duration_ms: float
    success: bool
    label: str
    detail: str = ""
    tokens_in: int = 0
    tokens_out: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "timestamp": self.timestamp,
            "iso_time": datetime.fromtimestamp(self.timestamp, tz=timezone.utc).isoformat(),
            "duration_ms": round(self.duration_ms, 2),
            "success": self.success,
            "label": self.label,
            "detail": self.detail,
            "tokens_in": self.tokens_in,
            "tokens_out": self.tokens_out,
        }


@dataclass(slots=True)
class LogEntry:
    """A single log line surfaced to the dashboard."""

    timestamp: float
    level: str
    source: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "iso_time": datetime.fromtimestamp(self.timestamp, tz=timezone.utc).isoformat(),
            "level": self.level,
            "source": self.source,
            "message": self.message,
        }


@dataclass(slots=True)
class Alert:
    """A user-visible alert (acknowledgable)."""

    id: str
    timestamp: float
    severity: Severity
    title: str
    body: str = ""
    acknowledged: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "iso_time": datetime.fromtimestamp(self.timestamp, tz=timezone.utc).isoformat(),
            "severity": self.severity,
            "title": self.title,
            "body": self.body,
            "acknowledged": self.acknowledged,
        }


@dataclass
class Telemetry:
    """Thread-safe telemetry store with bounded buffers."""

    max_events: int = 2000
    max_logs: int = 1000
    max_alerts: int = 200
    started_at: float = field(default_factory=time.time)

    def __post_init__(self) -> None:
        self._events: deque[Event] = deque(maxlen=self.max_events)
        self._logs: deque[LogEntry] = deque(maxlen=self.max_logs)
        self._alerts: deque[Alert] = deque(maxlen=self.max_alerts)
        self._lock = Lock()
        self._next_alert_id = 1

    # ── Recording ──────────────────────────────────────────────────────────
    def record_event(self, event: Event) -> None:
        with self._lock:
            self._events.append(event)

    def record_log(self, entry: LogEntry) -> None:
        with self._lock:
            self._logs.append(entry)

    def add_alert(self, severity: Severity, title: str, body: str = "") -> Alert:
        with self._lock:
            alert = Alert(
                id=f"a-{self._next_alert_id}",
                timestamp=time.time(),
                severity=severity,
                title=title,
                body=body,
            )
            self._next_alert_id += 1
            self._alerts.append(alert)
            return alert

    def acknowledge(self, alert_id: str) -> bool:
        with self._lock:
            for alert in self._alerts:
                if alert.id == alert_id:
                    alert.acknowledged = True
                    return True
        return False

    # ── Snapshots ──────────────────────────────────────────────────────────
    def events(self, kind: EventKind | None = None, limit: int = 500) -> list[Event]:
        with self._lock:
            data = list(self._events)
        if kind:
            data = [e for e in data if e.kind == kind]
        return data[-limit:]

    def logs(self, level: str | None = None, limit: int = 500) -> list[LogEntry]:
        with self._lock:
            data = list(self._logs)
        if level:
            data = [entry for entry in data if entry.level.lower() == level.lower()]
        return data[-limit:]

    def alerts(self, include_acknowledged: bool = True) -> list[Alert]:
        with self._lock:
            data = list(self._alerts)
        if not include_acknowledged:
            data = [a for a in data if not a.acknowledged]
        return list(reversed(data))

    # ── Aggregations ───────────────────────────────────────────────────────
    def summary(self) -> dict[str, Any]:
        with self._lock:
            events = list(self._events)
        api = [e for e in events if e.kind == "api"]
        claude = [e for e in events if e.kind == "claude"]
        queries = [e for e in events if e.kind == "query"]
        return {
            "uptime_seconds": int(time.time() - self.started_at),
            "started_at": self.started_at,
            "api": _stats(api),
            "claude": _stats(claude, include_tokens=True),
            "queries": _stats(queries),
        }

    def timeseries(self, kind: EventKind, minutes: int = 60) -> list[dict[str, Any]]:
        """Return per-minute buckets of count/avg latency for ``kind`` over the window."""
        cutoff = time.time() - minutes * 60
        with self._lock:
            events = [e for e in self._events if e.kind == kind and e.timestamp >= cutoff]
        bucket_size = 60
        now_bucket = int(time.time() // bucket_size)
        first_bucket = now_bucket - minutes + 1
        buckets: dict[int, list[Event]] = {b: [] for b in range(first_bucket, now_bucket + 1)}
        for event in events:
            bucket = int(event.timestamp // bucket_size)
            if bucket in buckets:
                buckets[bucket].append(event)
        return [_bucket_to_dict(bucket * bucket_size, items) for bucket, items in sorted(buckets.items())]


def _stats(events: Iterable[Event], include_tokens: bool = False) -> dict[str, Any]:
    """Compute count, success rate, and latency percentiles."""
    items = list(events)
    total = len(items)
    if total == 0:
        out: dict[str, Any] = {
            "total": 0,
            "success_rate": 1.0,
            "p50_ms": 0,
            "p95_ms": 0,
            "p99_ms": 0,
            "avg_ms": 0,
        }
        if include_tokens:
            out.update({"tokens_in": 0, "tokens_out": 0})
        return out
    successes = sum(1 for e in items if e.success)
    durations = sorted(e.duration_ms for e in items)
    out = {
        "total": total,
        "success_rate": round(successes / total, 4),
        "p50_ms": _percentile(durations, 50),
        "p95_ms": _percentile(durations, 95),
        "p99_ms": _percentile(durations, 99),
        "avg_ms": round(sum(durations) / total, 2),
    }
    if include_tokens:
        out["tokens_in"] = sum(e.tokens_in for e in items)
        out["tokens_out"] = sum(e.tokens_out for e in items)
    return out


def _percentile(sorted_values: list[float], p: float) -> float:
    if not sorted_values:
        return 0
    k = max(0, min(len(sorted_values) - 1, round((p / 100) * (len(sorted_values) - 1))))
    return round(sorted_values[k], 2)


def _bucket_to_dict(timestamp: float, events: list[Event]) -> dict[str, Any]:
    successes = sum(1 for e in events if e.success)
    avg = round(sum(e.duration_ms for e in events) / len(events), 2) if events else 0
    return {
        "timestamp": timestamp,
        "iso_time": datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat(),
        "count": len(events),
        "success_count": successes,
        "error_count": len(events) - successes,
        "avg_ms": avg,
        "tokens_in": sum(e.tokens_in for e in events),
        "tokens_out": sum(e.tokens_out for e in events),
    }


# ── Process-wide singleton ────────────────────────────────────────────────
_INSTANCE: Telemetry | None = None


def get_telemetry() -> Telemetry:
    """Return the process-wide Telemetry instance (created lazily)."""
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = Telemetry()
    return _INSTANCE


def reset_for_tests() -> None:
    """Reset the singleton; only use in tests."""
    global _INSTANCE
    _INSTANCE = None


class TelemetryLogHandler(logging.Handler):
    """Logging handler that pushes records into the telemetry log buffer."""

    def __init__(self, telemetry: Telemetry, level: int = logging.INFO):
        super().__init__(level=level)
        self._telemetry = telemetry

    def emit(self, record: logging.LogRecord) -> None:
        with contextlib.suppress(Exception):
            self._telemetry.record_log(
                LogEntry(
                    timestamp=record.created,
                    level=record.levelname,
                    source=record.name,
                    message=self.format(record),
                )
            )
