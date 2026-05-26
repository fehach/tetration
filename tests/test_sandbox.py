"""Tests for the AST sandbox."""

from __future__ import annotations

import pytest

from csw_agent.ai.sandbox import validate


def test_safe_get_call_passes():
    code = """
data, error = api_call('GET', '/sensors', params={'limit': 1})
print(data)
""".strip()
    report = validate(code)
    assert report.is_safe
    assert not report.has_destructive_intent
    assert report.violations == []


def test_post_to_readonly_endpoint_passes():
    code = "data, error = api_call('POST', '/inventory/search', json_body={'limit': 10})"
    report = validate(code)
    assert report.is_safe
    assert not report.has_destructive_intent


def test_delete_call_blocked_when_safe():
    code = "api_call('DELETE', '/sensors/abc')"
    report = validate(code)
    assert not report.is_safe
    assert report.has_destructive_intent


def test_delete_call_allowed_when_unsafe():
    code = "api_call('DELETE', '/sensors/abc')"
    report = validate(code, allow_destructive=True)
    assert report.is_safe
    assert report.has_destructive_intent


def test_destructive_post_blocked():
    code = "api_call('POST', '/applications/123/enable_enforce')"
    report = validate(code)
    assert not report.is_safe


def test_disallowed_import():
    code = "import os\nos.listdir('/')"
    report = validate(code)
    assert not report.is_safe
    assert any("import" in v for v in report.violations)


def test_open_blocked():
    code = "f = open('/etc/passwd')"
    report = validate(code)
    assert not report.is_safe


def test_dunder_access_blocked():
    code = "x = (1).__class__.__bases__[0]"
    report = validate(code)
    assert not report.is_safe


def test_getattr_blocked():
    code = "v = getattr(restclient, 'delete')('/x')"
    report = validate(code)
    assert not report.is_safe


def test_restclient_delete_blocked():
    code = "restclient.delete('/sensors/abc')"
    report = validate(code)
    assert report.has_destructive_intent
    assert not report.is_safe


def test_syntax_error_reported():
    report = validate("def broken(:")
    assert not report.is_safe
    assert any("syntax error" in v for v in report.violations)


@pytest.mark.parametrize(
    "code",
    [
        "import json\nprint(json.dumps({'a': 1}))",
        "from datetime import datetime\nprint(datetime.now())",
        "from collections import Counter\nprint(Counter([1, 1, 2]))",
    ],
)
def test_allowed_imports(code: str) -> None:
    assert validate(code).is_safe
