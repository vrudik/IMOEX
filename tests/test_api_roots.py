from __future__ import annotations

from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)


def test_list_roots_returns_seeded_universe() -> None:
    response = client.get("/api/v1/roots")

    assert response.status_code == 200
    payload = response.json()

    assert len(payload) >= 3
    assert payload[0]["root_code"] == "Si"
    assert "liquidity_score" in payload[0]
    assert "universe_status" in payload[0]


def test_root_deep_dive_returns_contract_context() -> None:
    response = client.get("/api/v1/roots/Si/deep-dive")

    assert response.status_code == 200
    payload = response.json()

    assert payload["root"]["root_code"] == "Si"
    assert payload["continuous_series"]["active_contract"] == "SiM6"
    assert payload["active_signals"]
    assert payload["active_signals"][0]["skeptic_verdict"] in {"pass", "soft_fail", "reject", "human_review"}
    assert "skeptic_score" in payload["active_signals"][0]
    assert payload["continuous_series"]["back_adjustment_method"] == "difference_on_roll"
    assert len(payload["feature_snapshots"]) == 4
    assert len(payload["analyst_outputs"]) == 16
    assert len(payload["skeptic_reviews"]) == 4
    assert payload["root"]["universe_status"] in {"selected", "watchlist", "excluded"}
