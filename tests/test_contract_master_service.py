from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from libs.reference.contracts import MoexContractReference
from libs.reference.service import get_moex_reference_service
from libs.domain.models import Base
from libs.domain.repository import SqlAlchemyContractMasterRepository
from libs.domain.service import ContractMasterService
from libs.continuous.engine import ContinuousSeriesEngine
from libs.features.service import FeatureService
from libs.session.engine import SessionEngine
from libs.utils.config import settings


def test_contract_master_service_seeds_and_returns_roots(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "moex_reference_auto_sync_enabled", False)
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
    assert active_contract.last_trade_date.isoformat() == "2026-06-18"
    assert active_contract.expiry_date.isoformat() == "2026-06-18"
    assert next_contract.last_trade_date.isoformat() == "2026-09-17"
    assert deep_dive.continuous_series.expiry_date == active_contract.expiry_date
    expected_session = SessionEngine().resolve(at=datetime.now(UTC), last_trade_date=active_contract.last_trade_date)
    assert deep_dive.session.trading_day == expected_session.trading_day
    assert deep_dive.continuous_series.days_to_expiry == max(
        0, (active_contract.expiry_date - expected_session.trading_day).days
    )


def test_sync_reference_snapshot_rolls_root_to_current_front_contract(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "moex_reference_auto_sync_enabled", False)
    get_moex_reference_service.cache_clear()
    reference_service = get_moex_reference_service()
    monkeypatch.setattr(
        reference_service,
        "contracts",
        (
        *reference_service.list_contracts(),
        MoexContractReference(
            contract_code="SiZ6",
            root_code="Si",
            expiry_date=date(2026, 12, 17),
            last_trade_date=date(2026, 12, 17),
            tick_size=1.0,
            lot_size=1,
            currency="RUB",
        ),
        ),
    )

    database_path = tmp_path / "contract_master_dynamic_root.db"
    engine = create_engine(f"sqlite:///{database_path}", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True, class_=Session)
    repository = SqlAlchemyContractMasterRepository(session_factory)

    repository.sync_reference_snapshot(as_of=datetime(2026, 6, 19, 10, 0, tzinfo=UTC))

    root = repository.get_root("Si")
    assert root is not None
    assert root.active_contract == "SiU6"
    assert root.next_contract == "SiZ6"
