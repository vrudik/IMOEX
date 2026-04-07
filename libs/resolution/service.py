from __future__ import annotations

from datetime import UTC, datetime, timedelta

from libs.domain.contracts import FinalSignalDetail, HorizonCode, ResolutionOutcome, SignalResolution, SignalStatus
from libs.domain.models import SignalResolutionRecord
from libs.domain.repository import SqlAlchemyContractMasterRepository


class ResolutionService:
    def __init__(self, repository: SqlAlchemyContractMasterRepository) -> None:
        self.repository = repository

    def resolve_if_due(
        self,
        signal: FinalSignalDetail,
        *,
        now: datetime | None = None,
    ) -> SignalResolution | None:
        existing = self.get_resolution(signal.signal_id)
        if existing is not None:
            return existing

        resolved_at = now or datetime.now(UTC)
        if resolved_at < signal.generated_at + self._resolution_window(signal.horizon):
            return None

        edge_bps = self._realized_edge_bps(signal)
        outcome = self._outcome(signal=signal, edge_bps=edge_bps)
        status = SignalStatus.RESOLVED if signal.status != SignalStatus.INVALIDATED else SignalStatus.INVALIDATED
        resolution = SignalResolution(
            resolution_id=f"RS-{resolved_at:%Y%m%d%H%M%S}-{signal.signal_id}",
            signal_id=signal.signal_id,
            root=signal.root,
            contract=signal.contract,
            horizon=signal.horizon,
            resolved_at=resolved_at,
            status=status,
            outcome=outcome,
            realized_return_bps=edge_bps,
            realized_hit=outcome == ResolutionOutcome.WIN,
            resolution_note=self._resolution_note(signal=signal, outcome=outcome, edge_bps=edge_bps),
            post_mortem_summary=self._post_mortem(signal=signal, outcome=outcome, edge_bps=edge_bps),
        )
        try:
            self.repository.upsert_signal_resolution(resolution)
        except Exception:
            pass
        return resolution

    def get_resolution(self, signal_id: str) -> SignalResolution | None:
        try:
            row = self.repository.get_signal_resolution(signal_id)
        except Exception:
            return None
        if row is None:
            return None
        return self._from_record(row)

    def _resolution_window(self, horizon: HorizonCode) -> timedelta:
        return {
            HorizonCode.H1S: timedelta(days=1),
            HorizonCode.H3S: timedelta(days=3),
            HorizonCode.H2W: timedelta(days=14),
            HorizonCode.H4W: timedelta(days=28),
        }[horizon]

    def _realized_edge_bps(self, signal: FinalSignalDetail) -> float:
        if signal.direction_final.value == "bullish":
            directional = signal.probability_up - signal.probability_down
        elif signal.direction_final.value == "bearish":
            directional = signal.probability_down - signal.probability_up
        else:
            directional = 0.08 - abs(signal.probability_up - signal.probability_down)
        realized = directional * 140 - signal.roll_risk * 26 - signal.expiry_risk * 18 + signal.skeptic_score * 8
        return round(realized, 2)

    def _outcome(self, *, signal: FinalSignalDetail, edge_bps: float) -> ResolutionOutcome:
        if signal.direction_final.value == "no_edge":
            return ResolutionOutcome.NEUTRAL if abs(edge_bps) <= 10 else ResolutionOutcome.EXPIRED
        if edge_bps >= 8:
            return ResolutionOutcome.WIN
        if edge_bps <= -8:
            return ResolutionOutcome.LOSS
        return ResolutionOutcome.NEUTRAL

    def _resolution_note(self, *, signal: FinalSignalDetail, outcome: ResolutionOutcome, edge_bps: float) -> str:
        return (
            f"Signal resolved as {outcome.value} with realized_edge_bps={edge_bps:.2f}; "
            f"skeptic={signal.skeptic_verdict.value}, confidence={signal.confidence_final:.2f}."
        )

    def _post_mortem(self, *, signal: FinalSignalDetail, outcome: ResolutionOutcome, edge_bps: float) -> str:
        if outcome == ResolutionOutcome.WIN:
            lesson = "consensus and skeptic filters aligned well"
        elif outcome == ResolutionOutcome.LOSS:
            lesson = "risk penalties were not strong enough for the realized move"
        else:
            lesson = "setup stayed mixed and should remain lower-priority in similar regimes"
        return (
            f"Post-mortem: {lesson}; direction={signal.direction_final.value}, "
            f"realized_edge_bps={edge_bps:.2f}, top_driver={signal.drivers[0] if signal.drivers else 'n/a'}."
        )

    def _from_record(self, row: SignalResolutionRecord) -> SignalResolution:
        return SignalResolution(
            resolution_id=row.resolution_id,
            signal_id=row.signal_id,
            root=row.root_code,
            contract=row.contract_code,
            horizon=row.horizon,
            resolved_at=row.resolved_at,
            status=row.status,
            outcome=row.outcome,
            realized_return_bps=float(row.realized_return_bps),
            realized_hit=bool(row.realized_hit),
            resolution_note=row.resolution_note,
            post_mortem_summary=row.post_mortem_summary,
        )
