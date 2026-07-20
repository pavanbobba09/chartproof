"""Contract tests for the lightweight free Vercel API."""

from fastapi.testclient import TestClient

from backend.vercel_app import app

client = TestClient(app)


def test_vercel_health_and_case_bank() -> None:
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "ok"

    response = client.get("/cases")
    assert response.status_code == 200
    cases = response.json()
    assert len(cases) == 100
    assert all("key_rationale" not in case for case in cases)
    assert sum(case["dataset_role"] == "clinical_scenario" for case in cases) == 15


def test_vercel_serves_precomputed_for_get_and_fresh_post() -> None:
    expected = client.get("/audit/sepsis_001")
    fresh = client.post("/audit/sepsis_001?fresh=true")

    assert expected.status_code == 200
    assert fresh.status_code == 200
    assert expected.json() == fresh.json()
    assert fresh.json()["source"] == "precomputed"
    assert fresh.headers["x-chartproof-mode"] == "precomputed-portfolio"


def test_vercel_training_keeps_span_guardrails() -> None:
    response = client.post(
        "/training/sepsis_001/grade",
        json={
            "verdict": "supported",
            "selected_spans": [
                {"doc_id": "not-a-document", "line_start": 1, "line_end": 1}
            ],
        },
    )

    assert response.status_code == 422
    assert "unknown document" in response.json()["detail"]


def test_vercel_rejects_path_like_case_ids() -> None:
    response = client.get("/cases/..%2F..%2Fetc%2Fpasswd")
    assert response.status_code == 404
