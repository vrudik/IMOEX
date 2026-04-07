from __future__ import annotations

from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)


def test_create_journal_entry_and_attach_it_to_signal_detail() -> None:
    listing = client.get("/api/v1/signals", params={"root": "Si"})
    assert listing.status_code == 200
    signal_id = listing.json()[0]["signal_id"]

    created = client.post(
        f"/api/v1/journal/{signal_id}",
        json={
            "kind": "thesis",
            "title": "Opening thesis",
            "note": "Consensus still favors the long bias after skeptic review.",
            "author": "tester",
        },
    )

    assert created.status_code == 200
    payload = created.json()
    assert payload["signal_id"] == signal_id
    assert payload["kind"] == "thesis"

    detail = client.get(f"/api/v1/signals/{signal_id}")
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload["journal_entries"]
    assert detail_payload["journal_entries"][-1]["title"] == "Opening thesis"
