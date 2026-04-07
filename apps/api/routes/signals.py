from __future__ import annotations

from fastapi import APIRouter, HTTPException

from libs.domain.contracts import FinalSignalCard, FinalSignalDetail, HorizonCode, SignalStatus
from libs.domain.repository import SqlAlchemyContractMasterRepository
from libs.domain.service import get_contract_master_service
from libs.signals.service import SignalService
from libs.utils.db import get_session_factory

router = APIRouter(tags=["signals"])


def _get_signal_service() -> SignalService:
    return SignalService(SqlAlchemyContractMasterRepository(get_session_factory()))


def _build_signal_baseline() -> list[FinalSignalDetail]:
    contract_service = get_contract_master_service()
    signal_service = _get_signal_service()
    built: list[FinalSignalDetail] = []
    for root in contract_service.list_roots():
        deep_dive = contract_service.get_root_deep_dive(root.root_code)
        if deep_dive is not None:
            built.extend(signal_service.build_signals_for_root(deep_dive))
    return built


@router.get("/signals", response_model=list[FinalSignalCard])
async def get_signals(
    root: str | None = None,
    horizon: HorizonCode | None = None,
    status: SignalStatus | None = None,
    limit: int = 50,
) -> list[FinalSignalCard]:
    built = _build_signal_baseline()
    rows = _get_signal_service().list_signals(
        root=root,
        horizon=horizon,
        status=status,
        limit=min(max(int(limit), 1), 200),
    )
    if not rows:
        rows = [
            FinalSignalCard.model_validate(item.model_dump())
            for item in built
            if (not root or item.root == root)
            and (not horizon or item.horizon == horizon)
            and (not status or item.status == status)
        ][: min(max(int(limit), 1), 200)]
    rows.sort(key=lambda item: (item.generated_at, item.priority_score), reverse=True)
    return rows


@router.get("/signals/{signal_id}", response_model=FinalSignalDetail)
async def get_signal_details(signal_id: str) -> FinalSignalDetail:
    built = _build_signal_baseline()
    signal = _get_signal_service().get_signal(signal_id)
    if signal is None:
        signal = next((item for item in built if item.signal_id == signal_id), None)
    if signal is None:
        raise HTTPException(status_code=404, detail=f"Unknown signal: {signal_id}")
    return signal
