from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from libs.bootstrap.container import get_app_container
from libs.domain.contracts import (
    AdminBackupRequest,
    AdminBackupResult,
    AdminCleanupRequest,
    AdminCleanupResult,
    AdminHealthSnapshot,
    AdminMoexReferenceSyncRequest,
    AdminMoexReferenceSyncResult,
    AdminRecalculateRequest,
    AdminRecalculateResult,
    AdminReplayRequest,
    AdminReplayResult,
)
from libs.reference.service import get_moex_reference_service
from libs.security.admin import require_admin_api_key

router = APIRouter(tags=["admin"], dependencies=[Depends(require_admin_api_key)])


@router.get("/admin/health", response_model=AdminHealthSnapshot)
async def admin_health() -> AdminHealthSnapshot:
    return get_app_container().observability_service.admin_health()


@router.post("/admin/backup", response_model=AdminBackupResult)
async def create_backup(payload: AdminBackupRequest) -> AdminBackupResult:
    return get_app_container().maintenance_service.create_backup(payload)


@router.post("/admin/cleanup", response_model=AdminCleanupResult)
async def cleanup_operational_data(payload: AdminCleanupRequest) -> AdminCleanupResult:
    return get_app_container().maintenance_service.cleanup(payload)


@router.post("/admin/moex-reference-sync", response_model=AdminMoexReferenceSyncResult)
async def sync_moex_reference(payload: AdminMoexReferenceSyncRequest) -> AdminMoexReferenceSyncResult:
    reference_service = get_moex_reference_service()
    result = reference_service.sync_from_iss(
        from_date=payload.from_date,
        to_date=payload.to_date,
        sync_calendar=payload.sync_calendar,
        sync_contracts=payload.sync_contracts,
    )
    repository = get_app_container().repository
    sync_time = payload.as_of or datetime.now(UTC)
    roots_synced, contracts_synced = repository.sync_reference_snapshot(
        as_of=sync_time,
        source=result.source,
    )
    details = list(result.details)
    details.append(f"roots_synced={roots_synced}")
    details.append(f"repository_contracts_synced={contracts_synced}")
    repository.record_reference_sync(
        as_of=sync_time,
        source=result.source,
        detail="; ".join(details),
    )
    return result.model_copy(update={"details": details}, deep=True)


@router.post("/admin/recalculate", response_model=AdminRecalculateResult)
async def recalculate_signals(payload: AdminRecalculateRequest) -> AdminRecalculateResult:
    return get_app_container().pipeline_service.recalculate(payload)


@router.post("/admin/replay", response_model=AdminReplayResult)
async def replay_signals(payload: AdminReplayRequest) -> AdminReplayResult:
    return get_app_container().pipeline_service.replay(payload)
