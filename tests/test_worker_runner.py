from __future__ import annotations

import json
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from apps.worker.runner import main
from libs.domain.repository import SqlAlchemyContractMasterRepository
from libs.domain.service import get_contract_master_service
from libs.reference.service import get_moex_reference_service
from libs.utils.config import settings
from libs.utils.db import get_engine, get_session_factory


def _prepare_runtime(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "worker.db"
    backup_path = tmp_path / "backups"
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{database_path.as_posix()}")
    monkeypatch.setattr(settings, "backups_dir", backup_path.as_posix())
    get_moex_reference_service.cache_clear()
    get_contract_master_service.cache_clear()
    get_engine.cache_clear()


def _run_cli(args: list[str]) -> dict:
    buffer = StringIO()
    with redirect_stdout(buffer):
        exit_code = main(args)
    assert exit_code == 0
    return json.loads(buffer.getvalue())


def test_worker_recalculate_outputs_pipeline_summary(tmp_path: Path, monkeypatch) -> None:
    _prepare_runtime(tmp_path, monkeypatch)

    payload = _run_cli(["recalculate", "--root", "Si"])

    assert payload["roots_processed"] == 1
    assert payload["signals_built"] >= 1
    assert "details" in payload


def test_worker_notify_telegram_supports_dry_run(tmp_path: Path, monkeypatch) -> None:
    _prepare_runtime(tmp_path, monkeypatch)

    payload = _run_cli(["notify-telegram", "--root", "Si", "--event-kind", "resolution", "--dry-run"])

    assert payload["delivered"] is False
    assert payload["delivery_status"] == "dry_run"
    assert payload["preview"]["root"] == "Si"
    assert payload["preview"]["event_kind"] == "resolution"


def test_worker_reference_sync_updates_local_contract_master(tmp_path: Path, monkeypatch) -> None:
    _prepare_runtime(tmp_path, monkeypatch)

    def _contracts_payload(self) -> dict:
        return {
            "securities": {
                "columns": ["SECID", "ASSETCODE", "LASTTRADEDATE", "MATDATE", "MINSTEP", "LOTSIZE", "FACEUNIT"],
                "data": [["SiZ6", "Si", "2026-12-16", "2026-12-18", 1.0, 1, "RUB"]],
            }
        }

    def _calendar_payload(self, *, from_date=None, to_date=None) -> dict:
        return {
            "dates": {
                "columns": ["TRADEDATE", "TRADINGDAY", "ISWEEKENDSESSION"],
                "data": [["2026-04-04", "2026-04-06", 1]],
            }
        }

    monkeypatch.setattr("libs.reference.iss.MoexIssClient.fetch_contracts_payload", _contracts_payload)
    monkeypatch.setattr("libs.reference.iss.MoexIssClient.fetch_calendar_payload", _calendar_payload)

    payload = _run_cli(
        [
            "reference-sync",
            "--as-of",
            "2026-04-07T12:00:00Z",
            "--from",
            "2026-04-01",
            "--to",
            "2026-04-07",
        ]
    )

    assert payload["source"] == "moex_iss"
    assert payload["contracts_synced"] == 1
    assert any(detail == "roots_synced=3" for detail in payload["details"])

    stored = SqlAlchemyContractMasterRepository(get_session_factory()).get_contract_meta("SiZ6")
    assert stored is not None
    assert stored.last_trade_date.isoformat() == "2026-12-16"


def test_worker_schedule_plan_exposes_due_jobs(tmp_path: Path, monkeypatch) -> None:
    _prepare_runtime(tmp_path, monkeypatch)
    monkeypatch.setattr(settings, "scheduler_timezone", "Europe/Moscow")
    monkeypatch.setattr(settings, "scheduler_jobs_json", "[]")

    payload = _run_cli(["schedule-plan", "--as-of", "2026-04-07T06:12:00Z"])

    assert payload["timezone"] == "Europe/Moscow"
    assert any(item["job_id"] == "telegram-open-brief" and item["due_now"] is True for item in payload["jobs"])
    assert any(item["job_id"] == "telegram-resolution-brief" and item["payload"]["event_kind"] == "resolution" for item in payload["jobs"])


def test_worker_schedule_leader_reports_no_active_owner_by_default(tmp_path: Path, monkeypatch) -> None:
    _prepare_runtime(tmp_path, monkeypatch)
    monkeypatch.setattr(settings, "scheduler_timezone", "Europe/Moscow")
    monkeypatch.setattr(settings, "scheduler_jobs_json", "[]")

    payload = _run_cli(["schedule-leader", "--as-of", "2026-04-07T06:12:00Z"])

    assert payload["is_leader"] is False
    assert payload["owner_id"] is None


def test_worker_run_schedule_supports_dry_run(tmp_path: Path, monkeypatch) -> None:
    _prepare_runtime(tmp_path, monkeypatch)
    monkeypatch.setattr(settings, "scheduler_timezone", "Europe/Moscow")
    monkeypatch.setattr(settings, "scheduler_jobs_json", "[]")

    payload = _run_cli(["run-schedule", "--as-of", "2026-04-07T06:12:00Z", "--dry-run"])

    assert payload["dry_run"] is True
    assert payload["due_jobs"] >= 1
    assert payload["executed_jobs"] == 0
    assert all(item["status"] == "dry_run" for item in payload["items"])


def test_worker_run_schedule_loop_supports_leader_loop_dry_run(tmp_path: Path, monkeypatch) -> None:
    _prepare_runtime(tmp_path, monkeypatch)
    monkeypatch.setattr(settings, "scheduler_timezone", "Europe/Moscow")
    monkeypatch.setattr(settings, "scheduler_jobs_json", "[]")

    payload = _run_cli(
        [
            "run-schedule-loop",
            "--as-of",
            "2026-04-07T06:12:00Z",
            "--iterations",
            "2",
            "--sleep-seconds",
            "0",
            "--owner-id",
            "worker-leader",
            "--dry-run",
        ]
    )

    assert payload["owner_id"] == "worker-leader"
    assert payload["iterations_requested"] == 2
    assert payload["iterations_completed"] == 2
    assert payload["leader"]["is_leader"] is True


def test_worker_export_schedule_runs_returns_jsonl_payload(tmp_path: Path, monkeypatch) -> None:
    _prepare_runtime(tmp_path, monkeypatch)
    monkeypatch.setattr(settings, "scheduler_timezone", "Europe/Moscow")
    monkeypatch.setattr(settings, "scheduler_jobs_json", "[]")

    _run_cli(["run-schedule", "--as-of", "2026-04-07T06:12:00Z"])
    payload = _run_cli(["export-schedule-runs", "--export-format", "jsonl", "--limit", "5"])

    assert payload["export_format"] == "jsonl"
    assert payload["content"]


def test_worker_notify_telegram_alerts_supports_dry_run(tmp_path: Path, monkeypatch) -> None:
    _prepare_runtime(tmp_path, monkeypatch)

    payload = _run_cli(["notify-telegram-alerts", "--dry-run"])

    assert payload["delivered"] is False
    assert payload["delivery_status"] == "dry_run"
    assert "IMOEX Ops Alerts" in payload["preview"]["message"]
