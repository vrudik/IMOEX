from __future__ import annotations

from fastapi import APIRouter, HTTPException

from libs.bootstrap.container import get_app_container
from libs.domain.contracts import FinalSignalCard, RootDeepDive, RootSeriesSummary

router = APIRouter(tags=["roots"])


@router.get("/roots", response_model=list[RootSeriesSummary])
async def get_roots() -> list[RootSeriesSummary]:
    return get_app_container().contract_master_service.list_roots()


@router.get("/roots/{root}/deep-dive", response_model=RootDeepDive)
async def get_root_details(root: str) -> RootDeepDive:
    container = get_app_container()
    details = container.contract_master_service.get_root_deep_dive(root)
    if details is None:
        raise HTTPException(status_code=404, detail=f"Unknown root series: {root}")
    signals = container.signal_service.list_signals(root=details.root.root_code, status="active", limit=20)
    if not signals:
        built = container.signal_service.build_signals_for_root(details)
        signals = [FinalSignalCard.model_validate(item.model_dump()) for item in built]
    return details.model_copy(
        update={"active_signals": signals},
        deep=True,
    )
