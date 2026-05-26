"""CSV helpers shared across queries and the CSV chat module."""

from __future__ import annotations

import csv
import json
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

DANGEROUS_CSV_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def to_bool(value: Any) -> bool:
    """Coerce common truthy/falsy representations into a bool."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("true", "1", "yes", "y"):
            return True
        if lowered in ("false", "0", "no", "n", ""):
            return False
    return bool(value)


def is_blank(value: Any) -> bool:
    """Return True if value is None or a whitespace-only string."""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    return False


def display_value(value: Any) -> Any:
    """Return ``(blank)`` for empty values, otherwise the original value."""
    return "(blank)" if is_blank(value) else value


def to_number(value: Any) -> int | float | None:
    """Best-effort numeric coercion. Returns None when conversion fails."""
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return value
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped:
        return None
    if stripped.endswith("%"):
        stripped = stripped[:-1].strip()
    stripped = stripped.replace(",", "")
    try:
        if any(ch in stripped for ch in (".", "e", "E")):
            return float(stripped)
        return int(stripped)
    except ValueError:
        return None


def safe_pct(part: Any, whole: Any, decimals: int = 1) -> str:
    """Format a percentage, returning ``0.0%`` when the divisor is zero/missing."""
    part_num = to_number(part)
    whole_num = to_number(whole)
    if part_num is None or whole_num in (None, 0):
        return f"{0:.{decimals}f}%"
    return f"{(part_num / whole_num) * 100:.{decimals}f}%"  # type: ignore[operator]


def sanitize_csv_cell(value: Any) -> Any:
    """Prefix risky values with `'` to defang CSV-injection attacks in spreadsheets."""
    if isinstance(value, str) and value.startswith(DANGEROUS_CSV_PREFIXES):
        return "'" + value
    return value


def write_csv(filepath: Path, columns: list[str], rows: Iterable[Mapping[str, Any]]) -> int:
    """Write rows to filepath. Returns the number of rows written."""
    count = 0
    with filepath.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            sanitized = {col: sanitize_csv_cell(row.get(col, "")) for col in columns}
            writer.writerow(sanitized)
            count += 1
    return count


def load_csv_rows(filepath: Path) -> list[dict[str, Any]]:
    """Load a CSV file, normalizing whitespace and ``true``/``false`` strings."""
    rows: list[dict[str, Any]] = []
    with filepath.open(newline="", encoding="utf-8") as f:
        for raw in csv.DictReader(f):
            rows.append({k: _normalize_cell(v) for k, v in raw.items()})
    return rows


def _normalize_cell(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    lowered = stripped.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    return stripped


def csv_context(filepath: Path, rows: list[dict[str, Any]]) -> str:
    """Build a textual summary of a CSV used as Claude context."""
    if not rows:
        return f"File: {filepath}\nRows: 0\nColumns: []"

    columns = list(rows[0].keys())
    lines = [
        f"File: {filepath}",
        f"Rows: {len(rows):,}",
        f"Columns: {columns}",
    ]
    blanks = {c: sum(1 for r in rows if is_blank(r.get(c))) for c in columns}
    blanks = {c: n for c, n in blanks.items() if n}
    bool_cols = [c for c in columns if _all_bool(rows, c)]
    numeric_cols = [c for c in columns if _mostly_numeric(rows, c)]

    if blanks:
        top = dict(sorted(blanks.items(), key=lambda kv: -kv[1])[:10])
        lines.append(f"Columns with blank values: {top}")
    if bool_cols:
        lines.append(f"Boolean columns detected: {bool_cols}")
    if numeric_cols:
        lines.append(f"Numeric columns detected: {numeric_cols}")
    for col in numeric_cols[:10]:
        nums = [n for n in (to_number(r.get(col)) for r in rows) if n is not None]
        if nums:
            avg = sum(nums) / len(nums)
            lines.append(
                f"Numeric summary for {col}: min={min(nums):,}, max={max(nums):,}, "
                f"avg={avg:,.2f}, sum={sum(nums):,}"
            )
    if "workspace_name" in columns:
        ws = Counter(display_value(r.get("workspace_name")) for r in rows)
        lines.append(f"Unique workspace_name values: {len(ws):,}")
        lines.append(f"Top workspace_name values: {ws.most_common(10)}")
    if "current_sw_version" in columns:
        ver = Counter(display_value(r.get("current_sw_version")) for r in rows)
        lines.append(f"Top current_sw_version values: {ver.most_common(10)}")
    for col in ("enforcement_enabled", "workspace_enforcement_enabled"):
        if col in columns:
            enabled = sum(1 for r in rows if to_bool(r.get(col)))
            lines.append(f"{col}=True rows: {enabled:,}")
    lines.append(f"Sample rows:\n{json.dumps(rows[:3], indent=2, default=str)}")
    return "\n".join(lines)


def _all_bool(rows: list[dict[str, Any]], col: str) -> bool:
    values = [r.get(col) for r in rows if not is_blank(r.get(col))]
    return bool(values) and all(isinstance(v, bool) for v in values)


def _mostly_numeric(rows: list[dict[str, Any]], col: str, threshold: float = 0.9) -> bool:
    values = [r.get(col) for r in rows if not is_blank(r.get(col))]
    if not values or any(isinstance(v, bool) for v in values):
        return False
    converted = [to_number(v) for v in values]
    numeric = sum(1 for v in converted if v is not None)
    return numeric / len(values) >= threshold
