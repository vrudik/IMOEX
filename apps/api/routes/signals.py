from __future__ import annotations

from fastapi import APIRouter, HTTPException

from libs.bootstrap.container import get_app_container
from libs.domain.contracts import (
    FinalSignalCard,
    FinalSignalDetail,
    HorizonCode,
    SignalStatus,
    SignalWorkflowStateUpdate,
)

router = APIRouter(tags=["signals"])


def _build_signal_baseline() -> list[FinalSignalDetail]:
    container = get_app_container()
    contract_service = container.contract_master_service
    signal_service = container.signal_service
    built: list[FinalSignalDetail] = []
    for root in contract_service.list_roots():
        deep_dive = contract_service.get_root_deep_dive(root.root_code)
        if deep_dive is not None:
            built.extend(signal_service.build_signals_for_root(deep_dive))
    return built


def _materialize_if_needed(
    *,
    root: str | None = None,
    horizon: HorizonCode | None = None,
    status: SignalStatus | None = None,
    limit: int,
) -> list[FinalSignalCard]:
    signal_service = get_app_container().signal_service
    rows = signal_service.list_signals(root=root, horizon=horizon, status=status, limit=limit)
    if rows:
        return rows

    built = _build_signal_baseline()
    rows = signal_service.list_signals(root=root, horizon=horizon, status=status, limit=limit)
    if rows:
        return rows

    return [
        FinalSignalCard.model_validate(item.model_dump())
        for item in built
        if (not root or item.root == root)
        and (not horizon or item.horizon == horizon)
        and (not status or item.status == status)
    ][:limit]


@router.get("/signals", response_model=list[FinalSignalCard])
async def get_signals(
    root: str | None = None,
    horizon: HorizonCode | None = None,
    status: SignalStatus | None = None,
    limit: int = 50,
) -> list[FinalSignalCard]:
    rows = _materialize_if_needed(
        root=root,
        horizon=horizon,
        status=status,
        limit=min(max(int(limit), 1), 200),
    )
    rows.sort(key=lambda item: (item.generated_at, item.priority_score), reverse=True)
    return rows


@router.get("/signals/{signal_id}", response_model=FinalSignalDetail)
async def get_signal_details(signal_id: str) -> FinalSignalDetail:
    signal_service = get_app_container().signal_service
    signal = signal_service.get_signal(signal_id)
    if signal is None:
        built = _build_signal_baseline()
        signal = signal_service.get_signal(signal_id)
        if signal is None:
            signal = next((item for item in built if item.signal_id == signal_id), None)
    if signal is None:
        raise HTTPException(status_code=404, detail=f"Unknown signal: {signal_id}")
    return signal


@router.post("/signals/{signal_id}/workflow-state", response_model=FinalSignalDetail)
async def update_signal_workflow_state(signal_id: str, payload: SignalWorkflowStateUpdate) -> FinalSignalDetail:
    signal_service = get_app_container().signal_service
    signal = signal_service.get_signal(signal_id)
    if signal is None:
        _build_signal_baseline()
    updated = signal_service.set_workflow_state(signal_id, payload.workflow_state)
    if updated is None:
        raise HTTPException(status_code=404, detail=f"Unknown signal: {signal_id}")
    return updated
