from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient


def test_quality_evaluation_returns_metrics_for_resolved_signals(client: TestClient) -> None:
    listing = client.get("/api/v1/signals", params={"root": "Si"})
    assert listing.status_code == 200
    payload = listing.json()
    assert payload

    generated_at = datetime.fromisoformat(payload[0]["generated_at"].replace("Z", "+00:00"))
    as_of = (generated_at + timedelta(days=40)).astimezone(UTC).isoformat()
    recalc = client.post(
        "/api/v1/admin/recalculate",
        json={
            "root": "Si",
            "as_of": as_of,
            "resolve_due": True,
        },
    )
    assert recalc.status_code == 200

    response = client.get("/api/v1/quality/evaluation", params={"root": "Si", "top_k": 3})
    assert response.status_code == 200
    summary = response.json()

    assert summary["resolved_signals"] >= 1
    assert summary["brier_score"] is not None
    assert summary["log_loss"] is not None
    assert summary["top_k_precision"] is not None
    assert len(summary["calibration_bins"]) == 5


def test_quality_evaluation_report_returns_regime_slices(client: TestClient) -> None:
    listing = client.get("/api/v1/signals", params={"root": "Si"})
    assert listing.status_code == 200
    payload = listing.json()
    assert payload

    generated_at = datetime.fromisoformat(payload[0]["generated_at"].replace("Z", "+00:00"))
    as_of = (generated_at + timedelta(days=40)).astimezone(UTC).isoformat()
    recalc = client.post(
        "/api/v1/admin/recalculate",
        json={
            "root": "Si",
            "as_of": as_of,
            "resolve_due": True,
        },
    )
    assert recalc.status_code == 200

    response = client.get("/api/v1/quality/evaluation-report", params={"root": "Si", "top_k": 3})
    assert response.status_code == 200
    report = response.json()

    assert report["overall"]["resolved_signals"] >= 1
    assert report["slices"]
    assert any(item["slice_key"] in {"root", "horizon", "skeptic_verdict", "direction_final"} for item in report["slices"])


def test_quality_shadow_compare_persists_check(client: TestClient) -> None:
    response = client.post(
        "/api/v1/quality/shadow-compare",
        json={
            "provider_a": "moex",
            "provider_b": "finam",
            "contract": "SiM6",
            "bars_a": [
                {
                    "provider": "moex",
                    "root": "Si",
                    "contract": "SiM6",
                    "timeframe": "1m",
                    "open": 100.0,
                    "high": 101.0,
                    "low": 99.5,
                    "close": 100.5,
                    "volume": 1000.0,
                    "start_at": "2026-04-07T10:00:00Z",
                    "end_at": "2026-04-07T10:01:00Z",
                },
                {
                    "provider": "moex",
                    "root": "Si",
                    "contract": "SiM6",
                    "timeframe": "1m",
                    "open": 100.5,
                    "high": 101.5,
                    "low": 100.0,
                    "close": 101.0,
                    "volume": 1100.0,
                    "start_at": "2026-04-07T10:01:00Z",
                    "end_at": "2026-04-07T10:02:00Z",
                },
            ],
            "bars_b": [
                {
                    "provider": "finam",
                    "root": "Si",
                    "contract": "SiM6",
                    "timeframe": "1m",
                    "open": 100.0,
                    "high": 101.0,
                    "low": 99.5,
                    "close": 100.5,
                    "volume": 1000.0,
                    "start_at": "2026-04-07T10:00:00Z",
                    "end_at": "2026-04-07T10:01:00Z",
                },
                {
                    "provider": "finam",
                    "root": "Si",
                    "contract": "SiM6",
                    "timeframe": "1m",
                    "open": 100.6,
                    "high": 101.5,
                    "low": 100.0,
                    "close": 101.0,
                    "volume": 1100.0,
                    "start_at": "2026-04-07T10:01:00Z",
                    "end_at": "2026-04-07T10:02:00Z",
                },
            ],
            "persist": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()

    assert payload["provider_a"] == "moex"
    assert payload["provider_b"] == "finam"
    assert payload["contract"] == "SiM6"
    assert payload["count_a"] == 2
    assert payload["count_b"] == 2
    assert payload["overlap_count"] == 2
    assert payload["mismatch_ohlc"] == 1
    assert payload["mismatch_volume"] == 0
    assert payload["mismatch_rate_overlap"] == 0.5

    summary = client.get("/api/v1/quality/summary", params={"provider_a": "moex", "provider_b": "finam"})
    assert summary.status_code == 200
    summary_payload = summary.json()
    assert summary_payload["contracts_count"] >= 1
    assert summary_payload["latest_contract"] == "SiM6"
