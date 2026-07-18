"""Graceful audit error mapping for demo hardening."""

from __future__ import annotations

from fastapi.testclient import TestClient

from backend.app import _is_rate_limit_error, app

client = TestClient(app)


def test_rate_limit_detector() -> None:
    assert _is_rate_limit_error(RuntimeError("HTTP 429 Too Many Requests"))
    assert _is_rate_limit_error(RuntimeError("rate limit exceeded"))
    assert not _is_rate_limit_error(RuntimeError("something else"))


def test_post_missing_case_404() -> None:
    res = client.post("/audit/no_such_case_xyz")
    assert res.status_code == 404
