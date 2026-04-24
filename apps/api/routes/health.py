from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

from libs.adapters.contracts import SourceRegistryEntry
from libs.adapters.registry import get_adapter_registry
from libs.bootstrap.container import get_app_container
from libs.bootstrap.modules import ModuleSpec, list_module_specs
from libs.domain.contracts import CapabilityRegistry
from libs.runtime.contracts import FeatureFlagState, RuntimeMetricsSnapshot
from libs.runtime.feature_flags import list_feature_flags
from libs.runtime.metrics import get_runtime_metrics_registry
from libs.notifications.readiness import telegram_source_health
from libs.scheduler.contracts import ScheduledJobSnapshot, SchedulerLeaderSnapshot, SchedulerRunHistoryEntry
from libs.utils.db import database_available

router = APIRouter(tags=["health"])
MetricValue = str | int | float | bool | None


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

