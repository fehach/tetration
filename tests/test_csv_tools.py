"""Tests for CSV helpers."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from csw_agent.csv_tools import (
    csv_context,
    display_value,
    is_blank,
    load_csv_rows,
    safe_pct,
    sanitize_csv_cell,
    to_bool,
    to_number,
    write_csv,
)


@pytest.mark.parametrize(
    "value,expected",
    [
        (True, True),
        ("true", True),
        ("YES", True),
        (1, True),
        (False, False),
        ("false", False),
        ("", False),
        (None, False),
    ],
)
def test_to_bool(value, expected):
    assert to_bool(value) is expected


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, True),
        ("", True),
        ("   ", True),
        ("hello", False),
        (0, False),
        (False, False),
    ],
)
def test_is_blank(value, expected):
    assert is_blank(value) is expected


def test_display_value():
    assert display_value(None) == "(blank)"
    assert display_value("x") == "x"


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, None),
        ("", None),
        ("12", 12),
        ("12.5", 12.5),
        ("1,234", 1234),
        ("50%", 50),
        ("abc", None),
        (True, 1),
    ],
)
def test_to_number(value, expected):
    assert to_number(value) == expected


def test_safe_pct_handles_zero():
    assert safe_pct(5, 0) == "0.0%"
    assert safe_pct(None, 10) == "0.0%"
    assert safe_pct(1, 4) == "25.0%"


@pytest.mark.parametrize(
    "value,expected",
    [
        ("=cmd|calc", "'=cmd|calc"),
        ("+SUM(A1)", "'+SUM(A1)"),
        ("-1", "'-1"),
        ("@hi", "'@hi"),
        ("normal", "normal"),
        (123, 123),
        (None, None),
    ],
)
def test_sanitize_csv_cell(value, expected):
    assert sanitize_csv_cell(value) == expected


def test_write_csv_sanitizes(tmp_path: Path):
    rows = [{"name": "=danger", "ok": "fine"}]
    path = tmp_path / "out.csv"
    written = write_csv(path, ["name", "ok"], rows)
    assert written == 1
    with path.open() as f:
        reader = list(csv.reader(f))
    assert reader[1] == ["'=danger", "fine"]


def test_load_csv_rows_normalizes_booleans(tmp_path: Path):
    path = tmp_path / "in.csv"
    path.write_text("flag,name\nTRUE,alice\nfalse, bob \n")
    rows = load_csv_rows(path)
    assert rows == [{"flag": True, "name": "alice"}, {"flag": False, "name": "bob"}]


def test_csv_context_handles_empty(tmp_path: Path):
    text = csv_context(tmp_path / "x.csv", [])
    assert "Rows: 0" in text


def test_csv_context_includes_summary(tmp_path: Path):
    rows = [
        {"workspace_name": "a", "current_sw_version": "3.9", "enforcement_enabled": True, "n": "10"},
        {"workspace_name": "a", "current_sw_version": "3.9", "enforcement_enabled": False, "n": "20"},
    ]
    text = csv_context(tmp_path / "x.csv", rows)
    assert "Rows: 2" in text
    assert "workspace_name" in text
