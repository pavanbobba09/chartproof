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


def test_internal_error_details_are_not_leaked(monkeypatch) -> None:
    """500 bodies must never echo exception text (paths, config, secrets)."""
    import backend.app as app_module

    def _boom(case_id: str, *, fresh: bool = False):
        raise RuntimeError("db connect failed: /fake/internal/path/secret.db")

    monkeypatch.setattr(app_module, "run_audit", _boom)
    res = client.post("/audit/sepsis_001")
    assert res.status_code == 500
    detail = res.json()["detail"]
    assert "secret.db" not in detail
    assert "/fake/internal" not in detail
    assert "error_id=" in detail
