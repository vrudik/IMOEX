from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, desc, inspect, select
from sqlalchemy.exc import IntegrityError
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
from libs.domain.demo_data import list_roots
from libs.domain.models import (
    AnalystOutputRecord,
    ContractMetaRecord,
    FeatureSnapshotRecord,
    FinalSignalRecord,
    NotificationDeliveryEventRecord,
    ReferenceSyncStateRecord,
    RootSeriesRecord,
    RuntimeAuditEventRecord,
    RuntimeFreshnessPolicyRecord,
    RuntimeModelRouteRecord,
    SchedulerLockRecord,
    SchedulerRunRecord,
    SkepticReviewRecord,
    SignalResolutionRecord,
    SignalVersionRecord,
    TradingSessionRecord,
    UserJournalEntryRecord,
    UserNotificationPreferenceRecord,
    UserWorkspaceWatchRecord,
)
from libs.continuous.engine import ContinuousSeriesEngine
from libs.reference.service import get_moex_reference_service
from libs.session.engine import SessionEngine
from libs.utils.config import settings


class SqlAlchemyContractMasterRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self.session_factory = session_factory

    @staticmethod
    def _coerce_utc(value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)

    def _ensure_schema(self) -> None:
        bind = self.session_factory.kw.get("bind")
        if bind is not None:
            RootSeriesRecord.metadata.create_all(bind)
            inspector = inspect(bind)
            table_names = set(inspector.get_table_names())
            if "final_signal" in table_names:
                columns = {column["name"] for column in inspector.get_columns("final_signal")}
                if "workflow_state" not in columns:
                    with bind.begin() as connection:
                        connection.exec_driver_sql("ALTER TABLE final_signal ADD COLUMN workflow_state VARCHAR(32)")
                        connection.exec_driver_sql(
                            "UPDATE final_signal SET workflow_state = 'watch' WHERE workflow_state IS NULL"
                        )
                else:
                    with bind.begin() as connection:
                        connection.exec_driver_sql(
                            "UPDATE final_signal SET workflow_state = 'watch' WHERE workflow_state IS NULL"
                        )
                        connection.exec_driver_sql(
                            "UPDATE final_signal SET workflow_state = 'watching' WHERE workflow_state = 'watch'"
                        )
                        connection.exec_driver_sql(
                            "UPDATE final_signal SET workflow_state = 'validating' WHERE workflow_state = 'review'"
                        )
                        connection.exec_driver_sql(
                            "UPDATE final_signal SET workflow_state = 'ignored' WHERE workflow_state = 'ignore'"
                        )
            if "signal_version" in table_names:
                columns = {column["name"] for column in inspector.get_columns("signal_version")}
                with bind.begin() as connection:
                    if "freshness_score" not in columns:
                        connection.exec_driver_sql("ALTER TABLE signal_version ADD COLUMN freshness_score NUMERIC(18, 10)")
                    if "drivers_blob" not in columns:
                        connection.exec_driver_sql("ALTER TABLE signal_version ADD COLUMN drivers_blob VARCHAR(2048)")
                    if "objections_blob" not in columns:
                        connection.exec_driver_sql("ALTER TABLE signal_version ADD COLUMN objections_blob VARCHAR(2048)")
                    if "invalidation_conditions_blob" not in columns:
                        connection.exec_driver_sql(
                            "ALTER TABLE signal_version ADD COLUMN invalidation_conditions_blob VARCHAR(2048)"
                        )
                    if "data_sources_blob" not in columns:
                        connection.exec_driver_sql("ALTER TABLE signal_version ADD COLUMN data_sources_blob VARCHAR(512)")
            if "user_journal_entry" in table_names:
                columns = {column["name"] for column in inspector.get_columns("user_journal_entry")}
                if "tags_json" not in columns:
                    with bind.begin() as connection:
                        connection.exec_driver_sql(
                            "ALTER TABLE user_journal_entry ADD COLUMN tags_json VARCHAR(1024) DEFAULT '[]'"
                        )

    def count_roots(self) -> int:
        with self.session_factory() as session:
            stmt = select(RootSeriesRecord)
            return len(list(session.execute(stmt).scalars().all()))

    def get_latest_reference_sync_at(self) -> datetime | None:
        self._ensure_schema()
        with self.session_factory() as session:
            sync_row = session.get(ReferenceSyncStateRecord, "contract_reference")
            if sync_row is not None and sync_row.synced_at is not None:
                return self._coerce_utc(sync_row.synced_at)

            stmt = select(ContractMetaRecord.created_at).order_by(desc(ContractMetaRecord.created_at)).limit(1)
            return self._coerce_utc(session.execute(stmt).scalars().first())

    def get_reference_sync_state(self) -> ReferenceSyncStateRecord | None:
        self._ensure_schema()
        with self.session_factory() as session:
            return session.get(ReferenceSyncStateRecord, "contract_reference")

    def record_reference_sync(
        self,
        *,
        as_of: datetime,
        source: str,
        detail: str | None = None,
    ) -> None:
        self._ensure_schema()
        with self.session_factory() as session:
            row = session.get(ReferenceSyncStateRecord, "contract_reference")
            if row is None:
                session.add(
                    ReferenceSyncStateRecord(
                        sync_key="contract_reference",
                        source=source,
                        detail=detail,
                        synced_at=as_of,
                        created_at=as_of,
                        updated_at=as_of,
                    )
                )
            else:
                row.source = source
                row.detail = detail
                row.synced_at = as_of
                row.updated_at = as_of
            session.commit()

    def seed_demo_snapshot(self) -> None:
        self._ensure_schema()
        as_of = datetime.now(UTC)
        reference_service = get_moex_reference_service()
        latest_reference_sync = self.get_latest_reference_sync_at()
        reference_sync_state = self.get_reference_sync_state()
        snapshot_source = reference_sync_state.source if reference_sync_state is not None else "bundled_fallback"
        snapshot_detail = reference_sync_state.detail if reference_sync_state is not None else None
        refresh_interval = timedelta(hours=max(1, settings.moex_reference_auto_sync_interval_hours))
        if latest_reference_sync is None or as_of - latest_reference_sync >= refresh_interval:
            sync_result = reference_service.sync_from_iss_if_due(now=as_of)
            if sync_result is not None:
                snapshot_source = sync_result.source
                snapshot_detail = "; ".join(sync_result.details)
                self.record_reference_sync(
                    as_of=as_of,
                    source=snapshot_source,
                    detail=snapshot_detail,
                )

        expected_roots = {
            item.root_code: item for item in self._build_reference_roots(as_of=as_of, reference_service=reference_service)
        }
        expected_contracts = {item.contract_code: item for item in reference_service.list_contracts()}
        needs_refresh = False

        with self.session_factory() as session:
            existing_root_codes = set(session.execute(select(RootSeriesRecord.root_code)).scalars().all())
            if expected_roots.keys() - existing_root_codes:
                needs_refresh = True
            else:
                for root_code, expected_root in expected_roots.items():
                    row = session.get(RootSeriesRecord, root_code)
                    if row is None:
                        needs_refresh = True
                        break
                    if row.active_contract != expected_root.active_contract or row.next_contract != expected_root.next_contract:
                        needs_refresh = True
                        break

            if not needs_refresh:
                for contract_code, expected_contract in expected_contracts.items():
                    row = session.get(ContractMetaRecord, contract_code)
                    if row is None:
                        needs_refresh = True
                        break
                    if (
                        row.root_code != expected_contract.root_code
                        or row.expiry_date != expected_contract.expiry_date
                        or row.last_trade_date != expected_contract.last_trade_date
                    ):
                        needs_refresh = True
                        break

        if needs_refresh:
            self.sync_reference_snapshot(as_of=as_of, source=snapshot_source, detail=snapshot_detail)

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

    def sync_reference_snapshot(
        self,
        *,
        as_of: datetime,
        source: str = "bundled_fallback",
        detail: str | None = None,
    ) -> tuple[int, int]:
        self._ensure_schema()
        reference_service = get_moex_reference_service()
        roots = self._build_reference_roots(as_of=as_of, reference_service=reference_service)
        contracts = reference_service.list_contracts()
        session_engine = SessionEngine(reference_service=reference_service)
        session_snapshot_by_root = {}
        for root in roots:
            contract = reference_service.get_contract(root.active_contract)
            session_snapshot_by_root[root.root_code] = session_engine.resolve(
                at=as_of,
                last_trade_date=contract.last_trade_date if contract is not None else None,
            )

        with self.session_factory() as session:
            roots_synced = 0
            contracts_synced = 0
            for root in roots:
                root_row = session.get(RootSeriesRecord, root.root_code)
                rule_code = reference_service.sync_root_rule_set(calendar_day=as_of.date())
                if root_row is None:
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
                            session_rule_set=rule_code,
                            created_at=as_of,
                        )
                    )
                else:
                    root_row.session_rule_set = rule_code
                    root_row.active_contract = root.active_contract
                    root_row.next_contract = root.next_contract
                roots_synced += 1

                snapshot = session_snapshot_by_root[root.root_code]
                session.add(
                    TradingSessionRecord(
                        root_code=root.root_code,
                        trading_day=snapshot.trading_day,
                        session_type=snapshot.session_type.value,
                        session_start_at=snapshot.session_start_at,
                        session_end_at=snapshot.session_end_at,
                        is_weekend_linked=snapshot.is_weekend_linked,
                        is_clearing_window=snapshot.is_clearing_window,
                        effective_rule_set=snapshot.effective_rule_set,
                        created_at=as_of,
                    )
                )

            for contract in contracts:
                row = session.get(ContractMetaRecord, contract.contract_code)
                if row is None:
                    session.add(
                        ContractMetaRecord(
                            contract_code=contract.contract_code,
                            root_code=contract.root_code,
                            expiry_date=contract.expiry_date,
                            last_trade_date=contract.last_trade_date,
                            tick_size=contract.tick_size,
                            lot_size=contract.lot_size,
                            currency=contract.currency,
                            active_flag=contract.active_flag,
                            created_at=as_of,
                        )
                    )
                else:
                    row.root_code = contract.root_code
                    row.expiry_date = contract.expiry_date
                    row.last_trade_date = contract.last_trade_date
                    row.tick_size = contract.tick_size
                    row.lot_size = contract.lot_size
                    row.currency = contract.currency
                    row.active_flag = contract.active_flag
                contracts_synced += 1
            session.commit()
        self.record_reference_sync(as_of=as_of, source=source, detail=detail)
        return roots_synced, contracts_synced

    def _build_reference_roots(
        self,
        *,
        as_of: datetime,
        reference_service,
    ):
        session_engine = SessionEngine(reference_service=reference_service)
        continuous_engine = ContinuousSeriesEngine()
        trading_day = session_engine.resolve(at=as_of).trading_day
        resolved_roots = []

        for root in list_roots():
            contracts = reference_service.list_contracts_for_root(root.root_code)
            if contracts:
                contract_rows = [
                    ContractMetaRecord(
                        contract_code=item.contract_code,
                        root_code=item.root_code,
                        expiry_date=item.expiry_date,
                        last_trade_date=item.last_trade_date,
                        tick_size=item.tick_size,
                        lot_size=item.lot_size,
                        currency=item.currency,
                        active_flag=item.active_flag,
                        created_at=as_of,
                    )
                    for item in contracts
                ]
                resolved = continuous_engine.resolve(
                    root_code=root.root_code,
                    trading_day=trading_day,
                    contracts=contract_rows,
                    preferred_active_contract=root.active_contract,
                    preferred_next_contract=root.next_contract,
                )
                if resolved is not None:
                    root = root.model_copy(
                        update={
                            "active_contract": resolved.snapshot.active_contract,
                            "next_contract": resolved.snapshot.next_contract,
                        },
                        deep=True,
                    )
            resolved_roots.append(root)

        return resolved_roots

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
                existing_workflow_state = session.execute(
                    select(FinalSignalRecord.workflow_state).where(FinalSignalRecord.signal_id == signal.signal_id)
                ).scalar_one_or_none()
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
                        workflow_state=existing_workflow_state or signal.workflow_state.value,
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
                        freshness_score=signal.freshness_score,
                        generated_at=signal.generated_at,
                        summary=signal.summary,
                        drivers_blob="\n".join(signal.drivers),
                        objections_blob="\n".join(signal.objections),
                        invalidation_conditions_blob="\n".join(signal.invalidation_conditions),
                        data_sources_blob="\n".join(signal.data_sources),
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

    def update_signal_workflow_state(self, signal_id: str, workflow_state: str) -> bool:
        self._ensure_schema()
        with self.session_factory() as session:
            row = session.execute(
                select(FinalSignalRecord).where(FinalSignalRecord.signal_id == signal_id).limit(1)
            ).scalars().first()
            if row is None:
                return False
            row.workflow_state = workflow_state
            session.commit()
            return True

    def list_signal_versions(
        self,
        *,
        root: str,
        contract: str,
        horizon: str,
        limit: int = 8,
    ) -> list[SignalVersionRecord]:
        self._ensure_schema()
        with self.session_factory() as session:
            stmt = (
                select(SignalVersionRecord)
                .where(SignalVersionRecord.root_code == root)
                .where(SignalVersionRecord.contract_code == contract)
                .where(SignalVersionRecord.horizon == horizon)
                .order_by(desc(SignalVersionRecord.generated_at), desc(SignalVersionRecord.created_at))
                .limit(limit)
            )
            return list(session.execute(stmt).scalars().all())

    def list_similar_resolutions(
        self,
        *,
        root: str,
        horizon: str,
        limit: int = 5,
    ) -> list[SignalResolutionRecord]:
        self._ensure_schema()
        with self.session_factory() as session:
            stmt = (
                select(SignalResolutionRecord)
                .where(SignalResolutionRecord.root_code == root)
                .where(SignalResolutionRecord.horizon == horizon)
                .order_by(desc(SignalResolutionRecord.resolved_at))
                .limit(limit)
            )
            return list(session.execute(stmt).scalars().all())

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
                    tags_json=json.dumps(entry.tags, ensure_ascii=False),
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

    def upsert_workspace_watch(
        self,
        *,
        watch_key: str,
        profile_id: str,
        root_code: str,
        signal_id: str | None,
        note: str | None,
        updated_at: datetime,
    ) -> UserWorkspaceWatchRecord:
        self._ensure_schema()
        with self.session_factory() as session:
            stmt = select(UserWorkspaceWatchRecord).where(UserWorkspaceWatchRecord.watch_key == watch_key).limit(1)
            row = session.execute(stmt).scalars().first()
            if row is None:
                row = UserWorkspaceWatchRecord(
                    watch_key=watch_key,
                    profile_id=profile_id,
                    root_code=root_code,
                    signal_id=signal_id,
                    note=note,
                    created_at=updated_at,
                    updated_at=updated_at,
                )
                session.add(row)
            else:
                row.root_code = root_code
                row.signal_id = signal_id
                row.note = note
                row.updated_at = updated_at
            session.commit()
            session.refresh(row)
            return row

    def list_workspace_watches(self, *, profile_id: str = "default") -> list[UserWorkspaceWatchRecord]:
        self._ensure_schema()
        with self.session_factory() as session:
            stmt = (
                select(UserWorkspaceWatchRecord)
                .where(UserWorkspaceWatchRecord.profile_id == profile_id)
                .order_by(desc(UserWorkspaceWatchRecord.updated_at), UserWorkspaceWatchRecord.root_code.asc())
            )
            return list(session.execute(stmt).scalars().all())

    def delete_workspace_watch(self, *, watch_key: str, profile_id: str = "default") -> bool:
        self._ensure_schema()
        with self.session_factory() as session:
            deleted = session.execute(
                delete(UserWorkspaceWatchRecord)
                .where(UserWorkspaceWatchRecord.watch_key == watch_key)
                .where(UserWorkspaceWatchRecord.profile_id == profile_id)
            ).rowcount or 0
            session.commit()
            return bool(deleted)

    def count_signals(self, *, status: str | None = None) -> int:
        self._ensure_schema()
        with self.session_factory() as session:
            stmt = select(FinalSignalRecord)
            if status:
                stmt = stmt.where(FinalSignalRecord.status == status)
            return len(list(session.execute(stmt).scalars().all()))

    def count_journal_entries(self) -> int:
        self._ensure_schema()
        with self.session_factory() as session:
            stmt = select(UserJournalEntryRecord)
            return len(list(session.execute(stmt).scalars().all()))

    def get_user_notification_preferences(self, profile_id: str = "default") -> UserNotificationPreferenceRecord | None:
        self._ensure_schema()
        with self.session_factory() as session:
            stmt = (
                select(UserNotificationPreferenceRecord)
                .where(UserNotificationPreferenceRecord.profile_id == profile_id)
                .limit(1)
            )
            return session.execute(stmt).scalars().first()

    def upsert_user_notification_preferences(
        self,
        *,
        profile_id: str,
        default_root: str | None,
        subscribed_roots_json: str,
        subscribed_horizons_json: str,
        subscribed_event_kinds_json: str,
        skip_next_event_kinds_json: str,
        min_priority_score: int,
        quiet_hours_start: str | None,
        quiet_hours_end: str | None,
        suppress_during_quiet_hours: bool,
        digest_limit: int,
        updated_at: datetime,
    ) -> UserNotificationPreferenceRecord:
        self._ensure_schema()
        with self.session_factory() as session:
            row = session.get(UserNotificationPreferenceRecord, profile_id)
            if row is None:
                row = UserNotificationPreferenceRecord(
                    profile_id=profile_id,
                    default_root=default_root,
                    subscribed_roots_json=subscribed_roots_json,
                    subscribed_horizons_json=subscribed_horizons_json,
                    subscribed_event_kinds_json=subscribed_event_kinds_json,
                    skip_next_event_kinds_json=skip_next_event_kinds_json,
                    min_priority_score=min_priority_score,
                    quiet_hours_start=quiet_hours_start,
                    quiet_hours_end=quiet_hours_end,
                    suppress_during_quiet_hours=suppress_during_quiet_hours,
                    digest_limit=digest_limit,
                    created_at=updated_at,
                    updated_at=updated_at,
                )
                session.add(row)
            else:
                row.default_root = default_root
                row.subscribed_roots_json = subscribed_roots_json
                row.subscribed_horizons_json = subscribed_horizons_json
                row.subscribed_event_kinds_json = subscribed_event_kinds_json
                row.skip_next_event_kinds_json = skip_next_event_kinds_json
                row.min_priority_score = min_priority_score
                row.quiet_hours_start = quiet_hours_start
                row.quiet_hours_end = quiet_hours_end
                row.suppress_during_quiet_hours = suppress_during_quiet_hours
                row.digest_limit = digest_limit
                row.updated_at = updated_at
            session.commit()
            session.refresh(row)
            return row

    def list_runtime_model_routes(self) -> list[RuntimeModelRouteRecord]:
        self._ensure_schema()
        with self.session_factory() as session:
            stmt = select(RuntimeModelRouteRecord).order_by(RuntimeModelRouteRecord.role_key.asc())
            return list(session.execute(stmt).scalars().all())

    def upsert_runtime_model_route(
        self,
        *,
        role_key: str,
        owner: str,
        product: str,
        model: str,
        control_mode: str,
        detail: str | None,
        updated_at: datetime,
    ) -> RuntimeModelRouteRecord:
        self._ensure_schema()
        with self.session_factory() as session:
            row = session.get(RuntimeModelRouteRecord, role_key)
            if row is None:
                row = RuntimeModelRouteRecord(
                    role_key=role_key,
                    owner=owner,
                    product=product,
                    model=model,
                    control_mode=control_mode,
                    detail=detail,
                    created_at=updated_at,
                    updated_at=updated_at,
                )
                session.add(row)
            else:
                row.owner = owner
                row.product = product
                row.model = model
                row.control_mode = control_mode
                row.detail = detail
                row.updated_at = updated_at
            session.commit()
            session.refresh(row)
            return row

    def delete_runtime_model_routes(self) -> None:
        self._ensure_schema()
        with self.session_factory() as session:
            session.execute(delete(RuntimeModelRouteRecord))
            session.commit()

    def get_runtime_freshness_policy(self, policy_key: str = "default") -> RuntimeFreshnessPolicyRecord | None:
        self._ensure_schema()
        with self.session_factory() as session:
            return session.get(RuntimeFreshnessPolicyRecord, policy_key)

    def upsert_runtime_freshness_policy(
        self,
        *,
        policy_key: str,
        fresh_max_seconds: int,
        aging_max_seconds: int,
        stale_max_seconds: int,
        degraded_max_seconds: int,
        updated_at: datetime,
    ) -> RuntimeFreshnessPolicyRecord:
        self._ensure_schema()
        with self.session_factory() as session:
            row = session.get(RuntimeFreshnessPolicyRecord, policy_key)
            if row is None:
                row = RuntimeFreshnessPolicyRecord(
                    policy_key=policy_key,
                    fresh_max_seconds=fresh_max_seconds,
                    aging_max_seconds=aging_max_seconds,
                    stale_max_seconds=stale_max_seconds,
                    degraded_max_seconds=degraded_max_seconds,
                    created_at=updated_at,
                    updated_at=updated_at,
                )
                session.add(row)
            else:
                row.fresh_max_seconds = fresh_max_seconds
                row.aging_max_seconds = aging_max_seconds
                row.stale_max_seconds = stale_max_seconds
                row.degraded_max_seconds = degraded_max_seconds
                row.updated_at = updated_at
            session.commit()
            session.refresh(row)
            return row

    def add_runtime_audit_event(
        self,
        *,
        event_id: str,
        category: str,
        action: str,
        target_key: str | None,
        detail: str,
        payload_json: str,
        created_at: datetime,
    ) -> RuntimeAuditEventRecord:
        self._ensure_schema()
        with self.session_factory() as session:
            session.execute(delete(RuntimeAuditEventRecord).where(RuntimeAuditEventRecord.event_id == event_id))
            row = RuntimeAuditEventRecord(
                event_id=event_id,
                category=category,
                action=action,
                target_key=target_key,
                detail=detail,
                payload_json=payload_json,
                created_at=created_at,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row

    def list_runtime_audit_events(self, *, category: str | None = None, limit: int = 50) -> list[RuntimeAuditEventRecord]:
        self._ensure_schema()
        with self.session_factory() as session:
            stmt = select(RuntimeAuditEventRecord)
            if category:
                stmt = stmt.where(RuntimeAuditEventRecord.category == category)
            stmt = stmt.order_by(desc(RuntimeAuditEventRecord.created_at)).limit(limit)
            return list(session.execute(stmt).scalars().all())

    def add_notification_delivery_event(
        self,
        *,
        activity_id: str,
        profile_id: str,
        action: str,
        event_kind: str,
        delivery_source: str | None,
        root_code: str | None,
        status: str,
        detail: str,
        signal_ids_json: str,
        provider_message_id: str | None,
        created_at: datetime,
    ) -> NotificationDeliveryEventRecord:
        self._ensure_schema()
        with self.session_factory() as session:
            session.execute(
                delete(NotificationDeliveryEventRecord).where(
                    NotificationDeliveryEventRecord.activity_id == activity_id
                )
            )
            row = NotificationDeliveryEventRecord(
                activity_id=activity_id,
                profile_id=profile_id,
                action=action,
                event_kind=event_kind,
                delivery_source=delivery_source,
                root_code=root_code,
                status=status,
                detail=detail,
                signal_ids_json=signal_ids_json,
                provider_message_id=provider_message_id,
                created_at=created_at,
            )
            session.add(row)
            session.commit()
            session.refresh(row)
            return row

    def list_recent_notification_delivery_events(
        self,
        *,
        profile_id: str = "default",
        root_code: str | None = None,
        event_kind: str | None = None,
        status: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> list[NotificationDeliveryEventRecord]:
        self._ensure_schema()
        with self.session_factory() as session:
            stmt = select(NotificationDeliveryEventRecord).where(
                NotificationDeliveryEventRecord.profile_id == profile_id
            )
            if root_code:
                stmt = stmt.where(NotificationDeliveryEventRecord.root_code == root_code)
            if event_kind:
                stmt = stmt.where(NotificationDeliveryEventRecord.event_kind == event_kind)
            if status:
                stmt = stmt.where(NotificationDeliveryEventRecord.status == status)
            stmt = stmt.order_by(desc(NotificationDeliveryEventRecord.created_at)).offset(max(0, offset)).limit(limit)
            return list(session.execute(stmt).scalars().all())

    def count_notification_delivery_events(
        self,
        *,
        profile_id: str = "default",
        root_code: str | None = None,
        event_kind: str | None = None,
        status: str | None = None,
    ) -> int:
        self._ensure_schema()
        with self.session_factory() as session:
            stmt = select(NotificationDeliveryEventRecord).where(
                NotificationDeliveryEventRecord.profile_id == profile_id
            )
            if root_code:
                stmt = stmt.where(NotificationDeliveryEventRecord.root_code == root_code)
            if event_kind:
                stmt = stmt.where(NotificationDeliveryEventRecord.event_kind == event_kind)
            if status:
                stmt = stmt.where(NotificationDeliveryEventRecord.status == status)
            return len(list(session.execute(stmt).scalars().all()))

    def get_scheduler_run_by_idempotency(self, idempotency_key: str) -> SchedulerRunRecord | None:
        self._ensure_schema()
        with self.session_factory() as session:
            stmt = (
                select(SchedulerRunRecord)
                .where(SchedulerRunRecord.idempotency_key == idempotency_key)
                .limit(1)
            )
            return session.execute(stmt).scalars().first()

    def get_latest_scheduler_run(self, *, job_id: str | None = None) -> SchedulerRunRecord | None:
        self._ensure_schema()
        with self.session_factory() as session:
            stmt = select(SchedulerRunRecord)
            if job_id:
                stmt = stmt.where(SchedulerRunRecord.job_id == job_id)
            stmt = stmt.order_by(desc(SchedulerRunRecord.started_at)).limit(1)
            return session.execute(stmt).scalars().first()

    def list_recent_scheduler_runs(
        self,
        *,
        job_id: str | None = None,
        limit: int = 50,
    ) -> list[SchedulerRunRecord]:
        self._ensure_schema()
        with self.session_factory() as session:
            stmt = select(SchedulerRunRecord)
            if job_id:
                stmt = stmt.where(SchedulerRunRecord.job_id == job_id)
            stmt = stmt.order_by(desc(SchedulerRunRecord.started_at)).limit(limit)
            return list(session.execute(stmt).scalars().all())

    def count_scheduler_runs(self, *, status: str | None = None) -> int:
        self._ensure_schema()
        with self.session_factory() as session:
            stmt = select(SchedulerRunRecord)
            if status:
                stmt = stmt.where(SchedulerRunRecord.status == status)
            return len(list(session.execute(stmt).scalars().all()))

    def count_scheduler_locks(self, *, active_only: bool = True, as_of: datetime | None = None) -> int:
        self._ensure_schema()
        effective_as_of = as_of or datetime.now(UTC)
        with self.session_factory() as session:
            stmt = select(SchedulerLockRecord)
            if active_only:
                stmt = stmt.where(SchedulerLockRecord.expires_at >= effective_as_of)
            return len(list(session.execute(stmt).scalars().all()))

    def has_scheduler_lock(self, lock_key: str, *, as_of: datetime | None = None) -> bool:
        self._ensure_schema()
        effective_as_of = as_of or datetime.now(UTC)
        with self.session_factory() as session:
            stmt = (
                select(SchedulerLockRecord)
                .where(SchedulerLockRecord.lock_key == lock_key)
                .where(SchedulerLockRecord.expires_at >= effective_as_of)
                .limit(1)
            )
            return session.execute(stmt).scalars().first() is not None

    def get_scheduler_lock(self, lock_key: str) -> SchedulerLockRecord | None:
        self._ensure_schema()
        with self.session_factory() as session:
            stmt = (
                select(SchedulerLockRecord)
                .where(SchedulerLockRecord.lock_key == lock_key)
                .limit(1)
            )
            return session.execute(stmt).scalars().first()

    def acquire_scheduler_lock(
        self,
        *,
        lock_key: str,
        job_id: str,
        owner_id: str,
        acquired_at: datetime,
        expires_at: datetime,
    ) -> bool:
        self._ensure_schema()
        with self.session_factory() as session:
            session.execute(delete(SchedulerLockRecord).where(SchedulerLockRecord.expires_at < acquired_at))
            try:
                session.add(
                    SchedulerLockRecord(
                        lock_key=lock_key,
                        job_id=job_id,
                        owner_id=owner_id,
                        acquired_at=acquired_at,
                        expires_at=expires_at,
                        created_at=acquired_at,
                    )
                )
                session.commit()
            except IntegrityError:
                session.rollback()
                return False
        return True

    def release_scheduler_lock(self, lock_key: str) -> None:
        self._ensure_schema()
        with self.session_factory() as session:
            session.execute(delete(SchedulerLockRecord).where(SchedulerLockRecord.lock_key == lock_key))
            session.commit()

    def renew_scheduler_lock(
        self,
        *,
        lock_key: str,
        owner_id: str,
        acquired_at: datetime,
        expires_at: datetime,
    ) -> bool:
        self._ensure_schema()
        with self.session_factory() as session:
            stmt = (
                select(SchedulerLockRecord)
                .where(SchedulerLockRecord.lock_key == lock_key)
                .where(SchedulerLockRecord.owner_id == owner_id)
                .limit(1)
            )
            row = session.execute(stmt).scalars().first()
            if row is None:
                return False
            row.acquired_at = acquired_at
            row.expires_at = expires_at
            session.commit()
            return True

    def release_scheduler_lock_owned(self, *, lock_key: str, owner_id: str) -> None:
        self._ensure_schema()
        with self.session_factory() as session:
            session.execute(
                delete(SchedulerLockRecord)
                .where(SchedulerLockRecord.lock_key == lock_key)
                .where(SchedulerLockRecord.owner_id == owner_id)
            )
            session.commit()

    def start_scheduler_run(
        self,
        *,
        run_id: str,
        job_id: str,
        command: str,
        trigger_mode: str,
        idempotency_key: str,
        status: str,
        detail: str | None,
        payload: dict[str, object] | None,
        scheduled_for: datetime | None,
        started_at: datetime,
    ) -> SchedulerRunRecord | None:
        self._ensure_schema()
        with self.session_factory() as session:
            try:
                row = SchedulerRunRecord(
                    run_id=run_id,
                    job_id=job_id,
                    command=command,
                    trigger_mode=trigger_mode,
                    idempotency_key=idempotency_key,
                    status=status,
                    detail=detail,
                    payload_blob=json.dumps(payload or {}, ensure_ascii=False, sort_keys=True),
                    result_blob=None,
                    scheduled_for=scheduled_for,
                    started_at=started_at,
                    finished_at=None,
                    created_at=started_at,
                )
                session.add(row)
                session.commit()
                session.refresh(row)
                return row
            except IntegrityError:
                session.rollback()
                return None

    def finish_scheduler_run(
        self,
        *,
        idempotency_key: str,
        status: str,
        detail: str | None,
        result: dict[str, object] | None,
        finished_at: datetime,
    ) -> SchedulerRunRecord | None:
        self._ensure_schema()
        with self.session_factory() as session:
            stmt = (
                select(SchedulerRunRecord)
                .where(SchedulerRunRecord.idempotency_key == idempotency_key)
                .limit(1)
            )
            row = session.execute(stmt).scalars().first()
            if row is None:
                return None
            row.status = status
            row.detail = detail
            row.result_blob = json.dumps(result or {}, ensure_ascii=False, sort_keys=True)
            row.finished_at = finished_at
            session.commit()
            session.refresh(row)
            return row

    def get_latest_signal(self) -> FinalSignalRecord | None:
        self._ensure_schema()
        with self.session_factory() as session:
            stmt = select(FinalSignalRecord).order_by(desc(FinalSignalRecord.generated_at)).limit(1)
            return session.execute(stmt).scalars().first()

    def get_latest_resolution(self) -> SignalResolutionRecord | None:
        self._ensure_schema()
        with self.session_factory() as session:
            stmt = select(SignalResolutionRecord).order_by(desc(SignalResolutionRecord.resolved_at)).limit(1)
            return session.execute(stmt).scalars().first()

    def get_latest_journal_entry(self) -> UserJournalEntryRecord | None:
        self._ensure_schema()
        with self.session_factory() as session:
            stmt = select(UserJournalEntryRecord).order_by(desc(UserJournalEntryRecord.created_at)).limit(1)
            return session.execute(stmt).scalars().first()

    def purge_operational_data_older_than(self, *, days: int) -> dict[str, int]:
        self._ensure_schema()
        cutoff = datetime.now(UTC) - timedelta(days=max(0, int(days)))
        with self.session_factory() as session:
            deleted = {
                "feature_snapshots": int(
                    session.execute(delete(FeatureSnapshotRecord).where(FeatureSnapshotRecord.created_at < cutoff)).rowcount
                    or 0
                ),
                "analyst_outputs": int(
                    session.execute(delete(AnalystOutputRecord).where(AnalystOutputRecord.created_at < cutoff)).rowcount
                    or 0
                ),
                "skeptic_reviews": int(
                    session.execute(delete(SkepticReviewRecord).where(SkepticReviewRecord.created_at < cutoff)).rowcount
                    or 0
                ),
                "signal_versions": int(
                    session.execute(delete(SignalVersionRecord).where(SignalVersionRecord.created_at < cutoff)).rowcount or 0
                ),
                "signal_resolutions": int(
                    session.execute(delete(SignalResolutionRecord).where(SignalResolutionRecord.created_at < cutoff)).rowcount
                    or 0
                ),
                "journal_entries": int(
                    session.execute(delete(UserJournalEntryRecord).where(UserJournalEntryRecord.created_at < cutoff)).rowcount
                    or 0
                ),
                "notification_delivery_events": int(
                    session.execute(
                        delete(NotificationDeliveryEventRecord).where(
                            NotificationDeliveryEventRecord.created_at < cutoff
                        )
                    ).rowcount
                    or 0
                ),
                "scheduler_runs": int(
                    session.execute(delete(SchedulerRunRecord).where(SchedulerRunRecord.created_at < cutoff)).rowcount or 0
                ),
                "scheduler_locks": int(
                    session.execute(delete(SchedulerLockRecord).where(SchedulerLockRecord.expires_at < cutoff)).rowcount or 0
                ),
                "final_signals": int(
                    session.execute(
                        delete(FinalSignalRecord)
                        .where(FinalSignalRecord.created_at < cutoff)
                        .where(FinalSignalRecord.status != "active")
                    ).rowcount
                    or 0
                ),
            }
            session.commit()
            return deleted


def _currency_for_root(root_code: str) -> str:
    if root_code.upper() == "SI":
        return "RUB"
    return "PTS"
