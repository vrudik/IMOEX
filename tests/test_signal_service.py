from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from libs.continuous.engine import ContinuousSeriesEngine
from libs.domain.models import Base
from libs.domain.repository import SqlAlchemyContractMasterRepository
from libs.domain.service import ContractMasterService
from libs.features.service import FeatureService
from libs.session.engine import SessionEngine
from libs.signals.service import SignalService


def test_signal_service_builds_and_persists_baseline_signals(tmp_path: Path) -> None:
    database_path = tmp_path / "signals.db"
    engine = create_engine(f"sqlite:///{database_path}", future=True)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True, class_=Session)

    repository = SqlAlchemyContractMasterRepository(session_factory)
    contract_service = ContractMasterService(
        repository,
        SessionEngine(),
        ContinuousSeriesEngine(),
        FeatureService(repository),
    )
    signal_service = SignalService(repository)

    deep_dive = contract_service.get_root_deep_dive("Si")

    assert deep_dive is not None
    built = signal_service.build_signals_for_root(deep_dive)
    latest = signal_service.list_signals(root="Si", limit=20)

    assert built
    assert latest
    assert all(item.root == "Si" for item in latest)
    assert any(item.direction_final in {"bullish", "bearish", "no_edge"} for item in latest)
    assert all(0 <= item.skeptic_score <= 1 for item in latest)
    assert any(item.skeptic_verdict in {"pass", "soft_fail", "reject", "human_review"} for item in latest)
