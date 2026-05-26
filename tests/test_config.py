"""Tests for Settings."""

from __future__ import annotations

from pathlib import Path

import pytest

from csw_agent.config import Settings


def test_from_env_overrides(monkeypatch):
    monkeypatch.setenv("CSW_ENDPOINT", "https://example.com/")
    monkeypatch.setenv("CSW_VERIFY_TLS", "false")
    monkeypatch.setenv("CSW_SAFE_MODE", "0")
    monkeypatch.setenv("CSW_LOG_LEVEL", "debug")
    monkeypatch.setenv("CSW_REQUEST_TIMEOUT", "120")
    settings = Settings.from_env()
    assert settings.api_endpoint == "https://example.com/"
    assert settings.verify_tls is False
    assert settings.safe_mode is False
    assert settings.log_level == "DEBUG"
    assert settings.request_timeout_seconds == 120


def test_from_env_invalid_timeout_falls_back(monkeypatch):
    monkeypatch.setenv("CSW_REQUEST_TIMEOUT", "fast")
    settings = Settings.from_env()
    assert settings.request_timeout_seconds == 60  # default unchanged


def test_resolve_credentials_uses_default(tmp_path):
    creds = tmp_path / "creds.json"
    creds.write_text("{}")
    settings = Settings(credentials_file=creds)
    assert settings.resolve_credentials() == creds


def test_resolve_credentials_missing_raises(tmp_path):
    missing = tmp_path / "nope.json"
    settings = Settings(credentials_file=missing)
    # If a legacy candidate exists in cwd at the time the test runs, the
    # method falls back; this asserts behavior when nothing is found.
    if any(
        p.exists()
        for p in [Path("credentials.json"), Path.home() / "Downloads" / "cxtaas_api_credentials.json"]
    ):
        pytest.skip("legacy credentials present in environment")
    with pytest.raises(FileNotFoundError):
        settings.resolve_credentials()
