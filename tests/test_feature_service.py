from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from libs.domain.contracts import ContinuousSeriesSnapshot, SessionSnapshot, SessionType
from libs.domain.models import Base
from libs.domain.repository import SqlAlchemyContractMasterRepository
from libs.features.service import FeatureService


def test_feature_service_builds_horizon_specific_point_in_time_snapshots(tmp_path: Path) -> None:
    database_path = tmp_path / "features.db"
    engine = create_engine(f"sqlite:///{database_path}", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True, class_=Session)

    service = FeatureService(SqlAlchemyContractMasterRepository(session_factory))
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

    snapshots = service.build_snapshots(
        root_code="Si",
        contract_code="SiM6",
        session=session,
        continuous=continuous,
        as_of=datetime(2026, 4, 6, 9, 30, tzinfo=UTC),
    )

    assert len(snapshots) == 4
    assert all(item.point_in_time_correct for item in snapshots)
    assert {item.horizon.value for item in snapshots} == {"H1S", "H3S", "H2W", "H4W"}
    assert snapshots[0].session_of_day == SessionType.MAIN


def test_feature_service_persists_latest_snapshots(tmp_path: Path) -> None:
    database_path = tmp_path / "features_latest.db"
    engine = create_engine(f"sqlite:///{database_path}", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True, class_=Session)

    repository = SqlAlchemyContractMasterRepository(session_factory)
    service = FeatureService(repository)
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
        active_contract="BRK6",
        next_contract="BRN6",
        days_to_expiry=10,
        days_to_last_trade=4,
        roll_risk_flag=True,
        next_contract_share=0.7,
        roll_state="roll_window",
        back_adjustment_method="difference_on_roll",
        estimated_roll_date=date(2026, 4, 10),
    )

    service.build_snapshots(
        root_code="BR",
        contract_code="BRK6",
        session=session,
        continuous=continuous,
        as_of=datetime(2026, 4, 6, 9, 30, tzinfo=UTC),
    )
    latest = service.list_latest_snapshots(root_code="BR")

    assert len(latest) == 4
    assert all(item.root == "BR" for item in latest)
    assert any(item.roll_risk_flag for item in latest)
