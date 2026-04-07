from __future__ import annotations

from datetime import UTC, datetime

from libs.domain.contracts import JournalEntry, JournalEntryCreate
from libs.domain.models import UserJournalEntryRecord
from libs.domain.repository import SqlAlchemyContractMasterRepository


class JournalService:
    def __init__(self, repository: SqlAlchemyContractMasterRepository) -> None:
        self.repository = repository

    def add_entry(self, *, signal_id: str, payload: JournalEntryCreate, created_at: datetime | None = None) -> JournalEntry:
        entry = JournalEntry(
            entry_id=f"JR-{(created_at or datetime.now(UTC)):%Y%m%d%H%M%S}-{signal_id}-{payload.kind.value}",
            signal_id=signal_id,
            kind=payload.kind,
            title=payload.title,
            note=payload.note,
            author=payload.author,
            created_at=created_at or datetime.now(UTC),
        )
        try:
            self.repository.add_journal_entry(entry)
        except Exception:
            pass
        return entry

    def list_entries(self, signal_id: str) -> list[JournalEntry]:
        try:
            rows = self.repository.list_journal_entries(signal_id)
        except Exception:
            return []
        return [self._from_record(item) for item in rows]

    def _from_record(self, row: UserJournalEntryRecord) -> JournalEntry:
        return JournalEntry(
            entry_id=row.entry_id,
            signal_id=row.signal_id,
            kind=row.kind,
            title=row.title,
            note=row.note,
            author=row.author,
            created_at=row.created_at,
        )
