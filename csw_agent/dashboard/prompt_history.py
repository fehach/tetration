"""Persistent log of chat prompts the user has sent.

Stored as JSON Lines at ``~/.csw/prompt_history.jsonl`` so it survives restarts.
Entries are capped to keep the file from growing without bound.
"""

from __future__ import annotations

import contextlib
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_HISTORY_PATH = Path.home() / ".csw" / "prompt_history.jsonl"
MAX_ENTRIES = 200


@dataclass(slots=True)
class PromptEntry:
    """A single prompt sent through the dashboard chat."""

    timestamp: float
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {"timestamp": self.timestamp, "message": self.message}


class PromptHistory:
    """Thread-safe append-only store with on-disk persistence."""

    def __init__(self, path: Path = DEFAULT_HISTORY_PATH, max_entries: int = MAX_ENTRIES):
        self._path = path
        self._max = max_entries
        self._lock = Lock()
        self._entries: list[PromptEntry] = self._load()

    def _load(self) -> list[PromptEntry]:
        if not self._path.exists():
            return []
        try:
            with self._path.open(encoding="utf-8") as f:
                return [self._parse(line) for line in f if line.strip()]
        except OSError as exc:
            logger.warning("Could not read prompt history at %s: %s", self._path, exc)
            return []

    @staticmethod
    def _parse(line: str) -> PromptEntry:
        payload = json.loads(line)
        return PromptEntry(timestamp=float(payload["timestamp"]), message=str(payload["message"]))

    def add(self, message: str) -> PromptEntry:
        entry = PromptEntry(timestamp=time.time(), message=message)
        with self._lock:
            self._entries.append(entry)
            self._entries = self._entries[-self._max :]
            self._persist()
        return entry

    def list(self, limit: int | None = None) -> list[PromptEntry]:
        with self._lock:
            data = list(reversed(self._entries))
        return data[:limit] if limit else data

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._persist()

    def _persist(self) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("w", encoding="utf-8") as f:
                for entry in self._entries:
                    f.write(json.dumps(entry.to_dict()) + "\n")
            with contextlib.suppress(OSError):
                self._path.chmod(0o600)
        except OSError as exc:
            logger.warning("Could not write prompt history to %s: %s", self._path, exc)


_INSTANCE: PromptHistory | None = None


def get_history() -> PromptHistory:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = PromptHistory()
    return _INSTANCE


def reset_for_tests(path: Path | None = None) -> PromptHistory:
    """Replace the module-level singleton (used in tests)."""
    global _INSTANCE
    _INSTANCE = PromptHistory(path=path or DEFAULT_HISTORY_PATH)
    return _INSTANCE
