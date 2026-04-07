from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from libs.analysts.service import AnalystService
from libs.domain.contracts import (
    AssetClass,
    ContinuousSeriesSnapshot,
    RootSeriesSummary,
    SessionSnapshot,
    SessionType,
    UniverseStatus,
)
from libs.domain.models import Base
from libs.domain.repository import SqlAlchemyContractMasterRepository
from libs.features.service import FeatureService


def test_analyst_service_builds_four_outputs_per_horizon(tmp_path: Path) -> None:
    database_path = tmp_path / "analysts.db"
    engine = create_engine(f"sqlite:///{database_path}", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True, class_=Session)

    repository = SqlAlchemyContractMasterRepository(session_factory)
    feature_service = FeatureService(repository)
    analyst_service = AnalystService(repository)
    root = RootSeriesSummary(
        root_code="Si",
        asset_class=AssetClass.CURRENCY,
        base_asset="USD/RUB",
        active_contract="SiM6",
        next_contract="SiU6",
        liquidity_rank=1,
        liquidity_score=0.92,
        universe_status=UniverseStatus.SELECTED,
        primary_provider="moex",
        secondary_provider="finam",
        session_rule_set="moex-unified-2026-03-23",
    )
    session = SessionSnapshot(
        calendar_day=date(2026, 4, 6),
        trading_day=date(2026, 4, 6),
        session_type=SessionType.MAIN,
        session_start_at=datetime(2026, 4, 6, 6, 50, tzinfo=UTC),
        session_end_at=datetime(2026, 4, 6, 15, 0, tzinfo=UTC),
        is_weekend_linked=False,
        is_clearing_window=False,
        is_near_expiry=False,
        effective_rule_set="moex-unified-2026-03-23",
    )
    continuous = ContinuousSeriesSnapshot(
        active_contract="SiM6",
        next_contract="SiU6",
        days_to_expiry=74,
        days_to_last_trade=72,
        roll_risk_flag=False,
        next_contract_share=0.24,
        roll_state="stable",
        back_adjustment_method="difference_on_roll",
        estimated_roll_date=date(2026, 6, 15),
    )
    snapshots = feature_service.build_snapshots(
        root_code="Si",
        contract_code="SiM6",
        session=session,
        continuous=continuous,
        as_of=datetime(2026, 4, 6, 9, 30, tzinfo=UTC),
    )

    outputs = analyst_service.build_outputs(
        root=root,
        session=session,
        continuous=continuous,
        feature_snapshots=snapshots,
        as_of=datetime(2026, 4, 6, 9, 30, tzinfo=UTC),
    )
    latest = analyst_service.list_latest_outputs(root_code="Si")

    assert len(outputs) == 16
    assert len(latest) == 16
    assert {item.analyst.value for item in outputs} == {
        "trend_vol",
        "flow_liquidity",
        "oi_roll",
        "macro_event",
    }
    assert all(item.root == "Si" for item in latest)
    assert all(item.freshness_score >= 0.4 for item in latest)
