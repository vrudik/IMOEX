from __future__ import annotations

from fastapi import APIRouter, HTTPException

from libs.bootstrap.container import get_app_container
from libs.domain.contracts import JournalEntry, JournalEntryCreate

router = APIRouter(tags=["journal"])


def _materialize_signals() -> list[str]:
    container = get_app_container()
    contract_service = container.contract_master_service
    signal_service = container.signal_service
    signal_ids: list[str] = []
    for root in contract_service.list_roots():
        deep_dive = contract_service.get_root_deep_dive(root.root_code)
        if deep_dive is not None:
            signal_ids.extend(item.signal_id for item in signal_service.build_signals_for_root(deep_dive))
    return signal_ids


@router.post("/journal/{signal_id}", response_model=JournalEntry)
async def create_journal_entry(signal_id: str, payload: JournalEntryCreate) -> JournalEntry:
    container = get_app_container()
    signal = container.signal_service.get_signal(signal_id)
    if signal is None:
        materialized_ids = _materialize_signals()
        signal = container.signal_service.get_signal(signal_id)
        if signal is None and signal_id not in materialized_ids:
            raise HTTPException(status_code=404, detail=f"Unknown signal: {signal_id}")
    return container.journal_service.add_entry(signal_id=signal_id, payload=payload)
