from __future__ import annotations

from libs.arbiter.service import ArbiterService
from libs.domain.contracts import FinalSignalCard, FinalSignalDetail, RootDeepDive
from libs.domain.models import FinalSignalRecord
from libs.domain.repository import SqlAlchemyContractMasterRepository
from libs.journal.service import JournalService
from libs.resolution.service import ResolutionService


class SignalService:
    def __init__(
        self,
        repository: SqlAlchemyContractMasterRepository,
        arbiter_service: ArbiterService | None = None,
        resolution_service: ResolutionService | None = None,
        journal_service: JournalService | None = None,
    ) -> None:
        self.repository = repository
        self.arbiter_service = arbiter_service or ArbiterService()
        self.resolution_service = resolution_service or ResolutionService(repository)
        self.journal_service = journal_service or JournalService(repository)

    def build_signals_for_root(self, deep_dive: RootDeepDive) -> list[FinalSignalDetail]:
        built: list[FinalSignalDetail] = []
        for snapshot in deep_dive.feature_snapshots:
            analyst_outputs = [item for item in deep_dive.analyst_outputs if item.horizon == snapshot.horizon]
            skeptic_review = next((item for item in deep_dive.skeptic_reviews if item.horizon == snapshot.horizon), None)
            if skeptic_review is None:
                continue
            signal = self.arbiter_service.build_signal(
                root=deep_dive.root,
                snapshot=snapshot,
                analyst_outputs=analyst_outputs,
                skeptic_review=skeptic_review,
            )
            if signal is not None:
                built.append(signal)
        if built:
            try:
                self.repository.upsert_final_signals(built)
            except Exception:
                pass
        for signal in built:
            self.resolution_service.resolve_if_due(signal)
        return built

    def list_signals(
        self,
        *,
        root: str | None = None,
        horizon: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[FinalSignalCard]:
        try:
            rows = self.repository.list_latest_signals(root=root, horizon=horizon, limit=max(limit * 3, 50))
        except Exception:
            return []
        cards: list[FinalSignalCard] = []
        for row in rows:
            card = self._to_card(row)
            resolution = self.resolution_service.get_resolution(card.signal_id)
            if resolution is not None:
                card = card.model_copy(update={"status": resolution.status}, deep=True)
            if status and card.status != status:
                continue
            cards.append(card)
        return cards[:limit]

    def get_signal(self, signal_id: str) -> FinalSignalDetail | None:
        try:
            row = self.repository.get_signal(signal_id)
        except Exception:
            return None
        if row is None:
            return None
        detail = self._to_detail(row)
        resolution = self.resolution_service.get_resolution(signal_id)
        entries = self.journal_service.list_entries(signal_id)
        if resolution is not None:
            detail = detail.model_copy(update={"status": resolution.status, "resolution": resolution}, deep=True)
        return detail.model_copy(update={"journal_entries": entries}, deep=True)

    def _to_card(self, row: FinalSignalRecord) -> FinalSignalCard:
        return FinalSignalCard(
            signal_id=row.signal_id,
            version=int(row.version),
            root=row.root_code,
            contract=row.contract_code,
            horizon=row.horizon,
            status=row.status,
            direction_final=row.direction_final,
            probability_up=float(row.probability_up),
            probability_down=float(row.probability_down),
            probability_no_edge=float(row.probability_no_edge),
            confidence_final=float(row.confidence_final),
            priority_score=int(row.priority_score),
            roll_risk=float(row.roll_risk),
            expiry_risk=float(row.expiry_risk),
            skeptic_score=float(row.skeptic_score),
            skeptic_verdict=row.skeptic_verdict,
            generated_at=row.generated_at,
            freshness_score=float(row.freshness_score),
            summary=row.summary,
        )

    def _to_detail(self, row: FinalSignalRecord) -> FinalSignalDetail:
        card = self._to_card(row)
        return FinalSignalDetail(
            **card.model_dump(),
            drivers=self._split_blob(row.drivers_blob),
            objections=self._split_blob(row.objections_blob),
            invalidation_conditions=self._split_blob(row.invalidation_conditions_blob),
            data_sources=self._split_blob(row.data_sources_blob),
        )

    def _split_blob(self, value: str) -> list[str]:
        if not value:
            return []
        return [item for item in value.split("\n") if item]
