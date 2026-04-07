from __future__ import annotations

from fastapi import APIRouter, HTTPException

from libs.domain.contracts import FinalSignalCard, RootDeepDive, RootSeriesSummary
from libs.domain.repository import SqlAlchemyContractMasterRepository
from libs.domain.service import get_contract_master_service
from libs.signals.service import SignalService
from libs.utils.db import get_session_factory

router = APIRouter(tags=["roots"])


def _get_signal_service() -> SignalService:
    return SignalService(SqlAlchemyContractMasterRepository(get_session_factory()))


@router.get("/roots", response_model=list[RootSeriesSummary])
async def get_roots() -> list[RootSeriesSummary]:
    return get_contract_master_service().list_roots()


@router.get("/roots/{root}/deep-dive", response_model=RootDeepDive)
async def get_root_details(root: str) -> RootDeepDive:
    details = get_contract_master_service().get_root_deep_dive(root)
    if details is None:
        raise HTTPException(status_code=404, detail=f"Unknown root series: {root}")
    signals = _get_signal_service().build_signals_for_root(details)
    return details.model_copy(
        update={"active_signals": [FinalSignalCard.model_validate(item.model_dump()) for item in signals]},
        deep=True,
    )
