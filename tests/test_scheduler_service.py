from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from libs.bootstrap.container import get_app_container
from libs.notifications.contracts import TelegramDeliveryEventKind, TelegramNotificationPreview, TelegramNotificationSendResult
from libs.domain.repository import SqlAlchemyContractMasterRepository
from libs.reference.service import get_moex_reference_service
from libs.utils.config import settings
from libs.utils.db import get_engine


def _prepare_runtime(tmp_path: Path, monkeypatch) -> None:
    database_path = tmp_path / "scheduler.db"
    backup_path = tmp_path / "backups"
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{database_path.as_posix()}")
    monkeypatch.setattr(settings, "backups_dir", backup_path.as_posix())
    monkeypatch.setattr(settings, "scheduler_timezone", "Europe/Moscow")
    monkeypatch.setattr(settings, "scheduler_jobs_json", "[]")
    get_app_container.cache_clear()
    get_moex_reference_service.cache_clear()
    get_engine.cache_clear()


def test_scheduler_plan_marks_due_jobs_in_local_timezone(tmp_path: Path, monkeypatch) -> None:
    _prepare_runtime(tmp_path, monkeypatch)

    service = get_app_container().scheduler_service
    plan = service.plan(as_of=datetime(2026, 4, 7, 6, 12, tzinfo=UTC))

    assert plan.timezone == "Europe/Moscow"
    due_ids = {item.job_id for item in plan.jobs if item.due_now}
    assert "telegram-open-brief" in due_ids
    assert any(item.job_id == "telegram-midday-digest" and item.payload.get("event_kind") == "digest" for item in plan.jobs)
    assert any(item.job_id == "telegram-resolution-brief" and item.payload.get("event_kind") == "resolution" for item in plan.jobs)
    assert any(item.job_id == "telegram-postmortem-brief" and item.payload.get("event_kind") == "post_mortem" for item in plan.jobs)
    assert any(item.job_id == "backup-nightly" and item.next_run_at is not None for item in plan.jobs)


def test_scheduler_run_due_supports_dry_run(tmp_path: Path, monkeypatch) -> None:
    _prepare_runtime(tmp_path, monkeypatch)

    result = get_app_container().scheduler_service.run_due(
        as_of=datetime(2026, 4, 7, 6, 12, tzinfo=UTC),
        dry_run=True,
    )

    assert result.dry_run is True
    assert result.due_jobs >= 1
    assert result.executed_jobs == 0
    assert all(item.status == "dry_run" for item in result.items)
    assert get_app_container().repository.count_scheduler_runs() == 0


def test_scheduler_can_run_single_job_by_id(tmp_path: Path, monkeypatch) -> None:
    _prepare_runtime(tmp_path, monkeypatch)

    result = get_app_container().scheduler_service.run_job(
        "recalculate-open",
        as_of=datetime(2026, 4, 7, 6, 30, tzinfo=UTC),
    )

    assert result.executed_jobs == 1
    item = result.items[0]
    assert item.job_id == "recalculate-open"
    assert item.status == "executed"
    assert item.run_id is not None
    assert item.result is not None
    assert item.result["roots_processed"] >= 1

    repo = SqlAlchemyContractMasterRepository(get_app_container().repository.session_factory)
    assert repo.count_signals(status="active") >= 1
    assert repo.count_scheduler_runs(status="executed") >= 1


def test_scheduler_can_run_telegram_job_with_event_kind(tmp_path: Path, monkeypatch) -> None:
    _prepare_runtime(tmp_path, monkeypatch)
    captured: dict[str, object] = {}

    def _send(self, payload):
        captured["event_kind"] = payload.event_kind
        captured["ignore_quiet_hours"] = payload.ignore_quiet_hours
        captured["limit"] = payload.limit
        preview = TelegramNotificationPreview(
            root="Si",
            enabled=True,
            configured=True,
            event_kind=payload.event_kind,
            quiet_hours_active=False,
            suppressed_reason=None,
            delivery_allowed=True,
            chat_id="123456",
            parse_mode="HTML",
            signal_ids=["SIG-1"],
            message="resolution brief",
            generated_at=datetime.now(UTC),
        )
        return TelegramNotificationSendResult(
            delivered=True,
            delivery_status="sent",
            root="Si",
            chat_id="123456",
            signal_ids=["SIG-1"],
            generated_at=preview.generated_at,
            preview=preview,
            provider_message_id="501",
            detail="Telegram message delivered.",
        )

    monkeypatch.setattr("libs.notifications.service.TelegramNotificationService.send", _send)

    service = get_app_container().scheduler_service
    result = service.run_job(
        "telegram-resolution-brief",
        as_of=datetime(2026, 4, 7, 15, 45, tzinfo=UTC),
    )

    assert result.executed_jobs == 1
    item = result.items[0]
    assert item.job_id == "telegram-resolution-brief"
    assert item.status == "sent"
    assert item.result is not None
    assert item.result["delivery_status"] == "sent"
    assert item.result["preview"]["event_kind"] == "resolution"
    assert captured["event_kind"] == TelegramDeliveryEventKind.RESOLUTION
    assert captured["ignore_quiet_hours"] is False
    assert captured["limit"] == 5


def test_scheduler_due_runs_are_idempotent_per_occurrence(tmp_path: Path, monkeypatch) -> None:
    _prepare_runtime(tmp_path, monkeypatch)

    service = get_app_container().scheduler_service
    first = service.run_due(as_of=datetime(2026, 4, 7, 6, 12, tzinfo=UTC))
    second = service.run_due(as_of=datetime(2026, 4, 7, 6, 12, tzinfo=UTC))

    assert first.executed_jobs >= 1
    assert second.executed_jobs == 0
    assert any(item.status == "duplicate" for item in second.items)
    assert get_app_container().repository.count_scheduler_runs(status="executed") >= 1


def test_scheduler_plan_includes_last_run_metadata(tmp_path: Path, monkeypatch) -> None:
    _prepare_runtime(tmp_path, monkeypatch)

    service = get_app_container().scheduler_service
    service.run_job("recalculate-open", as_of=datetime(2026, 4, 7, 6, 30, tzinfo=UTC))
    plan = service.plan(as_of=datetime(2026, 4, 7, 7, 0, tzinfo=UTC))

    recalc = next(item for item in plan.jobs if item.job_id == "recalculate-open")
    assert recalc.last_run_status == "executed"
    assert recalc.last_run_started_at is not None


def test_scheduler_run_history_is_listed(tmp_path: Path, monkeypatch) -> None:
    _prepare_runtime(tmp_path, monkeypatch)

    service = get_app_container().scheduler_service
    service.run_job("recalculate-open", as_of=datetime(2026, 4, 7, 6, 30, tzinfo=UTC))
    history = service.list_run_history(job_id="recalculate-open")

    assert history
    assert history[0].job_id == "recalculate-open"
    assert history[0].status == "executed"


def test_scheduler_leader_status_without_active_lease(tmp_path: Path, monkeypatch) -> None:
    _prepare_runtime(tmp_path, monkeypatch)

    leader = get_app_container().scheduler_service.leader_status(
        as_of=datetime(2026, 4, 7, 6, 0, tzinfo=UTC)
    )

    assert leader.is_leader is False
    assert leader.owner_id is None


def test_scheduler_loop_acquires_leader_and_runs_iterations(tmp_path: Path, monkeypatch) -> None:
    _prepare_runtime(tmp_path, monkeypatch)

    service = get_app_container().scheduler_service
    result = service.run_loop(
        as_of=datetime(2026, 4, 7, 6, 12, tzinfo=UTC),
        iterations=2,
        dry_run=True,
        sleep_seconds=0,
        owner_id="leader-1",
    )

    assert result.owner_id == "leader-1"
    assert result.iterations_requested == 2
    assert result.iterations_completed == 2
    assert result.leader.is_leader is True
    assert all(item.result.dry_run is True for item in result.iterations)


def test_scheduler_loop_skips_when_leader_is_already_held(tmp_path: Path, monkeypatch) -> None:
    _prepare_runtime(tmp_path, monkeypatch)

    repo = get_app_container().repository
    acquired_at = datetime.now(UTC)
    assert repo.acquire_scheduler_lock(
        lock_key=settings.scheduler_leader_lock_key,
        job_id="scheduler-leader",
        owner_id="other-owner",
        acquired_at=acquired_at,
        expires_at=acquired_at + timedelta(seconds=120),
    )

    result = get_app_container().scheduler_service.run_loop(
        as_of=datetime(2026, 4, 7, 6, 12, tzinfo=UTC),
        iterations=2,
        dry_run=True,
        sleep_seconds=0,
        owner_id="leader-2",
    )

    assert result.iterations_completed == 0
    assert result.leader.is_leader is False
    assert result.leader.owner_id == "other-owner"
