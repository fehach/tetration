"""Simple in-memory TTL cache."""

from __future__ import annotations

import time
from collections.abc import Callable
from threading import Lock
from typing import Generic, TypeVar

T = TypeVar("T")


class TTLCache(Generic[T]):
    """Holds a single value for `ttl_seconds`, recomputing on expiry."""

    def __init__(self, ttl_seconds: int):
        self._ttl = ttl_seconds
        self._value: T | None = None
        self._expires_at: float = 0.0
        self._lock = Lock()

    def get_or_compute(self, factory: Callable[[], T]) -> T:
        with self._lock:
            now = time.monotonic()
            if self._value is not None and now < self._expires_at:
                return self._value
            value = factory()
            self._value = value
            self._expires_at = now + self._ttl
            return value

    def invalidate(self) -> None:
        with self._lock:
            self._value = None
            self._expires_at = 0.0
