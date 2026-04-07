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
from libs.skeptic.service import SkepticService


def test_skeptic_service_penalizes_liquidity_and_roll_risk(tmp_path: Path) -> None:
    database_path = tmp_path / "skeptic.db"
    engine = create_engine(f"sqlite:///{database_path}", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True, class_=Session)

    repository = SqlAlchemyContractMasterRepository(session_factory)
    feature_service = FeatureService(repository)
    analyst_service = AnalystService(repository)
    skeptic_service = SkepticService(repository)
    root = RootSeriesSummary(
        root_code="BR",
        asset_class=AssetClass.COMMODITY,
        base_asset="Brent Crude",
        active_contract="BRK6",
        next_contract="BRN6",
        liquidity_rank=9,
        liquidity_score=0.54,
        universe_status=UniverseStatus.WATCHLIST,
        primary_provider="moex",
        secondary_provider="bcs",
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
        is_near_expiry=True,
        effective_rule_set="moex-unified-2026-03-23",
    )
    continuous = ContinuousSeriesSnapshot(
        active_contract="BRK6",
        next_contract="BRN6",
        days_to_expiry=5,
        days_to_last_trade=3,
        roll_risk_flag=True,
        next_contract_share=0.71,
        roll_state="roll_window",
        back_adjustment_method="difference_on_roll",
        estimated_roll_date=date(2026, 4, 8),
    )
    snapshots = feature_service.build_snapshots(
        root_code="BR",
        contract_code="BRK6",
        session=session,
        continuous=continuous,
        as_of=datetime(2026, 4, 6, 9, 30, tzinfo=UTC),
    )
    analyst_outputs = analyst_service.build_outputs(
        root=root,
        session=session,
        continuous=continuous,
        feature_snapshots=snapshots,
        as_of=datetime(2026, 4, 6, 9, 30, tzinfo=UTC),
    )

    reviews = skeptic_service.build_reviews(
        root=root,
        session=session,
        continuous=continuous,
        feature_snapshots=snapshots,
        analyst_outputs=analyst_outputs,
        as_of=datetime(2026, 4, 6, 9, 30, tzinfo=UTC),
    )
    latest = skeptic_service.list_latest_reviews(root_code="BR")

    assert len(reviews) == 4
    assert len(latest) == 4
    assert any(item.verdict.value in {"soft_fail", "reject", "human_review"} for item in reviews)
    assert any("low_liquidity" in item.data_quality_flags for item in reviews)
    assert any("near_expiry" in item.data_quality_flags for item in reviews)
