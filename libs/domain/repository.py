from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, desc, select
from sqlalchemy.orm import Session, sessionmaker

from libs.domain.contracts import (
    AnalystKind,
    AnalystOutput,
    FeatureSnapshot,
    FinalSignalDetail,
    HorizonCode,
    JournalEntry,
    SkepticReview,
    SignalResolution,
)
from libs.domain.demo_data import get_root_deep_dive, list_roots
from libs.domain.models import (
    AnalystOutputRecord,
    ContractMetaRecord,
    FeatureSnapshotRecord,
    FinalSignalRecord,
    RootSeriesRecord,
    SkepticReviewRecord,
    SignalResolutionRecord,
    SignalVersionRecord,
    TradingSessionRecord,
    UserJournalEntryRecord,
)


class SqlAlchemyContractMasterRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    def _ensure_schema(self) -> None:
        bind = self.session_factory.kw.get("bind")
        if bind is not None:
            RootSeriesRecord.metadata.create_all(bind)

    def count_roots(self) -> int:
        with self.session_factory() as session:
            stmt = select(RootSeriesRecord)
            return len(list(session.execute(stmt).scalars().all()))

    def seed_demo_snapshot(self) -> None:
        with self.session_factory() as session:
            existing = session.execute(select(RootSeriesRecord.root_code).limit(1)).first()
            if existing is not None:
                return

            created_at = datetime.now(UTC)
            for root in list_roots():
                deep_dive = get_root_deep_dive(root.root_code)
                session.add(
                    RootSeriesRecord(
                        root_code=root.root_code,
                        asset_class=root.asset_class.value,
                        base_asset=root.base_asset,
                        active_contract=root.active_contract,
                        next_contract=root.next_contract,
                        active_flag=True,
                        liquidity_rank=root.liquidity_rank,
                        liquidity_score=root.liquidity_score,
                        manual_allow=root.manual_override == "allow",
                        manual_deny=root.manual_override == "deny",
                        lock_selected=root.manual_override == "lock",
                        primary_provider=root.primary_provider,
                        secondary_provider=root.secondary_provider,
                        session_rule_set=root.session_rule_set,
                        created_at=created_at,
                    )
                )
                if deep_dive is None:
                    continue

                session.add(
                    TradingSessionRecord(
                        root_code=root.root_code,
                        trading_day=deep_dive.session.trading_day,
                        session_type=deep_dive.session.session_type.value,
                        session_start_at=deep_dive.session.session_start_at,
                        session_end_at=deep_dive.session.session_end_at,
                        is_weekend_linked=deep_dive.session.is_weekend_linked,
                        is_clearing_window=deep_dive.session.is_clearing_window,
                        effective_rule_set=deep_dive.session.effective_rule_set,
                        created_at=created_at,
                    )
                )

                session.add_all(
                    [
                        ContractMetaRecord(
                            contract_code=root.active_contract,
                            root_code=root.root_code,
                            expiry_date=deep_dive.session.trading_day
                            + timedelta(days=deep_dive.continuous_series.days_to_expiry),
                            last_trade_date=deep_dive.session.trading_day
                            + timedelta(days=deep_dive.continuous_series.days_to_last_trade),
                            tick_size=1.0,
                            lot_size=1,
                            currency=_currency_for_root(root.root_code),
                            active_flag=True,
                            created_at=created_at,
                        ),
                        ContractMetaRecord(
                            contract_code=root.next_contract,
                            root_code=root.root_code,
                            expiry_date=deep_dive.session.trading_day
                            + timedelta(days=deep_dive.continuous_series.days_to_expiry + 90),
                            last_trade_date=deep_dive.session.trading_day
                            + timedelta(days=deep_dive.continuous_series.days_to_last_trade + 90),
                            tick_size=1.0,
                            lot_size=1,
                            currency=_currency_for_root(root.root_code),
                            active_flag=True,
                            created_at=created_at,
                        ),
                    ]
                )

            session.commit()

    def list_roots(self) -> list[RootSeriesRecord]:
        with self.session_factory() as session:
            stmt = select(RootSeriesRecord).order_by(RootSeriesRecord.liquidity_rank.asc(), RootSeriesRecord.root_code.asc())
            return list(session.execute(stmt).scalars().all())

    def get_root(self, root_code: str) -> RootSeriesRecord | None:
        with self.session_factory() as session:
            stmt = select(RootSeriesRecord).where(RootSeriesRecord.root_code == root_code)
            return session.execute(stmt).scalars().first()

    def get_latest_session(self, root_code: str) -> TradingSessionRecord | None:
        with self.session_factory() as session:
            stmt = (
                select(TradingSessionRecord)
                .where(TradingSessionRecord.root_code == root_code)
                .order_by(desc(TradingSessionRecord.trading_day), desc(TradingSessionRecord.session_start_at))
                .limit(1)
            )
            return session.execute(stmt).scalars().first()

    def get_contract_meta(self, contract_code: str) -> ContractMetaRecord | None:
        with self.session_factory() as session:
            stmt = select(ContractMetaRecord).where(ContractMetaRecord.contract_code == contract_code)
            return session.execute(stmt).scalars().first()

    def list_contracts_for_root(self, root_code: str) -> list[ContractMetaRecord]:
        with self.session_factory() as session:
            stmt = (
                select(ContractMetaRecord)
                .where(ContractMetaRecord.root_code == root_code)
                .order_by(ContractMetaRecord.last_trade_date.asc(), ContractMetaRecord.contract_code.asc())
            )
            return list(session.execute(stmt).scalars().all())

    def upsert_feature_snapshots(self, snapshots: list[FeatureSnapshot]) -> None:
        if not snapshots:
            return
        self._ensure_schema()
        with self.session_factory() as session:
            for snapshot in snapshots:
                session.execute(
                    delete(FeatureSnapshotRecord).where(FeatureSnapshotRecord.snapshot_id == snapshot.snapshot_id)
                )
                session.add(
                    FeatureSnapshotRecord(
                        snapshot_id=snapshot.snapshot_id,
                        root_code=snapshot.root,
                        contract_code=snapshot.contract,
                        horizon=snapshot.horizon.value,
                        as_of=snapshot.as_of,
                        feature_version=snapshot.feature_version,
                        point_in_time_correct=snapshot.point_in_time_correct,
                        session_of_day=snapshot.session_of_day.value,
                        proximity_to_clearing_minutes=snapshot.proximity_to_clearing_minutes,
                        weekend_linked=snapshot.weekend_linked,
                        days_to_expiry=snapshot.days_to_expiry,
                        days_to_last_trade=snapshot.days_to_last_trade,
                        roll_state=snapshot.roll_state,
                        roll_risk_flag=snapshot.roll_risk_flag,
                        next_contract_share=snapshot.next_contract_share,
                        return_score=snapshot.return_score,
                        realized_volatility=snapshot.realized_volatility,
                        atr_ratio=snapshot.atr_ratio,
                        trend_slope=snapshot.trend_slope,
                        vwap_distance_bps=snapshot.vwap_distance_bps,
                        breakout_state=snapshot.breakout_state,
                        overnight_gap_regime=snapshot.overnight_gap_regime,
                        created_at=datetime.now(UTC),
                    )
                )
            session.commit()

    def list_latest_feature_snapshots(self, *, root_code: str) -> list[FeatureSnapshotRecord]:
        self._ensure_schema()
        with self.session_factory() as session:
            rows: list[FeatureSnapshotRecord] = []
            for horizon in HorizonCode:
                stmt = (
                    select(FeatureSnapshotRecord)
                    .where(FeatureSnapshotRecord.root_code == root_code)
                    .where(FeatureSnapshotRecord.horizon == horizon.value)
                    .order_by(desc(FeatureSnapshotRecord.as_of))
                    .limit(1)
                )
                row = session.execute(stmt).scalars().first()
                if row is not None:
                    rows.append(row)
            rows.sort(key=lambda item: item.horizon)
            return rows

    def upsert_analyst_outputs(self, outputs: list[AnalystOutput]) -> None:
        if not outputs:
            return
        self._ensure_schema()
        with self.session_factory() as session:
            for output in outputs:
                session.execute(delete(AnalystOutputRecord).where(AnalystOutputRecord.output_id == output.output_id))
                session.add(
                    AnalystOutputRecord(
                        output_id=output.output_id,
                        root_code=output.root,
                        contract_code=output.contract,
                        horizon=output.horizon.value,
                        analyst=output.analyst.value,
                        direction=output.direction.value,
                        probability=output.probability,
                        confidence=output.confidence,
                        freshness_score=output.freshness_score,
                        generated_at=output.generated_at,
                        drivers_blob="\n".join(output.drivers),
                        objections_blob="\n".join(output.objections),
                        invalidation_conditions_blob="\n".join(output.invalidation_conditions),
                        created_at=datetime.now(UTC),
                    )
                )
            session.commit()

    def list_latest_analyst_outputs(self, *, root_code: str) -> list[AnalystOutputRecord]:
        self._ensure_schema()
        with self.session_factory() as session:
            rows: list[AnalystOutputRecord] = []
            for horizon in HorizonCode:
                for analyst in AnalystKind:
                    stmt = (
                        select(AnalystOutputRecord)
                        .where(AnalystOutputRecord.root_code == root_code)
                        .where(AnalystOutputRecord.horizon == horizon.value)
                        .where(AnalystOutputRecord.analyst == analyst.value)
                        .order_by(desc(AnalystOutputRecord.generated_at))
                        .limit(1)
                    )
                    row = session.execute(stmt).scalars().first()
                    if row is not None:
                        rows.append(row)
            rows.sort(key=lambda item: (item.horizon, item.analyst))
            return rows

    def upsert_skeptic_reviews(self, reviews: list[SkepticReview]) -> None:
        if not reviews:
            return
        self._ensure_schema()
        with self.session_factory() as session:
            for review in reviews:
                session.execute(delete(SkepticReviewRecord).where(SkepticReviewRecord.review_id == review.review_id))
                session.add(
                    SkepticReviewRecord(
                        review_id=review.review_id,
                        root_code=review.root,
                        contract_code=review.contract,
                        horizon=review.horizon.value,
                        skeptic_score=review.skeptic_score,
                        verdict=review.verdict.value,
                        generated_at=review.generated_at,
                        main_objections_blob="\n".join(review.main_objections),
                        data_quality_flags_blob="\n".join(review.data_quality_flags),
                        created_at=datetime.now(UTC),
                    )
                )
            session.commit()

    def list_latest_skeptic_reviews(self, *, root_code: str) -> list[SkepticReviewRecord]:
        self._ensure_schema()
        with self.session_factory() as session:
            rows: list[SkepticReviewRecord] = []
            for horizon in HorizonCode:
                stmt = (
                    select(SkepticReviewRecord)
                    .where(SkepticReviewRecord.root_code == root_code)
                    .where(SkepticReviewRecord.horizon == horizon.value)
                    .order_by(desc(SkepticReviewRecord.generated_at))
                    .limit(1)
                )
                row = session.execute(stmt).scalars().first()
                if row is not None:
                    rows.append(row)
            rows.sort(key=lambda item: item.horizon)
            return rows

    def upsert_final_signals(self, signals: list[FinalSignalDetail]) -> None:
        if not signals:
            return
        self._ensure_schema()
        with self.session_factory() as session:
            for signal in signals:
                session.execute(delete(FinalSignalRecord).where(FinalSignalRecord.signal_id == signal.signal_id))
                session.execute(
                    delete(SignalVersionRecord)
                    .where(SignalVersionRecord.signal_id == signal.signal_id)
                    .where(SignalVersionRecord.version == signal.version)
                )
                session.add(
                    FinalSignalRecord(
                        signal_id=signal.signal_id,
                        version=signal.version,
                        root_code=signal.root,
                        contract_code=signal.contract,
                        horizon=signal.horizon.value,
                        status=signal.status.value,
                        direction_final=signal.direction_final.value,
                        probability_up=signal.probability_up,
                        probability_down=signal.probability_down,
                        probability_no_edge=signal.probability_no_edge,
                        confidence_final=signal.confidence_final,
                        priority_score=signal.priority_score,
                        roll_risk=signal.roll_risk,
                        expiry_risk=signal.expiry_risk,
                        skeptic_score=signal.skeptic_score,
                        skeptic_verdict=signal.skeptic_verdict.value,
                        generated_at=signal.generated_at,
                        freshness_score=signal.freshness_score,
                        summary=signal.summary,
                        drivers_blob="\n".join(signal.drivers),
                        objections_blob="\n".join(signal.objections),
                        invalidation_conditions_blob="\n".join(signal.invalidation_conditions),
                        data_sources_blob="\n".join(signal.data_sources),
                        created_at=datetime.now(UTC),
                    )
                )
                session.add(
                    SignalVersionRecord(
                        signal_id=signal.signal_id,
                        version=signal.version,
                        root_code=signal.root,
                        contract_code=signal.contract,
                        horizon=signal.horizon.value,
                        status=signal.status.value,
                        direction_final=signal.direction_final.value,
                        probability_up=signal.probability_up,
                        probability_down=signal.probability_down,
                        probability_no_edge=signal.probability_no_edge,
                        confidence_final=signal.confidence_final,
                        priority_score=signal.priority_score,
                        skeptic_score=signal.skeptic_score,
                        skeptic_verdict=signal.skeptic_verdict.value,
                        generated_at=signal.generated_at,
                        summary=signal.summary,
                        created_at=datetime.now(UTC),
                    )
                )
            session.commit()

    def list_latest_signals(
        self,
        *,
        root: str | None = None,
        horizon: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[FinalSignalRecord]:
        self._ensure_schema()
        with self.session_factory() as session:
            stmt = select(FinalSignalRecord)
            if root:
                stmt = stmt.where(FinalSignalRecord.root_code == root)
            if horizon:
                stmt = stmt.where(FinalSignalRecord.horizon == horizon)
            if status:
                stmt = stmt.where(FinalSignalRecord.status == status)
            stmt = stmt.order_by(desc(FinalSignalRecord.generated_at), desc(FinalSignalRecord.priority_score)).limit(limit)
            return list(session.execute(stmt).scalars().all())

    def get_signal(self, signal_id: str) -> FinalSignalRecord | None:
        self._ensure_schema()
        with self.session_factory() as session:
            stmt = select(FinalSignalRecord).where(FinalSignalRecord.signal_id == signal_id)
            return session.execute(stmt).scalars().first()

    def upsert_signal_resolution(self, resolution: SignalResolution) -> None:
        self._ensure_schema()
        with self.session_factory() as session:
            session.execute(delete(SignalResolutionRecord).where(SignalResolutionRecord.signal_id == resolution.signal_id))
            session.add(
                SignalResolutionRecord(
                    resolution_id=resolution.resolution_id,
                    signal_id=resolution.signal_id,
                    root_code=resolution.root,
                    contract_code=resolution.contract,
                    horizon=resolution.horizon.value,
                    resolved_at=resolution.resolved_at,
                    status=resolution.status.value,
                    outcome=resolution.outcome.value,
                    realized_return_bps=resolution.realized_return_bps,
                    realized_hit=resolution.realized_hit,
                    resolution_note=resolution.resolution_note,
                    post_mortem_summary=resolution.post_mortem_summary,
                    created_at=datetime.now(UTC),
                )
            )
            session.commit()

    def get_signal_resolution(self, signal_id: str) -> SignalResolutionRecord | None:
        self._ensure_schema()
        with self.session_factory() as session:
            stmt = (
                select(SignalResolutionRecord)
                .where(SignalResolutionRecord.signal_id == signal_id)
                .order_by(desc(SignalResolutionRecord.resolved_at))
                .limit(1)
            )
            return session.execute(stmt).scalars().first()

    def list_signal_resolutions(self, *, status: str | None = None, limit: int = 50) -> list[SignalResolutionRecord]:
        self._ensure_schema()
        with self.session_factory() as session:
            stmt = select(SignalResolutionRecord)
            if status:
                stmt = stmt.where(SignalResolutionRecord.status == status)
            stmt = stmt.order_by(desc(SignalResolutionRecord.resolved_at)).limit(limit)
            return list(session.execute(stmt).scalars().all())

    def add_journal_entry(self, entry: JournalEntry) -> None:
        self._ensure_schema()
        with self.session_factory() as session:
            session.execute(delete(UserJournalEntryRecord).where(UserJournalEntryRecord.entry_id == entry.entry_id))
            session.add(
                UserJournalEntryRecord(
                    entry_id=entry.entry_id,
                    signal_id=entry.signal_id,
                    kind=entry.kind.value,
                    title=entry.title,
                    note=entry.note,
                    author=entry.author,
                    created_at=entry.created_at,
                )
            )
            session.commit()

    def list_journal_entries(self, signal_id: str) -> list[UserJournalEntryRecord]:
        self._ensure_schema()
        with self.session_factory() as session:
            stmt = (
                select(UserJournalEntryRecord)
                .where(UserJournalEntryRecord.signal_id == signal_id)
                .order_by(UserJournalEntryRecord.created_at.asc())
            )
            return list(session.execute(stmt).scalars().all())


def _currency_for_root(root_code: str) -> str:
    if root_code.upper() == "SI":
        return "RUB"
    return "PTS"
