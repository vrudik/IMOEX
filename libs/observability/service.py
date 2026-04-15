from __future__ import annotations

from libs.domain.contracts import AdminHealthSnapshot, RuntimeMetric
from libs.domain.demo_data import list_sources
from libs.domain.repository import SqlAlchemyContractMasterRepository
from libs.maintenance.service import MaintenanceService
from libs.notifications.readiness import telegram_delivery_configured, telegram_delivery_enabled, telegram_source_health
from libs.utils.db import database_available


class ObservabilityService:
    def __init__(
        self,
        repository: SqlAlchemyContractMasterRepository,
        maintenance_service: MaintenanceService | None = None,
    ) -> None:
        self.repository = repository
        self.maintenance_service = maintenance_service

    def admin_health(self) -> AdminHealthSnapshot:
        db_ok = database_available()
        sources = list_sources()
        sources.append(telegram_source_health())

        try:
            roots_count = self.repository.count_roots()
            active_signals = self.repository.count_signals(status="active")
            resolved_signals = self.repository.count_signals(status="resolved")
            invalidated_signals = self.repository.count_signals(status="invalidated")
            journal_entries = self.repository.count_journal_entries()
            scheduler_runs = self.repository.count_scheduler_runs()
            scheduler_failed_runs = self.repository.count_scheduler_runs(status="failed")
            scheduler_active_locks = self.repository.count_scheduler_locks()
            latest_scheduler_run = self.repository.get_latest_scheduler_run()
            latest_signal = self.repository.get_latest_signal()
            latest_resolution = self.repository.get_latest_resolution()
            latest_journal = self.repository.get_latest_journal_entry()
        except Exception:
            roots_count = 0
            active_signals = 0
            resolved_signals = 0
            invalidated_signals = 0
            journal_entries = 0
            scheduler_runs = 0
            scheduler_failed_runs = 0
            scheduler_active_locks = 0
            latest_scheduler_run = None
            latest_signal = None
            latest_resolution = None
            latest_journal = None

        try:
            backup_inventory = self.maintenance_service.backup_inventory() if self.maintenance_service is not None else None
        except Exception:
            backup_inventory = None

        max_source_freshness = max((item.freshness_seconds or 0) for item in sources) if sources else 0
        degraded_sources = sum(1 for item in sources if item.status.value != "ok")
        total_events = active_signals + resolved_signals + invalidated_signals
        backup_artifacts = backup_inventory.artifacts if backup_inventory is not None else 0
        backup_size_total = backup_inventory.total_size_bytes if backup_inventory is not None else 0
        metrics = [
            RuntimeMetric(
                name="source_freshness_max",
                value=float(max_source_freshness),
                unit="seconds",
                status="ok" if max_source_freshness <= 900 else "degraded",
                detail="Maximum freshness lag across configured sources.",
            ),
            RuntimeMetric(
                name="sources_degraded",
                value=float(degraded_sources),
                unit="count",
                status="ok" if degraded_sources == 0 else "degraded",
                detail="Configured source-health entries not in OK state.",
            ),
            RuntimeMetric(
                name="signal_inventory",
                value=float(total_events),
                unit="count",
                status="ok" if total_events > 0 else "degraded",
                detail="Persisted final signals across active/resolved/invalidated states.",
            ),
            RuntimeMetric(
                name="journal_coverage",
                value=float(journal_entries),
                unit="count",
                status="ok" if journal_entries > 0 else "degraded",
                detail="User or system journal entries attached to signals.",
            ),
            RuntimeMetric(
                name="scheduler_runs_total",
                value=float(scheduler_runs),
                unit="count",
                status="ok" if scheduler_runs > 0 else "degraded",
                detail="Persisted scheduler run history rows.",
            ),
            RuntimeMetric(
                name="scheduler_failed_runs_total",
                value=float(scheduler_failed_runs),
                unit="count",
                status="ok" if scheduler_failed_runs == 0 else "degraded",
                detail="Persisted failed scheduler executions.",
            ),
            RuntimeMetric(
                name="scheduler_active_locks",
                value=float(scheduler_active_locks),
                unit="count",
                status="ok" if scheduler_active_locks == 0 else "degraded",
                detail="Currently active scheduler locks in persistence.",
            ),
            RuntimeMetric(
                name="backup_artifacts",
                value=float(backup_artifacts),
                unit="count",
                status="ok" if backup_artifacts > 0 else "degraded",
                detail="SQLite backup artifacts currently available in the configured backup directory.",
            ),
            RuntimeMetric(
                name="backup_size_total",
                value=float(backup_size_total),
                unit="bytes",
                status="ok" if backup_artifacts > 0 else "degraded",
                detail="Total size of backup artifacts stored under the configured backup directory.",
            ),
            RuntimeMetric(
                name="telegram_delivery_ready",
                value=1.0 if telegram_delivery_enabled() and telegram_delivery_configured() else 0.0,
                unit="flag",
                status=(
                    "ok"
                    if telegram_delivery_enabled() and telegram_delivery_configured()
                    else "degraded"
                ),
                detail="Telegram delivery channel readiness based on enabled/configured state.",
            ),
        ]

        statuses = [metric.status for metric in metrics]
        if not db_ok:
            overall = "not_ok"
        elif "degraded" in statuses:
            overall = "degraded"
        else:
            overall = "ok"

        return AdminHealthSnapshot(
            status=overall,
            database_status="ok" if db_ok else "not_ok",
            roots_count=roots_count,
            active_signals=active_signals,
            resolved_signals=resolved_signals,
            invalidated_signals=invalidated_signals,
            journal_entries=journal_entries,
            latest_signal_at=latest_signal.generated_at if latest_signal is not None else None,
            latest_resolution_at=latest_resolution.resolved_at if latest_resolution is not None else None,
            latest_journal_at=latest_journal.created_at if latest_journal is not None else None,
            backup_artifacts=backup_artifacts,
            latest_backup_at=(
                latest_scheduler_run.finished_at
                if latest_scheduler_run is not None and latest_scheduler_run.command == "backup"
                else backup_inventory.latest_backup_at if backup_inventory is not None else None
            ),
            source_health=sources,
            metrics=metrics,
        )
