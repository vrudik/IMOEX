from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from libs.continuous.engine import ContinuousSeriesEngine
from libs.domain.models import Base
from libs.domain.repository import SqlAlchemyContractMasterRepository
from libs.domain.service import ContractMasterService
from libs.features.service import FeatureService
from libs.resolution.service import ResolutionService
from libs.session.engine import SessionEngine
from libs.signals.service import SignalService


def test_resolution_service_resolves_due_signals(tmp_path: Path) -> None:
    database_path = tmp_path / "resolution.db"
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
    resolution_service = ResolutionService(repository)

    deep_dive = contract_service.get_root_deep_dive("Si")

    assert deep_dive is not None
    built = signal_service.build_signals_for_root(deep_dive)
    assert built

    resolved = resolution_service.resolve_if_due(
        built[0],
        now=built[0].generated_at + timedelta(days=40),
    )

    assert resolved is not None
    assert resolved.signal_id == built[0].signal_id
    assert resolved.status.value in {"resolved", "invalidated"}
    assert resolved.outcome.value in {"win", "loss", "neutral", "expired"}
    assert resolved.post_mortem_summary
