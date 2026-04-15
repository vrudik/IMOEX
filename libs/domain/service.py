from __future__ import annotations

from datetime import UTC, datetime
from functools import lru_cache

from libs.analysts.service import AnalystService
from libs.continuous.engine import ContinuousSeriesEngine
from libs.domain.contracts import (
    AssetClass,
    AnalystOutput,
    ContinuousSeriesSnapshot,
    FeatureSnapshot,
    RollEventPreview,
    RootDeepDive,
    RootSeriesSummary,
    SessionSnapshot,
    SessionType,
    SkepticReview,
)
from libs.domain.demo_data import get_root_deep_dive, list_roots
from libs.domain.models import ContractMetaRecord, RootSeriesRecord, TradingSessionRecord
from libs.domain.repository import SqlAlchemyContractMasterRepository
from libs.features.service import FeatureService
from libs.reference.service import MoexReferenceService, get_moex_reference_service
from libs.skeptic.service import SkepticService
from libs.session.engine import SessionEngine
from libs.universe.service import UniverseCandidate, UniverseService
from libs.utils.db import get_session_factory


class ContractMasterService:
    def __init__(
        self,
        repository: SqlAlchemyContractMasterRepository,
        session_engine: SessionEngine,
        continuous_engine: ContinuousSeriesEngine,
        feature_service: FeatureService,
        reference_service: MoexReferenceService | None = None,
        universe_service: UniverseService | None = None,
        analyst_service: AnalystService | None = None,
        skeptic_service: SkepticService | None = None,
    ) -> None:
        self.repository = repository
        self.session_engine = session_engine
        self.continuous_engine = continuous_engine
        self.feature_service = feature_service
        self.reference_service = reference_service or get_moex_reference_service()
        self.universe_service = universe_service or UniverseService()
        self.analyst_service = analyst_service or AnalystService(repository)
        self.skeptic_service = skeptic_service or SkepticService(repository)

    def list_roots(self) -> list[RootSeriesSummary]:
        try:
            self.repository.seed_demo_snapshot()
            rows = self.repository.list_roots()
            contracts_by_root = {item.root_code: self.repository.list_contracts_for_root(item.root_code) for item in rows}
        except Exception:
            return list_roots()

        if not rows:
            return list_roots()
        ranked = self.universe_service.rank(roots=rows, contracts_by_root=contracts_by_root)
        summaries = [
            self.universe_service.apply_to_summary(self._to_root_summary(item.root), item, index + 1)
            for index, item in enumerate(ranked)
        ]
        return summaries

    def get_root_deep_dive(self, root_code: str) -> RootDeepDive | None:
        demo = get_root_deep_dive(root_code)
        if demo is None:
            return None

        try:
            self.repository.seed_demo_snapshot()
            root_row = self.repository.get_root(demo.root.root_code)
            session_row = self.repository.get_latest_session(demo.root.root_code)
            contract_meta = self.repository.get_contract_meta(demo.root.active_contract)
            contracts = self.repository.list_contracts_for_root(demo.root.root_code)
        except Exception:
            return self._with_feature_fallback(demo)

        if root_row is None:
            return self._with_feature_fallback(demo)

        session_snapshot = self._build_session_snapshot(
            root_code=demo.root.root_code,
            contract_meta=contract_meta,
            fallback=session_row,
        )
        continuous_snapshot = self._build_continuous_snapshot(
            root=root_row,
            contracts=contracts,
            session=session_snapshot,
            fallback=demo.continuous_series,
        )
        feature_snapshots = self._build_feature_snapshots(
            root=root_row,
            session=session_snapshot,
            continuous=continuous_snapshot[0],
        )
        root_summary = self._to_root_summary(root_row)
        universe_candidate = self._build_universe_candidate(root=root_row, contracts=contracts)
        enriched_root = self.universe_service.apply_to_summary(root_summary, universe_candidate, int(root_row.liquidity_rank))
        analyst_outputs = self._build_analyst_outputs(
            root=enriched_root,
            session=session_snapshot,
            continuous=continuous_snapshot[0],
            feature_snapshots=feature_snapshots,
        )
        skeptic_reviews = self._build_skeptic_reviews(
            root=enriched_root,
            session=session_snapshot,
            continuous=continuous_snapshot[0],
            feature_snapshots=feature_snapshots,
            analyst_outputs=analyst_outputs,
        )
        return demo.model_copy(
            update={
                "root": enriched_root,
                "session": session_snapshot if session_snapshot is not None else demo.session,
                "continuous_series": continuous_snapshot[0],
                "roll_event": continuous_snapshot[1],
                "feature_snapshots": feature_snapshots,
                "analyst_outputs": analyst_outputs,
                "skeptic_reviews": skeptic_reviews,
            },
            deep=True,
        )

    def _to_root_summary(self, row: RootSeriesRecord) -> RootSeriesSummary:
        return RootSeriesSummary(
            root_code=row.root_code,
            asset_class=AssetClass(row.asset_class),
            base_asset=row.base_asset,
            active_contract=row.active_contract,
            next_contract=row.next_contract,
            liquidity_rank=int(row.liquidity_rank),
            primary_provider=row.primary_provider,
            secondary_provider=row.secondary_provider,
            session_rule_set=row.session_rule_set,
        )

    def _to_session_snapshot(self, row: TradingSessionRecord) -> SessionSnapshot:
        return SessionSnapshot(
            calendar_day=row.session_start_at.date(),
            trading_day=row.trading_day,
            session_type=SessionType(row.session_type),
            session_start_at=row.session_start_at,
            session_end_at=row.session_end_at,
            is_weekend_linked=bool(row.is_weekend_linked),
            is_clearing_window=bool(row.is_clearing_window),
            is_near_expiry=False,
            effective_rule_set=row.effective_rule_set,
        )

    def _build_session_snapshot(
        self,
        *,
        root_code: str,
        contract_meta: ContractMetaRecord | None,
        fallback: TradingSessionRecord | None,
    ) -> SessionSnapshot | None:
        if contract_meta is not None:
            return self.session_engine.resolve(
                at=datetime.now(UTC),
                last_trade_date=contract_meta.last_trade_date,
            )
        if fallback is not None:
            return self._to_session_snapshot(fallback)
        return None

    def _build_continuous_snapshot(
        self,
        *,
        root: RootSeriesRecord,
        contracts: list[ContractMetaRecord],
        session: SessionSnapshot | None,
        fallback: ContinuousSeriesSnapshot,
    ) -> tuple[ContinuousSeriesSnapshot, RollEventPreview | None]:
        if session is None or not contracts:
            return fallback, None

        resolved = self.continuous_engine.resolve(
            root_code=root.root_code,
            trading_day=session.trading_day,
            contracts=contracts,
            preferred_active_contract=root.active_contract,
            preferred_next_contract=root.next_contract,
        )
        if resolved is None:
            return fallback, None
        return resolved.snapshot, resolved.roll_event

    def _build_feature_snapshots(
        self,
        *,
        root: RootSeriesRecord,
        session: SessionSnapshot | None,
        continuous: ContinuousSeriesSnapshot,
    ) -> list[FeatureSnapshot]:
        if session is None:
            return []
        try:
            return self.feature_service.build_snapshots(
                root_code=root.root_code,
                contract_code=continuous.active_contract,
                session=session,
                continuous=continuous,
            )
        except Exception:
            return []

    def _with_feature_fallback(self, demo: RootDeepDive) -> RootDeepDive:
        try:
            feature_snapshots = self.feature_service.build_snapshots(
                root_code=demo.root.root_code,
                contract_code=demo.continuous_series.active_contract,
                session=demo.session,
                continuous=demo.continuous_series,
            )
        except Exception:
            feature_snapshots = []
        try:
            analyst_outputs = self.analyst_service.build_outputs(
                root=demo.root,
                session=demo.session,
                continuous=demo.continuous_series,
                feature_snapshots=feature_snapshots,
            )
        except Exception:
            analyst_outputs = []
        try:
            skeptic_reviews = self.skeptic_service.build_reviews(
                root=demo.root,
                session=demo.session,
                continuous=demo.continuous_series,
                feature_snapshots=feature_snapshots,
                analyst_outputs=analyst_outputs,
            )
        except Exception:
            skeptic_reviews = []
        return demo.model_copy(
            update={
                "feature_snapshots": feature_snapshots,
                "analyst_outputs": analyst_outputs,
                "skeptic_reviews": skeptic_reviews,
            },
            deep=True,
        )

    def _build_universe_candidate(
        self,
        *,
        root: RootSeriesRecord,
        contracts: list[ContractMetaRecord],
    ) -> UniverseCandidate:
        return self.universe_service.rank(roots=[root], contracts_by_root={root.root_code: contracts})[0]

    def _build_analyst_outputs(
        self,
        *,
        root: RootSeriesSummary,
        session: SessionSnapshot | None,
        continuous: ContinuousSeriesSnapshot,
        feature_snapshots: list[FeatureSnapshot],
    ) -> list[AnalystOutput]:
        if session is None or not feature_snapshots:
            return []
        try:
            return self.analyst_service.build_outputs(
                root=root,
                session=session,
                continuous=continuous,
                feature_snapshots=feature_snapshots,
            )
        except Exception:
            return []

    def _build_skeptic_reviews(
        self,
        *,
        root: RootSeriesSummary,
        session: SessionSnapshot | None,
        continuous: ContinuousSeriesSnapshot,
        feature_snapshots: list[FeatureSnapshot],
        analyst_outputs: list[AnalystOutput],
    ) -> list[SkepticReview]:
        if session is None or not feature_snapshots:
            return []
        try:
            return self.skeptic_service.build_reviews(
                root=root,
                session=session,
                continuous=continuous,
                feature_snapshots=feature_snapshots,
                analyst_outputs=analyst_outputs,
            )
        except Exception:
            return []


@lru_cache(maxsize=1)
def get_contract_master_service() -> ContractMasterService:
    repository = SqlAlchemyContractMasterRepository(get_session_factory())
    reference_service = get_moex_reference_service()
    return ContractMasterService(
        repository,
        SessionEngine(reference_service=reference_service),
        ContinuousSeriesEngine(),
        FeatureService(repository),
        reference_service,
        UniverseService(),
        AnalystService(repository),
        SkepticService(repository),
    )
