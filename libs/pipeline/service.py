from __future__ import annotations

from libs.domain.contracts import (
    AdminRecalculateRequest,
    AdminRecalculateResult,
    AdminReplayRequest,
    AdminReplayResult,
)
from libs.domain.service import ContractMasterService
from libs.evaluation.service import EvaluationService
from libs.resolution.service import ResolutionService
from libs.signals.service import SignalService


class PipelineService:
    def __init__(
        self,
        contract_service: ContractMasterService,
        signal_service: SignalService,
        resolution_service: ResolutionService,
        evaluation_service: EvaluationService | None = None,
    ) -> None:
        self.contract_service = contract_service
        self.signal_service = signal_service
        self.resolution_service = resolution_service
        self.evaluation_service = evaluation_service or EvaluationService(signal_service.repository)

    def recalculate(self, payload: AdminRecalculateRequest) -> AdminRecalculateResult:
        roots = self.contract_service.list_roots()
        if payload.root:
            roots = [item for item in roots if item.root_code.upper() == payload.root.upper()]

        built_count = 0
        resolved_count = 0
        details: list[str] = []
        for root in roots:
            deep_dive = self.contract_service.get_root_deep_dive(root.root_code)
            if deep_dive is None:
                continue
            built = self.signal_service.build_signals_for_root(deep_dive)
            built_count += len(built)
            details.append(f"{root.root_code}:built={len(built)}")
            if payload.resolve_due:
                for signal in built:
                    resolution = self.resolution_service.resolve_if_due(signal, now=payload.as_of)
                    if resolution is not None:
                        resolved_count += 1

        return AdminRecalculateResult(
            roots_processed=len(roots),
            signals_built=built_count,
            signals_resolved=resolved_count,
            as_of=payload.as_of,
            details=details,
        )

    def replay(self, payload: AdminReplayRequest) -> AdminReplayResult:
        recalculation = self.recalculate(
            AdminRecalculateRequest(
                root=payload.root,
                as_of=payload.as_of,
                resolve_due=True,
            )
        )
        report = self.evaluation_service.report(
            root=payload.root,
            top_k=payload.top_k,
            limit=payload.limit,
        )
        return AdminReplayResult(
            recalculation=recalculation,
            evaluation_report=report,
        )
