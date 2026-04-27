from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy import text

from libs.adapters.contracts import SourceRegistryEntry
from libs.adapters.registry import get_adapter_registry
from libs.bootstrap.container import get_app_container
from libs.bootstrap.modules import ModuleSpec, list_module_specs
from libs.domain.contracts import CapabilityRegistry
from libs.runtime.contracts import FeatureFlagState, RuntimeMetricsSnapshot
from libs.runtime.feature_flags import list_feature_flags
from libs.runtime.metrics import get_runtime_metrics_registry
from libs.security.admin import admin_security_state
from libs.notifications.readiness import telegram_delivery_configured, telegram_delivery_enabled, telegram_source_health
from libs.scheduler.contracts import ScheduledJobSnapshot, SchedulerLeaderSnapshot, SchedulerRunHistoryEntry
from libs.utils.config import settings
from libs.utils.db import database_available, get_engine

router = APIRouter(tags=["health"])
MetricValue = str | int | float | bool | None
BACKUP_FRESH_SECONDS = 36 * 60 * 60
PRODUCTION_LIKE_ENVIRONMENTS = {"prod", "production", "staging"}


class BootstrapState(BaseModel):
    status: str
    detail: str | None = None


class HealthResponse(BaseModel):
    status: str
    checks: dict[str, BootstrapState]


class SourceHealthResponse(BaseModel):
    provider: str
    role: str
    status: str
    detail: str
    freshness_seconds: int | None = None
    primary: bool = False


class CapabilityRegistryResponse(BaseModel):
    provider: str
    capabilities: CapabilityRegistry


class ProductReadinessCheck(BaseModel):
    key: str
    label: str
    surface: str
    severity: str
    status: str
    detail: str
    metrics: dict[str, MetricValue] = Field(default_factory=dict)


class ProductReadinessResponse(BaseModel):
    status: str
    release_gate: str
    root: str
    generated_at: datetime
    summary: str
    checks: list[ProductReadinessCheck]


@router.get("/health/live", response_model=HealthResponse)
async def live() -> HealthResponse:
    return HealthResponse(status="ok", checks={"app": BootstrapState(status="ok", detail="running")})


@router.get("/health/ready", response_model=HealthResponse)
async def ready() -> HealthResponse:
    db_ok = database_available()
    checks = {
        "db": BootstrapState(status="ok" if db_ok else "not_ok", detail="reachable" if db_ok else "unreachable"),
    }
    status = "ok" if all(v.status == "ok" for v in checks.values()) else "not_ok"
    return HealthResponse(status=status, checks=checks)


@router.get("/health/sources", response_model=list[SourceHealthResponse])
async def sources() -> list[SourceHealthResponse]:
    db_ok = database_available()
    rows = [SourceHealthResponse.model_validate(item.model_dump()) for item in get_adapter_registry().list_source_health()]
    rows.append(SourceHealthResponse.model_validate(telegram_source_health().model_dump()))
    rows.append(
        SourceHealthResponse(
            provider="database",
            role="storage",
            status="ok" if db_ok else "not_ok",
            detail="reachable" if db_ok else "unreachable",
            primary=True,
        )
    )
    return rows


@router.get("/health/capabilities", response_model=list[CapabilityRegistryResponse])
async def capabilities() -> list[CapabilityRegistryResponse]:
    registry = get_adapter_registry()
    return [
        CapabilityRegistryResponse(provider=provider, capabilities=capabilities)
        for provider, capabilities in registry.list_capabilities().items()
    ]


@router.get("/health/registry", response_model=list[SourceRegistryEntry])
async def source_registry() -> list[SourceRegistryEntry]:
    return get_adapter_registry().list_source_registry()


@router.get("/health/modules", response_model=list[ModuleSpec])
async def modules() -> list[ModuleSpec]:
    return list_module_specs()


@router.get("/health/feature-flags", response_model=list[FeatureFlagState])
async def feature_flags() -> list[FeatureFlagState]:
    return list_feature_flags()


@router.get("/health/runtime-metrics", response_model=RuntimeMetricsSnapshot)
async def runtime_metrics() -> RuntimeMetricsSnapshot:
    return get_runtime_metrics_registry().snapshot()


@router.get("/health/schedules", response_model=list[ScheduledJobSnapshot])
async def schedules() -> list[ScheduledJobSnapshot]:
    return get_app_container().scheduler_service.plan().jobs


@router.get("/health/schedule-runs", response_model=list[SchedulerRunHistoryEntry])
async def schedule_runs(job_id: str | None = None, limit: int = 50) -> list[SchedulerRunHistoryEntry]:
    return get_app_container().scheduler_service.list_run_history(
        job_id=job_id,
        limit=min(max(int(limit), 1), 200),
    )


@router.get("/health/schedule-runs/export", response_class=PlainTextResponse)
async def schedule_runs_export(
    export_format: str = "jsonl",
    job_id: str | None = None,
    limit: int = 200,
) -> PlainTextResponse:
    content = get_app_container().scheduler_service.export_run_history(
        export_format=export_format,
        job_id=job_id,
        limit=min(max(int(limit), 1), 1000),
    )
    media_type = "text/csv; charset=utf-8" if export_format.strip().lower() == "csv" else "application/x-ndjson"
    return PlainTextResponse(content=content, media_type=media_type)


@router.get("/health/scheduler-leader", response_model=SchedulerLeaderSnapshot)
async def scheduler_leader() -> SchedulerLeaderSnapshot:
    return get_app_container().scheduler_service.leader_status()


@router.get("/health/product-readiness", response_model=ProductReadinessResponse)
async def product_readiness(root: str | None = None) -> ProductReadinessResponse:
    container = get_app_container()
    generated_at = datetime.now(UTC)
    roots = container.contract_master_service.list_roots()
    selected_root = root or (roots[0].root_code if roots else "Si")
    if roots and all(item.root_code.upper() != selected_root.upper() for item in roots):
        selected_root = roots[0].root_code

    checks: list[ProductReadinessCheck] = []

    def add_check(
        *,
        key: str,
        label: str,
        surface: str,
        severity: str,
        status: str,
        detail: str,
        metrics: dict[str, MetricValue] | None = None,
    ) -> None:
        checks.append(
            ProductReadinessCheck(
                key=key,
                label=label,
                surface=surface,
                severity=severity,
                status=status,
                detail=detail,
                metrics=metrics or {},
            )
        )

    db_ok = database_available()
    add_check(
        key="database",
        label="Database availability",
        surface="storage",
        severity="required",
        status="ok" if db_ok else "not_ok",
        detail="Primary application database is reachable." if db_ok else "Primary application database is unreachable.",
    )

    _add_admin_runtime_security_check(add_check)

    admin_health_snapshot = None
    try:
        admin_health_snapshot = container.observability_service.admin_health()
    except Exception as exc:  # pragma: no cover - defensive readiness payload
        add_check(
            key="admin_health_surface",
            label="Admin health surface",
            surface="ops",
            severity="advisory",
            status="warning",
            detail=f"Admin health snapshot failed to build: {type(exc).__name__}.",
        )
    else:
        add_check(
            key="admin_health_surface",
            label="Admin health surface",
            surface="ops",
            severity="advisory",
            status="ok" if admin_health_snapshot.database_status == "ok" else "not_ok",
            detail=(
                "Admin health snapshot is available."
                if admin_health_snapshot.database_status == "ok"
                else "Admin health snapshot reports database problems."
            ),
            metrics={
                "admin_status": admin_health_snapshot.status,
                "database_status": admin_health_snapshot.database_status,
                "roots_count": admin_health_snapshot.roots_count,
            },
        )

    dashboard_enabled = any(item.name == "dashboard_ui" and item.enabled for item in list_feature_flags())
    add_check(
        key="dashboard_feature_flag",
        label="Dashboard feature flag",
        surface="routing",
        severity="required",
        status="ok" if dashboard_enabled else "not_ok",
        detail="Dashboard UI is enabled." if dashboard_enabled else "Dashboard UI is disabled, so operator surfaces are unavailable.",
    )

    dashboard_snapshot = None
    try:
        dashboard_snapshot = container.dashboard_service.build_snapshot(root=selected_root)
    except Exception as exc:  # pragma: no cover - exercised by contract tests through the response payload
        add_check(
            key="dashboard_surface",
            label="Dashboard surface",
            surface="dashboard",
            severity="required",
            status="not_ok",
            detail=f"Dashboard snapshot failed to build: {type(exc).__name__}.",
        )
    else:
        add_check(
            key="dashboard_surface",
            label="Dashboard surface",
            surface="dashboard",
            severity="required",
            status="ok",
            detail="Dashboard snapshot builds successfully.",
            metrics={
                "spotlight_signals": len(dashboard_snapshot.spotlight_signals),
                "recent_signals": len(dashboard_snapshot.recent_signals),
                "selected_root_matches": dashboard_snapshot.selected_root.upper() == selected_root.upper(),
            },
        )

    workspace_snapshot = None
    try:
        workspace_snapshot = container.dashboard_service.build_workspace_snapshot(root=selected_root)
    except Exception as exc:  # pragma: no cover - exercised by contract tests through the response payload
        add_check(
            key="workspace_surface",
            label="Workspace surface",
            surface="workspace",
            severity="required",
            status="not_ok",
            detail=f"Workspace snapshot failed to build: {type(exc).__name__}.",
        )
    else:
        add_check(
            key="workspace_surface",
            label="Workspace surface",
            surface="workspace",
            severity="required",
            status="ok",
            detail="Workspace snapshot builds with the root lane, signal lane, trust ribbon, and decision pack.",
            metrics={
                "signal_lane_count": len(workspace_snapshot.signal_lane),
                "watchlist_count": len(workspace_snapshot.watchlist),
                "focus_signal_present": workspace_snapshot.focus_signal is not None,
                "workspace_mode": workspace_snapshot.workspace_mode,
            },
        )

    if workspace_snapshot is None or workspace_snapshot.focus_signal is None:
        add_check(
            key="signal_detail_surface",
            label="Signal detail surface",
            surface="signal_detail",
            severity="advisory",
            status="warning",
            detail="No focus signal is available yet, so the full signal detail surface is not primed.",
            metrics={"focus_signal_present": False},
        )
    else:
        try:
            signal_snapshot = container.dashboard_service.build_signal_snapshot(
                signal_id=workspace_snapshot.focus_signal.signal_id
            )
        except Exception as exc:  # pragma: no cover - exercised by contract tests through the response payload
            add_check(
                key="signal_detail_surface",
                label="Signal detail surface",
                surface="signal_detail",
                severity="required",
                status="not_ok",
                detail=f"Signal detail snapshot failed to build: {type(exc).__name__}.",
            )
        else:
            status = "ok" if signal_snapshot is not None else "not_ok"
            detail = (
                "Signal detail snapshot builds successfully."
                if signal_snapshot is not None
                else "Signal detail snapshot returned no data for the focus signal."
            )
            add_check(
                key="signal_detail_surface",
                label="Signal detail surface",
                surface="signal_detail",
                severity="required",
                status=status,
                detail=detail,
                metrics={
                    "decision_log_items": len(signal_snapshot.decision_log) if signal_snapshot is not None else 0,
                    "similar_setups": len(signal_snapshot.similar_setups) if signal_snapshot is not None else 0,
                },
            )

    try:
        journal_snapshot = container.dashboard_service.build_journal_snapshot(root=selected_root, limit=40)
    except Exception as exc:  # pragma: no cover - exercised by contract tests through the response payload
        add_check(
            key="review_loop_surface",
            label="Review loop surface",
            surface="journal",
            severity="required",
            status="not_ok",
            detail=f"Journal snapshot failed to build: {type(exc).__name__}.",
        )
    else:
        add_check(
            key="review_loop_surface",
            label="Review loop surface",
            surface="journal",
            severity="required",
            status="ok",
            detail="Journal and decision-log review surfaces build successfully.",
            metrics={
                "decision_log_items": len(journal_snapshot.decision_log),
                "entries": len(journal_snapshot.entries),
                "note_templates": len(journal_snapshot.note_templates),
                "tag_suggestions": len(journal_snapshot.tag_suggestions),
            },
        )

    runtime_snapshot = None
    prompt_context = None
    if workspace_snapshot is not None:
        from apps.api.routes.dashboard import _build_council_prompt_context

        prompt_context = _build_council_prompt_context(workspace_snapshot, language="ru")
    try:
        runtime_snapshot = container.runtime_control_service.get_snapshot(prompt_context=prompt_context)
    except Exception as exc:  # pragma: no cover - exercised by contract tests through the response payload
        add_check(
            key="runtime_control_surface",
            label="Runtime control surface",
            surface="runtime",
            severity="required",
            status="not_ok",
            detail=f"Runtime control snapshot failed to build: {type(exc).__name__}.",
        )
    else:
        add_check(
            key="runtime_control_surface",
            label="Runtime control surface",
            surface="runtime",
            severity="required",
            status="ok",
            detail="Runtime control snapshot builds successfully.",
            metrics={
                "model_routes": len(runtime_snapshot.model_routes),
                "role_prompts": len(runtime_snapshot.role_prompts),
                "audit_events": len(runtime_snapshot.audit_trail),
            },
        )
        rendered_prompts = sum(1 for item in runtime_snapshot.role_prompts if item.rendered_prompt)
        prompt_templates = sum(1 for item in runtime_snapshot.role_prompts if item.prompt_template.strip())
        governance_ok = (
            len(runtime_snapshot.model_routes) >= 6
            and len(runtime_snapshot.role_prompts) >= 6
            and prompt_templates == len(runtime_snapshot.role_prompts)
            and rendered_prompts == len(runtime_snapshot.role_prompts)
        )
        add_check(
            key="runtime_prompt_governance",
            label="Council prompt governance",
            surface="council_runtime",
            severity="required",
            status="ok" if governance_ok else "not_ok",
            detail=(
                "Council role prompts are populated, rendered with live context, and visible for operator control."
                if governance_ok
                else "Some council role prompts are missing, empty, or not renderable with the current context."
            ),
            metrics={
                "model_routes": len(runtime_snapshot.model_routes),
                "role_prompts": len(runtime_snapshot.role_prompts),
                "rendered_prompts": rendered_prompts,
            },
        )

    _add_backup_readiness_check(add_check, generated_at=generated_at, admin_health=admin_health_snapshot)
    _add_scheduler_readiness_check(add_check, container=container, admin_health=admin_health_snapshot)
    _add_delivery_readiness_check(add_check)
    _add_migration_readiness_check(add_check)
    _add_restore_drill_evidence_check(add_check, generated_at=generated_at)

    if workspace_snapshot is None:
        add_check(
            key="market_data_truth",
            label="Market-data truth posture",
            surface="market_panel",
            severity="advisory",
            status="warning",
            detail="Workspace snapshot is unavailable, so truthful market-data posture could not be evaluated.",
        )
    elif workspace_snapshot.market_snapshot is None:
        add_check(
            key="market_data_truth",
            label="Market-data truth posture",
            surface="market_panel",
            severity="advisory",
            status="warning",
            detail="Market panel is hidden until live quote and candle data are available; no synthetic prices are exposed.",
            metrics={
                "market_visible": False,
                "data_mode": workspace_snapshot.control_panel.data_mode,
            },
        )
    else:
        market_snapshot = workspace_snapshot.market_snapshot
        market_status = "warning" if market_snapshot.status in {"stale", "degraded"} else "ok"
        add_check(
            key="market_data_truth",
            label="Market-data truth posture",
            surface="market_panel",
            severity="advisory",
            status=market_status,
            detail="Market panel is backed by live quote and candle data." if market_status == "ok" else "Market panel is visible, but the current live data posture is aging or degraded.",
            metrics={
                "market_visible": True,
                "price_source": market_snapshot.price_source,
                "status": market_snapshot.status,
                "daily_points": len(market_snapshot.daily.points),
                "weekly_points": len(market_snapshot.weekly.points),
                "monthly_points": len(market_snapshot.monthly.points),
            },
        )

    _add_market_data_policy_check(add_check, workspace_snapshot=workspace_snapshot)

    required_failures = [item for item in checks if item.severity == "required" and item.status == "not_ok"]
    warnings = [item for item in checks if item.status == "warning"]
    status = "not_ok" if required_failures else "warning" if warnings else "ok"
    release_gate = "fail" if required_failures else "pass"
    if required_failures:
        summary = f"{len(required_failures)} required readiness check(s) failed; release gate is blocked."
    elif warnings:
        summary = f"Core operator surfaces are healthy; release gate passes with {len(warnings)} warning(s) to review."
    else:
        summary = "Core operator surfaces, prompt governance, and truthful market-data posture are healthy."

    return ProductReadinessResponse(
        status=status,
        release_gate=release_gate,
        root=selected_root,
        generated_at=generated_at,
        summary=summary,
        checks=checks,
    )


def _add_admin_runtime_security_check(add_check) -> None:
    state = admin_security_state()
    configured = bool(state["configured"])
    protected_environment = bool(state["protected_environment"])
    required = bool(state["required"])
    severity = "required" if required else "advisory"

    if required and not configured:
        status = "not_ok"
        detail = "Admin/runtime controls require ADMIN_API_KEY in this environment, but it is not configured."
    elif configured:
        status = "ok"
        detail = "Admin/runtime control APIs require the configured admin key."
    else:
        status = "ok"
        detail = "Local environment allows admin/runtime controls without an API key."

    add_check(
        key="admin_runtime_security",
        label="Admin/runtime API protection",
        surface="security",
        severity=severity,
        status=status,
        detail=detail,
        metrics={
            "environment": state["environment"],
            "protected_environment": protected_environment,
            "admin_api_key_configured": configured,
            "header": state["header"],
        },
    )


def _add_backup_readiness_check(add_check, *, generated_at: datetime, admin_health) -> None:
    if admin_health is None:
        add_check(
            key="backup_freshness",
            label="Backup freshness",
            surface="backup",
            severity="advisory",
            status="warning",
            detail="Backup freshness could not be evaluated because admin health is unavailable.",
        )
        return

    latest_backup_at = _ensure_aware_utc(admin_health.latest_backup_at)
    age_seconds = (
        int((generated_at - latest_backup_at).total_seconds()) if latest_backup_at is not None else None
    )
    backup_artifacts = int(admin_health.backup_artifacts)
    is_fresh = backup_artifacts > 0 and age_seconds is not None and age_seconds <= BACKUP_FRESH_SECONDS
    if is_fresh:
        status = "ok"
        detail = "A recent backup artifact is available."
    elif backup_artifacts > 0:
        status = "warning"
        detail = "Backup artifacts exist, but the latest backup is older than the freshness target."
    else:
        status = "warning"
        detail = "No backup artifacts are available yet; run the restore drill before release."
    add_check(
        key="backup_freshness",
        label="Backup freshness",
        surface="backup",
        severity="advisory",
        status=status,
        detail=detail,
        metrics={
            "backup_artifacts": backup_artifacts,
            "latest_backup_age_seconds": age_seconds,
            "freshness_target_seconds": BACKUP_FRESH_SECONDS,
        },
    )


def _add_scheduler_readiness_check(add_check, *, container, admin_health) -> None:
    if admin_health is None:
        add_check(
            key="scheduler_health",
            label="Scheduler health",
            surface="scheduler",
            severity="advisory",
            status="warning",
            detail="Scheduler health could not be evaluated because admin health is unavailable.",
        )
        return

    metrics = {item.name: item for item in admin_health.metrics}
    total_runs = int(metrics.get("scheduler_runs_total").value) if metrics.get("scheduler_runs_total") else 0
    failed_runs = int(metrics.get("scheduler_failed_runs_total").value) if metrics.get("scheduler_failed_runs_total") else 0
    active_locks = int(metrics.get("scheduler_active_locks").value) if metrics.get("scheduler_active_locks") else 0
    try:
        planned_jobs = len(container.scheduler_service.plan().jobs)
    except Exception:
        planned_jobs = 0

    if failed_runs > 0:
        status = "warning"
        detail = "Recent scheduler failures need review before release."
    elif total_runs == 0:
        status = "warning"
        detail = "No scheduler run history is available yet."
    else:
        status = "ok"
        detail = "Scheduler run history has no recorded failures."

    add_check(
        key="scheduler_health",
        label="Scheduler health",
        surface="scheduler",
        severity="advisory",
        status=status,
        detail=detail,
        metrics={
            "planned_jobs": planned_jobs,
            "scheduler_runs_total": total_runs,
            "scheduler_failed_runs_total": failed_runs,
            "scheduler_active_locks": active_locks,
        },
    )


def _add_delivery_readiness_check(add_check) -> None:
    enabled = telegram_delivery_enabled()
    configured = telegram_delivery_configured()
    source = telegram_source_health()
    if enabled and configured:
        status = "ok"
        detail = "Telegram delivery is enabled and configured."
    elif enabled:
        status = "warning"
        detail = "Telegram delivery is enabled but not fully configured."
    else:
        status = "warning"
        detail = "Telegram delivery is disabled; alerts and digests will stay in preview/dry-run mode."
    add_check(
        key="delivery_readiness",
        label="Delivery readiness",
        surface="notifications",
        severity="advisory",
        status=status,
        detail=detail,
        metrics={
            "telegram_enabled": enabled,
            "telegram_configured": configured,
            "source_status": source.status.value,
        },
    )


def _add_migration_readiness_check(add_check) -> None:
    expected_head = _latest_alembic_revision()
    current_version = _current_database_revision()
    if expected_head is None:
        status = "warning"
        detail = "Alembic migration head could not be resolved from the repository."
    elif current_version is None:
        status = "warning"
        detail = "Database schema is available, but alembic_version is not stamped."
    elif current_version == expected_head:
        status = "ok"
        detail = "Database migration version matches the repository migration head."
    else:
        status = "warning"
        detail = "Database migration version does not match the repository migration head."
    add_check(
        key="migration_status",
        label="Migration status",
        surface="database_schema",
        severity="advisory",
        status=status,
        detail=detail,
        metrics={
            "current_version": current_version,
            "expected_head": expected_head,
            "stamped": current_version is not None,
        },
    )


def _add_restore_drill_evidence_check(add_check, *, generated_at: datetime) -> None:
    environment = _readiness_environment()
    required = bool(settings.product_readiness_require_restore_evidence) or _is_production_like_environment(
        environment
    )
    severity = "required" if required else "advisory"
    configured_path = (settings.product_readiness_restore_evidence_path or "").strip()
    max_age_hours = max(1, int(settings.product_readiness_restore_evidence_max_age_hours))
    metrics: dict[str, MetricValue] = {
        "environment": environment,
        "required": required,
        "path_configured": bool(configured_path),
        "max_age_hours": max_age_hours,
    }

    if not configured_path:
        add_check(
            key="restore_drill_evidence",
            label="Restore drill evidence",
            surface="backup_restore",
            severity=severity,
            status="not_ok" if required else "ok",
            detail=(
                "Production-like environments require PRODUCT_READINESS_RESTORE_EVIDENCE_PATH to point at a fresh restore-drill JSON summary."
                if required
                else "Restore-drill evidence is optional for local development and beta preflight."
            ),
            metrics=metrics,
        )
        return

    evidence_path = Path(configured_path).expanduser()
    if not evidence_path.is_absolute():
        evidence_path = Path.cwd() / evidence_path
    metrics["path"] = str(evidence_path)

    if not evidence_path.exists():
        add_check(
            key="restore_drill_evidence",
            label="Restore drill evidence",
            surface="backup_restore",
            severity=severity,
            status="not_ok" if required else "warning",
            detail="Restore-drill evidence path is configured, but the JSON summary file does not exist.",
            metrics=metrics,
        )
        return

    try:
        payload = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        add_check(
            key="restore_drill_evidence",
            label="Restore drill evidence",
            surface="backup_restore",
            severity=severity,
            status="not_ok" if required else "warning",
            detail=f"Restore-drill evidence could not be read as JSON: {type(exc).__name__}.",
            metrics=metrics,
        )
        return

    generated_raw = payload.get("generated_at") if isinstance(payload, dict) else None
    evidence_generated_at = _parse_iso_datetime(generated_raw)
    evidence_age_seconds = (
        int((generated_at - evidence_generated_at).total_seconds()) if evidence_generated_at is not None else None
    )
    max_age_seconds = max_age_hours * 60 * 60
    release_gate = str(payload.get("release_gate", "")).strip().lower() if isinstance(payload, dict) else ""
    admin_status = str(payload.get("admin_status", "")).strip().lower() if isinstance(payload, dict) else ""
    integrity_check = str(payload.get("integrity_check", "")).strip().lower() if isinstance(payload, dict) else ""
    roots = _coerce_int(payload.get("roots")) if isinstance(payload, dict) else None
    final_signals = _coerce_int(payload.get("final_signals")) if isinstance(payload, dict) else None

    metrics.update(
        {
            "age_seconds": evidence_age_seconds,
            "max_age_seconds": max_age_seconds,
            "release_gate": release_gate or None,
            "admin_status": admin_status or None,
            "integrity_check": integrity_check or None,
            "roots": roots,
            "final_signals": final_signals,
        }
    )

    problems: list[str] = []
    if evidence_generated_at is None:
        problems.append("generated_at is missing or invalid")
    elif evidence_age_seconds is None or evidence_age_seconds < 0 or evidence_age_seconds > max_age_seconds:
        problems.append(f"evidence is older than {max_age_hours}h")
    if release_gate != "pass":
        problems.append("release_gate is not pass")
    if roots is None or roots <= 0:
        problems.append("roots count is missing or zero")
    if final_signals is None or final_signals <= 0:
        problems.append("final_signals count is missing or zero")
    if integrity_check and integrity_check != "ok":
        problems.append("database integrity check is not ok")

    add_check(
        key="restore_drill_evidence",
        label="Restore drill evidence",
        surface="backup_restore",
        severity=severity,
        status="ok" if not problems else "not_ok" if required else "warning",
        detail=(
            "Restore-drill evidence is fresh and passed launch-critical validation."
            if not problems
            else f"Restore-drill evidence is not launch-ready: {'; '.join(problems)}."
        ),
        metrics=metrics,
    )


def _add_market_data_policy_check(add_check, *, workspace_snapshot) -> None:
    environment = _readiness_environment()
    live_required = bool(settings.product_readiness_require_live_market_data) or _is_production_like_environment(
        environment
    )
    market_snapshot = workspace_snapshot.market_snapshot if workspace_snapshot is not None else None
    market_visible = market_snapshot is not None
    market_status = str(market_snapshot.status).strip().lower() if market_snapshot is not None else "hidden"
    live_enabled = bool(settings.market_data_live_enabled)
    if live_required and not live_enabled:
        status = "not_ok"
        severity = "required"
        detail = "This environment requires live market data, but live market-data mode is disabled."
    elif live_required and not market_visible:
        status = "not_ok"
        severity = "required"
        detail = "This environment requires live market data, but the market panel is hidden."
    elif live_required and market_status in {"stale", "degraded"}:
        status = "not_ok"
        severity = "required"
        detail = "This environment requires fresh live market data, but the market panel is stale or degraded."
    elif live_required:
        status = "ok"
        severity = "required"
        detail = "This environment requires live market data and the market panel is fresh."
    elif market_visible:
        status = "ok"
        severity = "advisory"
        detail = "Live market data is visible; local/beta policy is satisfied."
    else:
        status = "warning"
        severity = "advisory"
        detail = "Local/beta policy allows hidden market data when the UI is explicit about it."
    add_check(
        key="market_data_policy",
        label="Environment market-data policy",
        surface="market_panel",
        severity=severity,
        status=status,
        detail=detail,
        metrics={
            "environment": environment,
            "live_required": live_required,
            "live_enabled": live_enabled,
            "market_visible": market_visible,
            "market_status": market_status,
        },
    )


def _readiness_environment() -> str:
    return settings.app_environment.strip().lower() or "local"


def _is_production_like_environment(environment: str) -> bool:
    return environment in PRODUCTION_LIKE_ENVIRONMENTS


def _parse_iso_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return _ensure_aware_utc(parsed)


def _coerce_int(value: object) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _latest_alembic_revision() -> str | None:
    versions_dir = Path.cwd() / "alembic" / "versions"
    if not versions_dir.exists():
        return None
    revisions: list[str] = []
    pattern = re.compile(r'^revision\s*=\s*["\']([^"\']+)["\']')
    for path in versions_dir.glob("*.py"):
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            continue
        for line in content.splitlines():
            match = pattern.match(line.strip())
            if match:
                revisions.append(match.group(1))
                break
    return sorted(revisions)[-1] if revisions else None


def _current_database_revision() -> str | None:
    try:
        with get_engine().connect() as conn:
            row = conn.execute(text("SELECT version_num FROM alembic_version LIMIT 1")).fetchone()
    except Exception:
        return None
    return str(row[0]) if row is not None and row[0] else None


def _ensure_aware_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)

