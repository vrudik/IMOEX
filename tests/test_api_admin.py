from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import update

from libs.domain.models import (
    AnalystOutputRecord,
    FeatureSnapshotRecord,
    FinalSignalRecord,
    SignalResolutionRecord,
    SkepticReviewRecord,
    SourceQualityCheckRecord,
    UserJournalEntryRecord,
)
from libs.reference.service import get_moex_reference_service
from libs.utils.db import get_session_factory


def test_admin_recalculate_builds_and_resolves_due_signals(client: TestClient) -> None:
    baseline = client.get("/api/v1/signals", params={"root": "Si"})
    assert baseline.status_code == 200
    payload = baseline.json()
    assert payload

    generated_at = datetime.fromisoformat(payload[0]["generated_at"].replace("Z", "+00:00"))
    as_of = (generated_at + timedelta(days=40)).astimezone(UTC).isoformat()

    response = client.post(
        "/api/v1/admin/recalculate",
        json={
            "root": "Si",
            "as_of": as_of,
            "resolve_due": True,
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["roots_processed"] == 1
    assert result["signals_built"] >= 1
    assert result["signals_resolved"] >= 1

    resolved = client.get("/api/v1/signals", params={"root": "Si", "status": "resolved"})
    assert resolved.status_code == 200
    resolved_payload = resolved.json()
    assert resolved_payload
    assert all(item["status"] == "resolved" for item in resolved_payload)

    detail = client.get(f"/api/v1/signals/{resolved_payload[0]['signal_id']}")
    assert detail.status_code == 200
    detail_payload = detail.json()
    assert detail_payload["resolution"] is not None
    assert detail_payload["resolution"]["outcome"] in {"win", "loss", "neutral", "expired"}


def test_admin_replay_returns_evaluation_report(client: TestClient) -> None:
    listing = client.get("/api/v1/signals", params={"root": "Si"})
    assert listing.status_code == 200
    payload = listing.json()
    assert payload

    generated_at = datetime.fromisoformat(payload[0]["generated_at"].replace("Z", "+00:00"))
    as_of = (generated_at + timedelta(days=40)).astimezone(UTC).isoformat()

    response = client.post(
        "/api/v1/admin/replay",
        json={
            "root": "Si",
            "as_of": as_of,
            "top_k": 3,
            "limit": 100,
        },
    )

    assert response.status_code == 200
    result = response.json()
    assert result["recalculation"]["roots_processed"] == 1
    assert result["evaluation_report"]["overall"]["resolved_signals"] >= 1
    assert result["evaluation_report"]["slices"]


def test_admin_health_returns_operational_snapshot(client: TestClient) -> None:
    bootstrap = client.get("/api/v1/signals", params={"root": "Si"})
    assert bootstrap.status_code == 200

    response = client.get("/api/v1/admin/health")
    assert response.status_code == 200
    payload = response.json()

    assert payload["database_status"] in {"ok", "not_ok"}
    assert payload["roots_count"] >= 1
    assert "metrics" in payload and payload["metrics"]
    assert any(item["name"] == "signal_inventory" for item in payload["metrics"])
    assert any(item["name"] == "backup_artifacts" for item in payload["metrics"])
    assert any(item["name"] == "telegram_delivery_ready" for item in payload["metrics"])
    assert any(item["name"] == "scheduler_runs_total" for item in payload["metrics"])
    assert any(item["name"] == "scheduler_active_locks" for item in payload["metrics"])
    assert payload["source_health"]


def test_admin_backup_creates_sqlite_snapshot_and_health_reflects_it(client: TestClient) -> None:
    bootstrap = client.get("/api/v1/signals", params={"root": "Si"})
    assert bootstrap.status_code == 200

    response = client.post("/api/v1/admin/backup", json={"label": "manual smoke"})
    assert response.status_code == 200
    payload = response.json()

    assert payload["backup_path"].endswith(".sqlite3")
    assert payload["size_bytes"] > 0

    health = client.get("/api/v1/admin/health")
    assert health.status_code == 200
    health_payload = health.json()
    assert health_payload["backup_artifacts"] >= 1
    assert health_payload["latest_backup_at"] is not None
    assert any(item["name"] == "backup_artifacts" and item["value"] >= 1 for item in health_payload["metrics"])


def test_admin_cleanup_purges_old_operational_records(client: TestClient) -> None:
    listing = client.get("/api/v1/signals", params={"root": "Si"})
    assert listing.status_code == 200
    signal_id = listing.json()[0]["signal_id"]

    created = client.post(
        f"/api/v1/journal/{signal_id}",
        json={
            "kind": "risk_note",
            "title": "Cleanup target",
            "note": "Aged journal entry for retention test.",
            "author": "tester",
        },
    )
    assert created.status_code == 200

    generated_at = datetime.fromisoformat(listing.json()[0]["generated_at"].replace("Z", "+00:00"))
    as_of = (generated_at + timedelta(days=45)).astimezone(UTC).isoformat()
    recalc = client.post(
        "/api/v1/admin/recalculate",
        json={
            "root": "Si",
            "as_of": as_of,
            "resolve_due": True,
        },
    )
    assert recalc.status_code == 200

    cutoff_time = datetime.now(UTC) - timedelta(days=90)
    with get_session_factory()() as session:
        session.add(
            SourceQualityCheckRecord(
                provider_a="moex",
                provider_b="finam",
                contract="SiM6",
                from_ts=cutoff_time - timedelta(minutes=5),
                till_ts=cutoff_time,
                count_a=10,
                count_b=10,
                overlap_count=10,
                missing_in_a=0,
                missing_in_b=0,
                mismatch_ohlc=0,
                mismatch_volume=0,
                mismatch_rate_overlap=0.0,
                created_at=cutoff_time,
            )
        )
        for model in (
            FeatureSnapshotRecord,
            AnalystOutputRecord,
            SkepticReviewRecord,
            FinalSignalRecord,
            SignalResolutionRecord,
            UserJournalEntryRecord,
        ):
            session.execute(update(model).values(created_at=cutoff_time))
        session.commit()

    response = client.post("/api/v1/admin/cleanup", json={"retention_days": 30})
    assert response.status_code == 200
    payload = response.json()

    assert payload["retention_days"] == 30
    assert payload["total_deleted"] >= 1
    assert any(detail.startswith("quality_checks=") for detail in payload["details"])


def test_admin_moex_reference_sync_updates_reference_layer_and_repository(
    client: TestClient,
    monkeypatch,
) -> None:
    get_moex_reference_service.cache_clear()

    def _contracts_payload(self) -> dict:
        return {
            "securities": {
                "columns": ["SECID", "ASSETCODE", "LASTTRADEDATE", "MATDATE", "MINSTEP", "LOTSIZE", "FACEUNIT"],
                "data": [
                    ["SiZ6", "Si", "2026-12-16", "2026-12-18", 1.0, 1, "RUB"],
                ],
            }
        }

    def _calendar_payload(self, *, from_date=None, to_date=None) -> dict:
        return {
            "dates": {
                "columns": ["TRADEDATE", "TRADINGDAY", "ISWEEKENDSESSION"],
                "data": [
                    ["2026-04-04", "2026-04-06", 1],
                ],
            }
        }

    monkeypatch.setattr("libs.reference.iss.MoexIssClient.fetch_contracts_payload", _contracts_payload)
    monkeypatch.setattr("libs.reference.iss.MoexIssClient.fetch_calendar_payload", _calendar_payload)

    response = client.post(
        "/api/v1/admin/moex-reference-sync",
        json={
            "as_of": "2026-04-07T12:00:00Z",
            "from_date": "2026-04-01",
            "to_date": "2026-04-07",
            "sync_calendar": True,
            "sync_contracts": True,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["source"] == "moex_iss"
    assert payload["contracts_synced"] == 1
    assert payload["calendar_days_synced"] == 1
    assert any(detail == "roots_synced=3" for detail in payload["details"])

    from libs.domain.repository import SqlAlchemyContractMasterRepository

    stored = SqlAlchemyContractMasterRepository(get_session_factory()).get_contract_meta("SiZ6")
    assert stored is not None
    assert stored.last_trade_date.isoformat() == "2026-12-16"
