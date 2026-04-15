from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

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

