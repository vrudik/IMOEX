from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from libs.domain.models import Base
from libs.domain.repository import SqlAlchemyContractMasterRepository
from libs.domain.service import ContractMasterService
from libs.continuous.engine import ContinuousSeriesEngine
from libs.features.service import FeatureService
from libs.session.engine import SessionEngine


def test_contract_master_service_seeds_and_returns_roots(tmp_path: Path) -> None:
    database_path = tmp_path / "contract_master.db"
    engine = create_engine(f"sqlite:///{database_path}", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True, class_=Session)
    repository = SqlAlchemyContractMasterRepository(session_factory)

    service = ContractMasterService(
        repository,
        SessionEngine(),
        ContinuousSeriesEngine(),
        FeatureService(repository),
    )

    roots = service.list_roots()
    deep_dive = service.get_root_deep_dive("Si")

    assert len(roots) >= 3
    assert roots[0].root_code == "Si"
    assert deep_dive is not None
    assert deep_dive.root.active_contract == "SiM6"
    assert deep_dive.session.effective_rule_set
    assert deep_dive.session.calendar_day
    assert deep_dive.continuous_series.active_contract == "SiM6"
    assert deep_dive.continuous_series.next_contract == "SiU6"
    assert deep_dive.continuous_series.back_adjustment_method == "difference_on_roll"
    assert len(deep_dive.feature_snapshots) == 4
    assert len(deep_dive.analyst_outputs) == 16
    assert len(deep_dive.skeptic_reviews) == 4
    assert {item.analyst.value for item in deep_dive.analyst_outputs} == {
        "trend_vol",
        "flow_liquidity",
        "oi_roll",
        "macro_event",
    }
    assert {item.verdict.value for item in deep_dive.skeptic_reviews}

    active_contract = repository.get_contract_meta("SiM6")
    next_contract = repository.get_contract_meta("SiU6")
    assert active_contract is not None
    assert next_contract is not None
    assert active_contract.last_trade_date.isoformat() == "2026-06-17"
    assert active_contract.expiry_date.isoformat() == "2026-06-19"
    assert next_contract.last_trade_date.isoformat() == "2026-09-16"
