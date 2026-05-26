"""Tests for the persistent prompt history."""

from __future__ import annotations

from pathlib import Path

from csw_agent.dashboard.prompt_history import PromptHistory


def test_add_and_list(tmp_path: Path):
    h = PromptHistory(path=tmp_path / "history.jsonl")
    h.add("¿cuántos agentes?")
    h.add("muestra workspaces")
    listed = h.list()
    assert [e.message for e in listed] == ["muestra workspaces", "¿cuántos agentes?"]


def test_list_limit(tmp_path: Path):
    h = PromptHistory(path=tmp_path / "history.jsonl")
    for i in range(5):
        h.add(f"msg-{i}")
    assert [e.message for e in h.list(limit=2)] == ["msg-4", "msg-3"]


def test_persists_across_instances(tmp_path: Path):
    path = tmp_path / "history.jsonl"
    PromptHistory(path=path).add("hola")
    reloaded = PromptHistory(path=path)
    assert [e.message for e in reloaded.list()] == ["hola"]


def test_cap_max_entries(tmp_path: Path):
    h = PromptHistory(path=tmp_path / "history.jsonl", max_entries=3)
    for i in range(5):
        h.add(f"m{i}")
    messages = [e.message for e in h.list()]
    assert messages == ["m4", "m3", "m2"]


def test_clear(tmp_path: Path):
    h = PromptHistory(path=tmp_path / "history.jsonl")
    h.add("x")
    h.clear()
    assert h.list() == []
    # The file should still exist but be empty after clearing.
    assert (tmp_path / "history.jsonl").read_text() == ""


def test_load_skips_blank_lines(tmp_path: Path):
    path = tmp_path / "history.jsonl"
    path.write_text('{"timestamp": 1.0, "message": "a"}\n\n{"timestamp": 2.0, "message": "b"}\n')
    assert [e.message for e in PromptHistory(path=path).list()] == ["b", "a"]
