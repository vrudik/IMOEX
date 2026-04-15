from __future__ import annotations

import time as time_module
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, Callable
from uuid import uuid4
from zoneinfo import ZoneInfo

from libs.domain.contracts import (
    AdminBackupRequest,
    AdminCleanupRequest,
    AdminMoexReferenceSyncRequest,
    AdminRecalculateRequest,
)
from libs.domain.models import SchedulerRunRecord
from libs.domain.repository import SqlAlchemyContractMasterRepository
from libs.maintenance.service import MaintenanceService
from libs.notifications.contracts import TelegramNotificationSendRequest
from libs.notifications.contracts import TelegramDeliverySourceKind
from libs.notifications.service import TelegramNotificationService
from libs.pipeline.service import PipelineService
from libs.reference.service import MoexReferenceService
from libs.scheduler.contracts import (
    ScheduleExecutionItem,
    ScheduleExecutionResult,
    SchedulerLeaderSnapshot,
    SchedulerLoopIteration,
    SchedulerLoopResult,
    SchedulePlan,
    ScheduledJobSnapshot,
    ScheduledJobSpec,
    SchedulerRunHistoryEntry,
)
from libs.utils.config import settings


def default_job_specs(*, timezone: str) -> list[ScheduledJobSpec]:
    return [
        ScheduledJobSpec(
            job_id="reference-sync-morning",
            command="reference-sync",
            description="Refresh MOEX reference/calendar snapshot before the main signal cycle.",
            timezone=timezone,
            hour=8,
            minute=45,
            weekdays=["mon", "tue", "wed", "thu", "fri"],
            payload={"sync_calendar": True, "sync_contracts": True},
        ),
        ScheduledJobSpec(
            job_id="recalculate-open",
            command="recalculate",
            description="Materialize baseline signals for the active root universe after the morning sync.",
            timezone=timezone,
            hour=9,
            minute=5,
            weekdays=["mon", "tue", "wed", "thu", "fri"],
            payload={"resolve_due": True},
        ),
        ScheduledJobSpec(
            job_id="telegram-open-brief",
            command="notify-telegram",
            description="Send the opening signal alert to the configured Telegram chat.",
            timezone=timezone,
            hour=9,
            minute=10,
            weekdays=["mon", "tue", "wed", "thu", "fri"],
            payload={"event_kind": "signal_open", "limit": 3},
        ),
        ScheduledJobSpec(
            job_id="telegram-midday-digest",
            command="notify-telegram",
            description="Send the midday digest using the current user delivery preferences.",
            timezone=timezone,
            hour=13,
            minute=0,
            weekdays=["mon", "tue", "wed", "thu", "fri"],
            payload={"event_kind": "digest", "limit": 3},
        ),
        ScheduledJobSpec(
            job_id="telegram-resolution-brief",
            command="notify-telegram",
            description="Send the end-of-day resolution brief for resolved signals.",
            timezone=timezone,
            hour=18,
            minute=40,
            weekdays=["mon", "tue", "wed", "thu", "fri"],
            payload={"event_kind": "resolution", "limit": 5},
        ),
        ScheduledJobSpec(
            job_id="telegram-postmortem-brief",
            command="notify-telegram",
            description="Send the post-mortem brief after the journal window closes.",
            timezone=timezone,
            hour=19,
            minute=10,
            weekdays=["mon", "tue", "wed", "thu", "fri"],
            payload={"event_kind": "post_mortem", "limit": 5},
        ),
        ScheduledJobSpec(
            job_id="backup-nightly",
            command="backup",
            description="Create a nightly operational SQLite backup artifact.",
            timezone=timezone,
            hour=23,
            minute=50,
            weekdays=[0, 1, 2, 3, 4, 5, 6],
            payload={"label": "nightly-schedule"},
        ),
        ScheduledJobSpec(
            job_id="cleanup-nightly",
            command="cleanup",
            description="Purge aged operational records according to the default retention window.",
            timezone=timezone,
            hour=23,
            minute=55,
            weekdays=[0, 1, 2, 3, 4, 5, 6],
            payload={"retention_days": 30},
        ),
    ]


class SchedulerService:
    def __init__(
        self,
        *,
        repository: SqlAlchemyContractMasterRepository,
        pipeline_service: PipelineService,
        maintenance_service: MaintenanceService,
        telegram_notification_service: TelegramNotificationService,
        reference_service: MoexReferenceService,
        sleep_fn: Callable[[float], None] | None = None,
    ) -> None:
        self.repository = repository
        self.pipeline_service = pipeline_service
        self.maintenance_service = maintenance_service
        self.telegram_notification_service = telegram_notification_service
        self.reference_service = reference_service
        self.sleep_fn = sleep_fn or time_module.sleep

    def plan(self, *, as_of: datetime | None = None) -> SchedulePlan:
        effective_as_of = as_of.astimezone(UTC) if as_of is not None else datetime.now(UTC)
        timezone = self._timezone_name()
        jobs = [
            self._snapshot_for_job(spec, as_of=effective_as_of)
            for spec in self._job_specs()
        ]
        jobs.sort(key=lambda item: (item.next_run_at or item.scheduled_for or effective_as_of, item.job_id))
        return SchedulePlan(
            generated_at=datetime.now(UTC),
            as_of=effective_as_of,
            timezone=timezone,
            jobs=jobs,
        )

    def list_run_history(
        self,
        *,
        job_id: str | None = None,
        limit: int = 50,
    ) -> list[SchedulerRunHistoryEntry]:
        rows = self.repository.list_recent_scheduler_runs(job_id=job_id, limit=min(max(int(limit), 1), 500))
        return [self._history_from_record(item) for item in rows]

    def export_run_history(
        self,
        *,
        export_format: str = "jsonl",
        job_id: str | None = None,
        limit: int = 200,
    ) -> str:
        rows = self.list_run_history(job_id=job_id, limit=limit)
        fmt = export_format.strip().lower()
        if fmt == "csv":
            header = [
                "run_id",
                "job_id",
                "command",
                "trigger_mode",
                "idempotency_key",
                "status",
                "detail",
                "scheduled_for",
                "started_at",
                "finished_at",
            ]
            lines = [",".join(header)]
            for row in rows:
                values = [
                    row.run_id,
                    row.job_id,
                    row.command,
                    row.trigger_mode,
                    row.idempotency_key,
                    row.status,
                    (row.detail or "").replace('"', '""'),
                    row.scheduled_for.isoformat() if row.scheduled_for is not None else "",
                    row.started_at.isoformat(),
                    row.finished_at.isoformat() if row.finished_at is not None else "",
                ]
                lines.append(",".join(f'"{item}"' for item in values))
            return "\n".join(lines)
        import json

        return "\n".join(json.dumps(item.model_dump(mode="json"), ensure_ascii=False) for item in rows)

    def leader_status(
        self,
        *,
        as_of: datetime | None = None,
        owner_id: str | None = None,
    ) -> SchedulerLeaderSnapshot:
        effective_as_of = as_of.astimezone(UTC) if as_of is not None else datetime.now(UTC)
        row = self.repository.get_scheduler_lock(self._leader_lock_key())
        expires_at = self._coerce_utc(row.expires_at) if row is not None else None
        acquired_at = self._coerce_utc(row.acquired_at) if row is not None else None
        if row is None or expires_at is None or expires_at < effective_as_of:
            return SchedulerLeaderSnapshot(
                lock_key=self._leader_lock_key(),
                is_leader=False,
                lease_seconds=self._leader_lease_seconds(),
                detail="No active scheduler leader lease.",
            )
        is_leader = bool(owner_id and row.owner_id == owner_id)
        return SchedulerLeaderSnapshot(
            lock_key=row.lock_key,
            is_leader=is_leader,
            owner_id=row.owner_id,
            acquired_at=acquired_at,
            expires_at=expires_at,
            lease_seconds=self._leader_lease_seconds(),
            detail="Active scheduler leader lease is present.",
        )

    def run_loop(
        self,
        *,
        as_of: datetime | None = None,
        iterations: int = 1,
        dry_run: bool = False,
        sleep_seconds: float | None = None,
        owner_id: str | None = None,
    ) -> SchedulerLoopResult:
        started_at = datetime.now(UTC)
        effective_as_of = as_of.astimezone(UTC) if as_of is not None else started_at
        poll_interval = max(0.0, float(sleep_seconds if sleep_seconds is not None else settings.scheduler_poll_interval_seconds))
        requested_iterations = int(iterations)
        target_iterations = None if requested_iterations <= 0 else requested_iterations
        leader_owner = owner_id or str(uuid4())
        leader_lock_key = self._leader_lock_key()
        lease_seconds = self._leader_lease_seconds()

        if not self.repository.acquire_scheduler_lock(
            lock_key=leader_lock_key,
            job_id="scheduler-leader",
            owner_id=leader_owner,
            acquired_at=started_at,
            expires_at=started_at + timedelta(seconds=lease_seconds),
        ):
            return SchedulerLoopResult(
                started_at=started_at,
                finished_at=datetime.now(UTC),
                owner_id=leader_owner,
                iterations_requested=requested_iterations,
                iterations_completed=0,
                leader=self.leader_status(as_of=effective_as_of, owner_id=leader_owner),
                dry_run=dry_run,
                sleep_seconds=poll_interval,
                iterations=[],
            )

        iteration_results: list[SchedulerLoopIteration] = []
        try:
            index = 0
            while target_iterations is None or index < target_iterations:
                iteration_as_of = effective_as_of + timedelta(seconds=poll_interval * index)
                renewed = self.repository.renew_scheduler_lock(
                    lock_key=leader_lock_key,
                    owner_id=leader_owner,
                    acquired_at=datetime.now(UTC),
                    expires_at=datetime.now(UTC) + timedelta(seconds=lease_seconds),
                )
                if not renewed:
                    break
                result = self.run_due(as_of=iteration_as_of, dry_run=dry_run)
                iteration_results.append(
                    SchedulerLoopIteration(
                        iteration=index + 1,
                        as_of=iteration_as_of,
                        result=result,
                    )
                )
                index += 1
                if (target_iterations is None or index < target_iterations) and poll_interval > 0:
                    self.sleep_fn(poll_interval)
            finished_at = datetime.now(UTC)
            leader_snapshot = self.leader_status(as_of=finished_at, owner_id=leader_owner)
            return SchedulerLoopResult(
                started_at=started_at,
                finished_at=finished_at,
                owner_id=leader_owner,
                iterations_requested=requested_iterations,
                iterations_completed=len(iteration_results),
                leader=leader_snapshot,
                dry_run=dry_run,
                sleep_seconds=poll_interval,
                iterations=iteration_results,
            )
        finally:
            self.repository.release_scheduler_lock_owned(lock_key=leader_lock_key, owner_id=leader_owner)

    def run_due(
        self,
        *,
        as_of: datetime | None = None,
        dry_run: bool = False,
    ) -> ScheduleExecutionResult:
        plan = self.plan(as_of=as_of)
        due_jobs = [item for item in plan.jobs if item.due_now]
        items = [self._run_snapshot(item, as_of=plan.as_of, dry_run=dry_run) for item in due_jobs]
        return ScheduleExecutionResult(
            generated_at=datetime.now(UTC),
            as_of=plan.as_of,
            timezone=plan.timezone,
            dry_run=dry_run,
            due_jobs=len(due_jobs),
            executed_jobs=sum(1 for item in items if item.executed),
            items=items,
        )

    def run_job(
        self,
        job_id: str,
        *,
        as_of: datetime | None = None,
        dry_run: bool = False,
    ) -> ScheduleExecutionResult:
        plan = self.plan(as_of=as_of)
        snapshot = next((item for item in plan.jobs if item.job_id == job_id), None)
        if snapshot is None:
            item = ScheduleExecutionItem(
                job_id=job_id,
                command="unknown",
                executed=False,
                status="not_found",
                detail=f"Unknown scheduled job: {job_id}",
            )
            return ScheduleExecutionResult(
                generated_at=datetime.now(UTC),
                as_of=plan.as_of,
                timezone=plan.timezone,
                dry_run=dry_run,
                due_jobs=0,
                executed_jobs=0,
                items=[item],
            )
        item = self._run_snapshot(snapshot, as_of=plan.as_of, dry_run=dry_run, force=True)
        return ScheduleExecutionResult(
            generated_at=datetime.now(UTC),
            as_of=plan.as_of,
            timezone=plan.timezone,
            dry_run=dry_run,
            due_jobs=1 if snapshot.due_now else 0,
            executed_jobs=1 if item.executed else 0,
            items=[item],
        )

    def _run_snapshot(
        self,
        snapshot: ScheduledJobSnapshot,
        *,
        as_of: datetime,
        dry_run: bool,
        force: bool = False,
    ) -> ScheduleExecutionItem:
        trigger_mode = "manual" if force else "due"
        scheduled_for = snapshot.scheduled_for or as_of
        idempotency_key = self._idempotency_key(
            job_id=snapshot.job_id,
            trigger_mode=trigger_mode,
            scheduled_for=scheduled_for,
            as_of=as_of,
        )
        lock_key = self._lock_key(
            job_id=snapshot.job_id,
            trigger_mode=trigger_mode,
            scheduled_for=scheduled_for,
            as_of=as_of,
        )
        if not snapshot.enabled:
            return ScheduleExecutionItem(
                trigger_mode=trigger_mode,
                idempotency_key=idempotency_key,
                job_id=snapshot.job_id,
                command=snapshot.command,
                scheduled_for=snapshot.scheduled_for,
                executed=False,
                status="disabled",
                detail="Scheduled job is disabled.",
                payload=snapshot.payload,
            )
        if not force and not snapshot.due_now:
            return ScheduleExecutionItem(
                trigger_mode=trigger_mode,
                idempotency_key=idempotency_key,
                job_id=snapshot.job_id,
                command=snapshot.command,
                scheduled_for=snapshot.scheduled_for,
                executed=False,
                status="not_due",
                detail="Scheduled job is not due at the requested timestamp.",
                payload=snapshot.payload,
            )
        if dry_run:
            return ScheduleExecutionItem(
                trigger_mode=trigger_mode,
                idempotency_key=idempotency_key,
                job_id=snapshot.job_id,
                command=snapshot.command,
                scheduled_for=snapshot.scheduled_for,
                executed=False,
                status="dry_run",
                detail="Scheduled job execution skipped because dry_run=true.",
                payload=snapshot.payload,
            )

        existing = self.repository.get_scheduler_run_by_idempotency(idempotency_key)
        if existing is not None:
            if existing.status == "running" and self.repository.has_scheduler_lock(lock_key, as_of=as_of):
                return self._execution_item_from_record(
                    existing,
                    executed=False,
                    status="locked",
                    detail="Scheduled job is already running for this idempotency key.",
                )
            if existing.status != "running":
                return self._execution_item_from_record(
                    existing,
                    executed=False,
                    status="duplicate",
                    detail="Scheduled job already has persisted history for this execution key.",
                )

        started_at = datetime.now(UTC)
        if not self.repository.acquire_scheduler_lock(
            lock_key=lock_key,
            job_id=snapshot.job_id,
            owner_id=str(uuid4()),
            acquired_at=started_at,
            expires_at=started_at + timedelta(minutes=max(5, snapshot.tolerance_minutes)),
        ):
            return ScheduleExecutionItem(
                trigger_mode=trigger_mode,
                idempotency_key=idempotency_key,
                job_id=snapshot.job_id,
                command=snapshot.command,
                scheduled_for=snapshot.scheduled_for,
                started_at=started_at,
                executed=False,
                status="locked",
                detail="Unable to acquire scheduler lock for this job occurrence.",
                payload=snapshot.payload,
            )

        run_row = self.repository.start_scheduler_run(
            run_id=str(uuid4()),
            job_id=snapshot.job_id,
            command=snapshot.command,
            trigger_mode=trigger_mode,
            idempotency_key=idempotency_key,
            status="running",
            detail="Execution started.",
            payload=snapshot.payload,
            scheduled_for=snapshot.scheduled_for,
            started_at=started_at,
        )
        if run_row is None:
            self.repository.release_scheduler_lock(lock_key)
            existing = self.repository.get_scheduler_run_by_idempotency(idempotency_key)
            if existing is not None:
                return self._execution_item_from_record(
                    existing,
                    executed=False,
                    status="duplicate",
                    detail="Scheduled job already persisted history for this execution key.",
                )
            return ScheduleExecutionItem(
                trigger_mode=trigger_mode,
                idempotency_key=idempotency_key,
                job_id=snapshot.job_id,
                command=snapshot.command,
                scheduled_for=snapshot.scheduled_for,
                started_at=started_at,
                executed=False,
                status="duplicate",
                detail="Unable to create scheduler run record because it already exists.",
                payload=snapshot.payload,
            )

        try:
            result = self._execute_command(snapshot.command, payload=snapshot.payload, as_of=as_of)
            result_status, result_detail = self._result_status(
                command=snapshot.command,
                result=result,
            )
            finalized = self.repository.finish_scheduler_run(
                idempotency_key=idempotency_key,
                status=result_status,
                detail=result_detail,
                result=self._normalize(result),
                finished_at=datetime.now(UTC),
            )
            return self._execution_item_from_record(
                finalized or run_row,
                executed=True,
                status=result_status,
                detail=result_detail,
            )
        except Exception as exc:
            finalized = self.repository.finish_scheduler_run(
                idempotency_key=idempotency_key,
                status="failed",
                detail=str(exc),
                result={"error": str(exc)},
                finished_at=datetime.now(UTC),
            )
            return self._execution_item_from_record(
                finalized or run_row,
                executed=False,
                status="failed",
                detail=str(exc),
            )
        finally:
            self.repository.release_scheduler_lock(lock_key)

    def _execute_command(self, command: str, *, payload: dict[str, Any], as_of: datetime) -> Any:
        if command == "reference-sync":
            request = AdminMoexReferenceSyncRequest(
                as_of=as_of,
                from_date=self._optional_date(payload.get("from_date")),
                to_date=self._optional_date(payload.get("to_date")),
                sync_calendar=bool(payload.get("sync_calendar", True)),
                sync_contracts=bool(payload.get("sync_contracts", True)),
            )
            result = self.reference_service.sync_from_iss(
                from_date=request.from_date,
                to_date=request.to_date,
                sync_calendar=request.sync_calendar,
                sync_contracts=request.sync_contracts,
            )
            roots_synced, contracts_synced = self.repository.sync_reference_snapshot(as_of=request.as_of or as_of)
            details = list(result.details)
            details.append(f"roots_synced={roots_synced}")
            details.append(f"repository_contracts_synced={contracts_synced}")
            return result.model_copy(update={"details": details}, deep=True)
        if command == "recalculate":
            return self.pipeline_service.recalculate(
                AdminRecalculateRequest(
                    root=self._optional_str(payload.get("root")),
                    as_of=as_of,
                    resolve_due=bool(payload.get("resolve_due", True)),
                )
            )
        if command == "notify-telegram":
            return self.telegram_notification_service.send(
                TelegramNotificationSendRequest(
                    root=self._optional_str(payload.get("root")),
                    limit=int(payload.get("limit", 3)),
                    event_kind=self._optional_str(payload.get("event_kind")) or "digest",
                    delivery_source=TelegramDeliverySourceKind.SCHEDULE,
                    ignore_quiet_hours=bool(payload.get("ignore_quiet_hours", False)),
                    dry_run=bool(payload.get("dry_run", False)),
                )
            )
        if command == "backup":
            return self.maintenance_service.create_backup(
                AdminBackupRequest(label=self._optional_str(payload.get("label")))
            )
        if command == "cleanup":
            return self.maintenance_service.cleanup(
                AdminCleanupRequest(retention_days=int(payload.get("retention_days", 30)))
            )
        raise ValueError(f"Unsupported scheduled command: {command}")

    def _result_status(self, *, command: str, result: Any) -> tuple[str, str]:
        if command == "notify-telegram":
            normalized = self._normalize(result)
            delivery_status = str(normalized.get("delivery_status") or "executed")
            detail = str(normalized.get("detail") or "Telegram notification job completed.")
            return delivery_status, detail
        return "executed", "Scheduled job executed."

    def _snapshot_for_job(self, spec: ScheduledJobSpec, *, as_of: datetime) -> ScheduledJobSnapshot:
        tz = self._zoneinfo(spec.timezone)
        as_of_local = as_of.astimezone(tz)
        scheduled_for = self._latest_scheduled_at(spec, as_of_local=as_of_local)
        next_run_at = self._next_scheduled_at(spec, as_of_local=as_of_local)
        due_now = False
        if spec.enabled and scheduled_for is not None:
            lag_seconds = (as_of_local - scheduled_for).total_seconds()
            due_now = 0 <= lag_seconds < spec.tolerance_minutes * 60
        latest_run = self.repository.get_latest_scheduler_run(job_id=spec.job_id)
        return ScheduledJobSnapshot(
            job_id=spec.job_id,
            command=spec.command,
            description=spec.description,
            timezone=spec.timezone,
            enabled=spec.enabled,
            weekdays=list(spec.weekdays),
            hour=spec.hour,
            minute=spec.minute,
            tolerance_minutes=spec.tolerance_minutes,
            payload=dict(spec.payload),
            scheduled_for=scheduled_for.astimezone(UTC) if scheduled_for is not None else None,
            next_run_at=next_run_at.astimezone(UTC) if next_run_at is not None else None,
            last_run_started_at=self._coerce_utc(latest_run.started_at) if latest_run is not None else None,
            last_run_finished_at=self._coerce_utc(latest_run.finished_at) if latest_run is not None else None,
            last_run_status=latest_run.status if latest_run is not None else None,
            last_run_detail=latest_run.detail if latest_run is not None else None,
            due_now=due_now,
        )

    def _latest_scheduled_at(self, spec: ScheduledJobSpec, *, as_of_local: datetime) -> datetime | None:
        tz = self._zoneinfo(spec.timezone)
        for day_offset in range(0, 8):
            current_day = as_of_local.date() - timedelta(days=day_offset)
            if current_day.weekday() not in spec.weekdays:
                continue
            scheduled_local = datetime.combine(
                current_day,
                time(hour=spec.hour, minute=spec.minute),
                tzinfo=tz,
            )
            if scheduled_local <= as_of_local:
                return scheduled_local
        return None

    def _next_scheduled_at(self, spec: ScheduledJobSpec, *, as_of_local: datetime) -> datetime | None:
        tz = self._zoneinfo(spec.timezone)
        for day_offset in range(0, 15):
            current_day = as_of_local.date() + timedelta(days=day_offset)
            if current_day.weekday() not in spec.weekdays:
                continue
            scheduled_local = datetime.combine(
                current_day,
                time(hour=spec.hour, minute=spec.minute),
                tzinfo=tz,
            )
            if scheduled_local > as_of_local:
                return scheduled_local
        return None

    def _job_specs(self) -> list[ScheduledJobSpec]:
        configured = settings.scheduler_jobs
        timezone = self._timezone_name()
        if configured:
            specs = [
                ScheduledJobSpec.model_validate(item | {"timezone": str(item.get("timezone") or timezone)})
                for item in configured
            ]
        else:
            specs = default_job_specs(timezone=timezone)
        scheduler_enabled = bool(settings.scheduler_enabled)
        specs = [
            spec.model_copy(update={"enabled": bool(spec.enabled and scheduler_enabled)}, deep=True)
            for spec in specs
        ]
        return sorted(specs, key=lambda item: (item.hour, item.minute, item.job_id))

    def _timezone_name(self) -> str:
        raw = (settings.scheduler_timezone or "Europe/Moscow").strip() or "Europe/Moscow"
        try:
            ZoneInfo(raw)
        except Exception:
            return "Europe/Moscow"
        return raw

    def _leader_lock_key(self) -> str:
        raw = (settings.scheduler_leader_lock_key or "scheduler:leader").strip()
        return raw or "scheduler:leader"

    def _leader_lease_seconds(self) -> int:
        return max(10, int(settings.scheduler_leader_lease_seconds))

    def _zoneinfo(self, value: str) -> ZoneInfo:
        try:
            return ZoneInfo(value)
        except Exception:
            return ZoneInfo("Europe/Moscow")

    def _idempotency_key(
        self,
        *,
        job_id: str,
        trigger_mode: str,
        scheduled_for: datetime,
        as_of: datetime,
    ) -> str:
        if trigger_mode == "due":
            return f"{job_id}:due:{scheduled_for.astimezone(UTC).isoformat()}"
        return f"{job_id}:manual:{as_of.astimezone(UTC).isoformat()}"

    def _lock_key(
        self,
        *,
        job_id: str,
        trigger_mode: str,
        scheduled_for: datetime,
        as_of: datetime,
    ) -> str:
        if trigger_mode == "due":
            return f"{job_id}:due:{scheduled_for.astimezone(UTC).isoformat()}"
        return f"{job_id}:manual:{as_of.astimezone(UTC).isoformat()}"

    def _execution_item_from_record(
        self,
        row: SchedulerRunRecord,
        *,
        executed: bool,
        status: str | None = None,
        detail: str | None = None,
    ) -> ScheduleExecutionItem:
        history = self._history_from_record(row)
        return ScheduleExecutionItem(
            run_id=history.run_id,
            trigger_mode=history.trigger_mode,
            idempotency_key=history.idempotency_key,
            job_id=history.job_id,
            command=history.command,
            scheduled_for=history.scheduled_for,
            started_at=history.started_at,
            finished_at=history.finished_at,
            executed=executed,
            status=status or history.status,
            detail=detail or history.detail,
            payload=history.payload,
            result=history.result,
        )

    def _history_from_record(self, row: SchedulerRunRecord) -> SchedulerRunHistoryEntry:
        return SchedulerRunHistoryEntry(
            run_id=row.run_id,
            job_id=row.job_id,
            command=row.command,
            trigger_mode=row.trigger_mode,
            idempotency_key=row.idempotency_key,
            status=row.status,
            detail=row.detail,
            payload=self._parse_blob(row.payload_blob),
            result=self._parse_blob(row.result_blob) if row.result_blob else None,
            scheduled_for=self._coerce_utc(row.scheduled_for),
            started_at=self._coerce_utc(row.started_at) or datetime.now(UTC),
            finished_at=self._coerce_utc(row.finished_at),
        )

    def _optional_str(self, value: object) -> str | None:
        if value in (None, ""):
            return None
        return str(value)

    def _optional_date(self, value: object) -> date | None:
        if value in (None, ""):
            return None
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        return date.fromisoformat(str(value))

    def _parse_blob(self, value: str | None) -> dict[str, Any]:
        if not value:
            return {}
        try:
            import json

            parsed = json.loads(value)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _coerce_utc(self, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def _normalize(self, value: Any) -> dict[str, Any]:
        if hasattr(value, "model_dump"):
            return value.model_dump(mode="json")
        if isinstance(value, dict):
            return {str(key): self._normalize(item) if hasattr(item, "model_dump") else item for key, item in value.items()}
        return {"value": value}
