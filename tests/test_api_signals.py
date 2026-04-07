from __future__ import annotations

from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)


def test_list_signals_filters_by_root() -> None:
    response = client.get("/api/v1/signals", params={"root": "Si"})

    assert response.status_code == 200
    payload = response.json()

    assert payload
    assert all(item["root"] == "Si" for item in payload)
    assert all("skeptic_score" in item for item in payload)


def test_signal_details_returns_explanation_fields() -> None:
    listing = client.get("/api/v1/signals", params={"root": "Si"})
    assert listing.status_code == 200
    signal_id = listing.json()[0]["signal_id"]

    response = client.get(f"/api/v1/signals/{signal_id}")

    assert response.status_code == 200
    payload = response.json()

    assert payload["signal_id"] == signal_id
    assert payload["drivers"]
    assert payload["objections"]
    assert payload["skeptic_verdict"] in {"pass", "soft_fail", "reject", "human_review"}
    assert payload["skeptic_score"] >= 0
    assert "journal_entries" in payload
