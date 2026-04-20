from __future__ import annotations

from fastapi.testclient import TestClient


def test_list_signals_filters_by_root(client: TestClient) -> None:
    response = client.get("/api/v1/signals", params={"root": "Si"})

    assert response.status_code == 200
    payload = response.json()

    assert payload
    assert all(item["root"] == "Si" for item in payload)
    assert all("skeptic_score" in item for item in payload)
    assert all("workflow_state" in item for item in payload)


def test_signal_details_returns_explanation_fields(client: TestClient) -> None:
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
    assert "resolution" in payload
    assert payload["workflow_state"] == "watching"


def test_signal_workflow_state_can_be_updated_via_api(client: TestClient) -> None:
    listing = client.get("/api/v1/signals", params={"root": "Si"})
    assert listing.status_code == 200
    signal_id = listing.json()[0]["signal_id"]

    response = client.post(
        f"/api/v1/signals/{signal_id}/workflow-state",
        json={"workflow_state": "escalate"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["signal_id"] == signal_id
    assert payload["workflow_state"] == "escalate"

    detail = client.get(f"/api/v1/signals/{signal_id}")
    assert detail.status_code == 200
    assert detail.json()["workflow_state"] == "escalate"
