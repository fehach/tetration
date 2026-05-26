"""Fallback `tabulate` implementation used when the dependency is unavailable."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

try:
    from tabulate import tabulate as _tabulate
except ModuleNotFoundError:  # pragma: no cover - exercised when tabulate is missing
    _tabulate = None  # type: ignore[assignment]


def tabulate(
    rows: Iterable[Sequence[Any] | dict[str, Any]] | None,
    headers: Sequence[str] | str = (),
    tablefmt: str | None = None,
    showindex: bool = False,
) -> str:
    """Format `rows` as a table. Delegates to the real tabulate if installed."""
    if _tabulate is not None:
        return _tabulate(rows or [], headers=headers, tablefmt=tablefmt or "simple", showindex=showindex)
    return _basic_format(list(rows or []), headers, tablefmt, showindex)


def _basic_format(
    rows: list[Sequence[Any] | dict[str, Any]],
    headers: Sequence[str] | str,
    tablefmt: str | None,
    showindex: bool,
) -> str:
    if headers == "keys" and rows and isinstance(rows[0], dict):
        header_row = list(rows[0].keys())
        data_rows = [[row.get(col, "") for col in header_row] for row in rows]  # type: ignore[union-attr]
    else:
        header_row = list(headers) if headers and headers != "keys" else []
        data_rows = [list(r) if isinstance(r, (list, tuple)) else [r] for r in rows]

    if showindex:
        header_row = ["#", *header_row]
        data_rows = [[idx, *row] for idx, row in enumerate(data_rows)]

    col_count = max([len(header_row), *(len(r) for r in data_rows)], default=0)
    if col_count == 0:
        return ""

    header_row = [*header_row, *[""] * (col_count - len(header_row))]
    data_rows = [[str(c) for c in row] + [""] * (col_count - len(row)) for row in data_rows]
    width_source = ([header_row] if header_row else []) + data_rows
    widths = [max(len(str(row[i])) for row in width_source) for i in range(col_count)]

    if tablefmt == "grid":
        return _format_grid(header_row, data_rows, widths, col_count)
    return _format_plain(header_row, data_rows, widths, col_count)


def _format_grid(header: list[str], data: list[list[str]], widths: list[int], cols: int) -> str:
    border = "+-" + "-+-".join("-" * w for w in widths) + "-+"
    lines = [border]
    if header:
        lines.append("| " + " | ".join(header[i].ljust(widths[i]) for i in range(cols)) + " |")
        lines.append(border)
    lines.extend("| " + " | ".join(row[i].ljust(widths[i]) for i in range(cols)) + " |" for row in data)
    lines.append(border)
    return "\n".join(lines)


def _format_plain(header: list[str], data: list[list[str]], widths: list[int], cols: int) -> str:
    lines: list[str] = []
    if header:
        lines.append("  ".join(header[i].ljust(widths[i]) for i in range(cols)))
        lines.append("  ".join("-" * widths[i] for i in range(cols)))
    lines.extend("  ".join(row[i].ljust(widths[i]) for i in range(cols)) for row in data)
    return "\n".join(lines)
