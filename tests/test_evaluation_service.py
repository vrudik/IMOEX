from __future__ import annotations

from datetime import timedelta
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from libs.continuous.engine import ContinuousSeriesEngine
from libs.domain.contracts import AdminRecalculateRequest
from libs.domain.models import Base
from libs.domain.repository import SqlAlchemyContractMasterRepository
from libs.domain.service import ContractMasterService
from libs.evaluation.service import EvaluationService
from libs.features.service import FeatureService
from libs.pipeline.service import PipelineService
from libs.resolution.service import ResolutionService
from libs.session.engine import SessionEngine
from libs.signals.service import SignalService


def test_evaluation_service_builds_metrics_from_resolved_signals(tmp_path: Path) -> None:
    database_path = tmp_path / "evaluation.db"
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
    pipeline_service = PipelineService(contract_service, signal_service, resolution_service)
    root = contract_service.list_roots()[0]
    seed_signal = signal_service.build_signals_for_root(contract_service.get_root_deep_dive(root.root_code))[0]

    result = pipeline_service.recalculate(
        AdminRecalculateRequest(
            as_of=seed_signal.generated_at + timedelta(days=40),
            resolve_due=True,
        )
    )
    summary = EvaluationService(repository).summarize(top_k=3, limit=100)

    assert result.signals_resolved >= 1
    assert summary.resolved_signals >= 1
    assert summary.brier_score is not None
    assert summary.log_loss is not None
    assert summary.top_k_precision is not None
    assert len(summary.calibration_bins) == 5

    report = EvaluationService(repository).report(top_k=3, limit=100)
    assert report.overall.resolved_signals >= 1
    assert report.slices
