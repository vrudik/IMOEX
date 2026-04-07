from __future__ import annotations

from fastapi import APIRouter, HTTPException

from libs.domain.contracts import JournalEntry, JournalEntryCreate
from libs.domain.repository import SqlAlchemyContractMasterRepository
from libs.domain.service import get_contract_master_service
from libs.journal.service import JournalService
from libs.signals.service import SignalService
from libs.utils.db import get_session_factory

router = APIRouter(tags=["journal"])


def _get_signal_service() -> SignalService:
    repository = SqlAlchemyContractMasterRepository(get_session_factory())
    return SignalService(repository)


def _get_journal_service() -> JournalService:
    return JournalService(SqlAlchemyContractMasterRepository(get_session_factory()))


def _materialize_signals() -> list[str]:
    contract_service = get_contract_master_service()
    signal_service = _get_signal_service()
    signal_ids: list[str] = []
    for root in contract_service.list_roots():
        deep_dive = contract_service.get_root_deep_dive(root.root_code)
        if deep_dive is not None:
            signal_ids.extend(item.signal_id for item in signal_service.build_signals_for_root(deep_dive))
    return signal_ids


@router.post("/journal/{signal_id}", response_model=JournalEntry)
async def create_journal_entry(signal_id: str, payload: JournalEntryCreate) -> JournalEntry:
    materialized_ids = _materialize_signals()
    signal = _get_signal_service().get_signal(signal_id)
    if signal is None and signal_id not in materialized_ids:
        raise HTTPException(status_code=404, detail=f"Unknown signal: {signal_id}")
    return _get_journal_service().add_entry(signal_id=signal_id, payload=payload)
