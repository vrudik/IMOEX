from __future__ import annotations

import argparse
import json
from datetime import UTC, date, datetime
from typing import Any

from libs.bootstrap.container import get_app_container
from libs.domain.contracts import (
    AdminBackupRequest,
    AdminCleanupRequest,
    AdminMoexReferenceSyncRequest,
    AdminRecalculateRequest,
    AdminReplayRequest,
)
from libs.notifications.contracts import TelegramNotificationSendRequest
from libs.notifications.contracts import TelegramOpsAlertSendRequest
from libs.reference.service import get_moex_reference_service


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    payload = _dispatch(args)
    print(json.dumps(_normalize(payload), ensure_ascii=False, indent=2))
    return 0


def _dispatch(args: argparse.Namespace) -> Any:
    command = args.command
    if command == "reference-sync":
        return _reference_sync(args)
    if command == "recalculate":
        return _pipeline_service().recalculate(
            AdminRecalculateRequest(
                root=args.root,
                as_of=_parse_datetime(args.as_of),
                resolve_due=not args.no_resolve,
            )
        )
    if command == "replay":
        return _pipeline_service().replay(
            AdminReplayRequest(
                root=args.root,
                as_of=_parse_datetime(args.as_of) or datetime.now(UTC),
                top_k=args.top_k,
                limit=args.limit,
            )
        )
    if command == "notify-telegram":
        return _notification_service().send(
            TelegramNotificationSendRequest(
                root=args.root,
                limit=args.limit,
                event_kind=args.event_kind,
                ignore_quiet_hours=args.ignore_quiet_hours,
                dry_run=args.dry_run,
            )
        )
    if command == "notify-telegram-alerts":
        return _ops_alert_service().send(
            TelegramOpsAlertSendRequest(
                dry_run=args.dry_run,
                stale_after_minutes=args.stale_after_minutes,
                failed_runs_limit=args.failed_runs_limit,
            )
        )
    if command == "backup":
        return _maintenance_service().create_backup(AdminBackupRequest(label=args.label))
    if command == "cleanup":
        return _maintenance_service().cleanup(AdminCleanupRequest(retention_days=args.days))
    if command == "schedule-plan":
        return _scheduler_service().plan(as_of=_parse_datetime(args.as_of))
    if command == "schedule-leader":
        return _scheduler_service().leader_status(as_of=_parse_datetime(args.as_of))
    if command == "run-schedule":
        if args.job_id:
            return _scheduler_service().run_job(
                args.job_id,
                as_of=_parse_datetime(args.as_of),
                dry_run=args.dry_run,
            )
        return _scheduler_service().run_due(
            as_of=_parse_datetime(args.as_of),
            dry_run=args.dry_run,
        )
    if command == "run-schedule-loop":
        return _scheduler_service().run_loop(
            as_of=_parse_datetime(args.as_of),
            iterations=args.iterations,
            dry_run=args.dry_run,
            sleep_seconds=args.sleep_seconds,
            owner_id=args.owner_id,
        )
    if command == "export-schedule-runs":
        return {
            "export_format": args.export_format,
            "content": _scheduler_service().export_run_history(
                export_format=args.export_format,
                job_id=args.job_id,
                limit=args.limit,
            ),
        }
    raise ValueError(f"Unsupported command: {command}")


def _reference_sync(args: argparse.Namespace) -> dict[str, Any]:
    payload = AdminMoexReferenceSyncRequest(
        as_of=_parse_datetime(args.as_of),
        from_date=_parse_date(args.from_date),
        to_date=_parse_date(args.to_date),
        sync_calendar=not args.skip_calendar,
        sync_contracts=not args.skip_contracts,
    )
    reference_service = get_moex_reference_service()
    result = reference_service.sync_from_iss(
        from_date=payload.from_date,
        to_date=payload.to_date,
        sync_calendar=payload.sync_calendar,
        sync_contracts=payload.sync_contracts,
    )
    repository = get_app_container().repository
    roots_synced, contracts_synced = repository.sync_reference_snapshot(
        as_of=payload.as_of or datetime.now(UTC),
        source=result.source,
    )
    details = list(result.details)
    details.append(f"roots_synced={roots_synced}")
    details.append(f"repository_contracts_synced={contracts_synced}")
    repository.record_reference_sync(
        as_of=payload.as_of or datetime.now(UTC),
        source=result.source,
        detail="; ".join(details),
    )
    return result.model_dump(mode="json") | {
        "details": details,
    }


def _pipeline_service():
    return get_app_container().pipeline_service


def _maintenance_service():
    return get_app_container().maintenance_service


def _notification_service():
    return get_app_container().telegram_notification_service


def _ops_alert_service():
    return get_app_container().telegram_ops_alert_service


def _scheduler_service():
    return get_app_container().scheduler_service


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m apps.worker.runner")
    subparsers = parser.add_subparsers(dest="command", required=True)

    reference_sync = subparsers.add_parser("reference-sync")
    reference_sync.add_argument("--as-of")
    reference_sync.add_argument("--from", dest="from_date")
    reference_sync.add_argument("--to", dest="to_date")
    reference_sync.add_argument("--skip-calendar", action="store_true")
    reference_sync.add_argument("--skip-contracts", action="store_true")

    recalculate = subparsers.add_parser("recalculate")
    recalculate.add_argument("--root")
    recalculate.add_argument("--as-of")
    recalculate.add_argument("--no-resolve", action="store_true")

    replay = subparsers.add_parser("replay")
    replay.add_argument("--root")
    replay.add_argument("--as-of")
    replay.add_argument("--top-k", type=int, default=5)
    replay.add_argument("--limit", type=int, default=500)

    notify = subparsers.add_parser("notify-telegram")
    notify.add_argument("--root")
    notify.add_argument("--limit", type=int, default=3)
    notify.add_argument("--event-kind", default="digest")
    notify.add_argument("--ignore-quiet-hours", action="store_true")
    notify.add_argument("--dry-run", action="store_true")

    notify_alerts = subparsers.add_parser("notify-telegram-alerts")
    notify_alerts.add_argument("--dry-run", action="store_true")
    notify_alerts.add_argument("--stale-after-minutes", type=int)
    notify_alerts.add_argument("--failed-runs-limit", type=int)

    backup = subparsers.add_parser("backup")
    backup.add_argument("--label")

    cleanup = subparsers.add_parser("cleanup")
    cleanup.add_argument("--days", type=int, default=30)

    schedule_plan = subparsers.add_parser("schedule-plan")
    schedule_plan.add_argument("--as-of")

    schedule_leader = subparsers.add_parser("schedule-leader")
    schedule_leader.add_argument("--as-of")

    run_schedule = subparsers.add_parser("run-schedule")
    run_schedule.add_argument("--as-of")
    run_schedule.add_argument("--job-id")
    run_schedule.add_argument("--dry-run", action="store_true")

    run_schedule_loop = subparsers.add_parser("run-schedule-loop")
    run_schedule_loop.add_argument("--as-of")
    run_schedule_loop.add_argument("--iterations", type=int, default=1)
    run_schedule_loop.add_argument("--sleep-seconds", type=float)
    run_schedule_loop.add_argument("--owner-id")
    run_schedule_loop.add_argument("--dry-run", action="store_true")

    export_schedule_runs = subparsers.add_parser("export-schedule-runs")
    export_schedule_runs.add_argument("--export-format", default="jsonl")
    export_schedule_runs.add_argument("--job-id")
    export_schedule_runs.add_argument("--limit", type=int, default=200)

    return parser


def _parse_datetime(value: str | None) -> datetime | None:
    if value in (None, ""):
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _parse_date(value: str | None) -> date | None:
    if value in (None, ""):
        return None
    return date.fromisoformat(value)


def _normalize(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {key: _normalize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    return value


if __name__ == "__main__":
    raise SystemExit(main())
