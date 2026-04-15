from __future__ import annotations

from math import log

from libs.domain.contracts import CalibrationBin, EvaluationReport, EvaluationSlice, EvaluationSummary, SignalDirection
from libs.domain.models import FinalSignalRecord, SignalResolutionRecord
from libs.domain.repository import SqlAlchemyContractMasterRepository


class EvaluationService:
    def __init__(self, repository: SqlAlchemyContractMasterRepository) -> None:
        self.repository = repository

    def summarize(
        self,
        *,
        root: str | None = None,
        horizon: str | None = None,
        top_k: int = 5,
        limit: int = 500,
    ) -> EvaluationSummary:
        rows = self.repository.list_latest_signals(root=root, horizon=horizon, limit=max(limit, top_k, 50))
        resolved: list[tuple[FinalSignalRecord, SignalResolutionRecord]] = []
        for row in rows:
            resolution = self.repository.get_signal_resolution(row.signal_id)
            if resolution is not None:
                resolved.append((row, resolution))

        return self._summarize_resolved(resolved, top_k=top_k)

    def report(
        self,
        *,
        root: str | None = None,
        horizon: str | None = None,
        top_k: int = 5,
        limit: int = 500,
    ) -> EvaluationReport:
        overall = self.summarize(root=root, horizon=horizon, top_k=top_k, limit=limit)
        rows = self.repository.list_latest_signals(root=root, horizon=horizon, limit=max(limit, top_k, 50))
        resolved: list[tuple[FinalSignalRecord, SignalResolutionRecord]] = []
        for row in rows:
            resolution = self.repository.get_signal_resolution(row.signal_id)
            if resolution is not None:
                resolved.append((row, resolution))

        slices: list[EvaluationSlice] = []
        for slice_key in ("root", "horizon", "skeptic_verdict", "direction_final"):
            for slice_value in sorted({self._slice_value(signal, slice_key) for signal, _ in resolved}):
                if not slice_value:
                    continue
                filtered = [
                    (signal, resolution)
                    for signal, resolution in resolved
                    if self._slice_value(signal, slice_key) == slice_value
                ]
                if not filtered:
                    continue
                slices.append(
                    EvaluationSlice(
                        slice_key=slice_key,
                        slice_value=slice_value,
                        summary=self._summarize_resolved(filtered, top_k=top_k),
                    )
                )
        return EvaluationReport(overall=overall, slices=slices)

    def _summarize_resolved(
        self,
        resolved: list[tuple[FinalSignalRecord, SignalResolutionRecord]],
        *,
        top_k: int,
    ) -> EvaluationSummary:
        if not resolved:
            return EvaluationSummary(resolved_signals=0, actionable_signals=0, top_k=top_k)

        brier_values: list[float] = []
        baseline_values: list[float] = []
        log_losses: list[float] = []
        predicted_actionable = 0
        actual_actionable = 0
        hits = 0
        calibration_inputs: list[tuple[float, float]] = []

        actual_classes = [self._actual_class(signal, resolution) for signal, resolution in resolved]
        class_priors = {
            "up": actual_classes.count("up") / len(actual_classes),
            "down": actual_classes.count("down") / len(actual_classes),
            "no_edge": actual_classes.count("no_edge") / len(actual_classes),
        }

        for signal, resolution in resolved:
            probs = self._probs(signal)
            actual_class = self._actual_class(signal, resolution)
            actual = {
                "up": 1.0 if actual_class == "up" else 0.0,
                "down": 1.0 if actual_class == "down" else 0.0,
                "no_edge": 1.0 if actual_class == "no_edge" else 0.0,
            }
            brier_values.append(sum((probs[key] - actual[key]) ** 2 for key in actual))
            baseline_values.append(sum((class_priors[key] - actual[key]) ** 2 for key in actual))
            log_losses.append(-log(max(1e-9, probs[actual_class])))

            predicted_class = self._predicted_class(signal)
            predicted_is_actionable = predicted_class in {"up", "down"}
            actual_is_actionable = actual_class in {"up", "down"}
            if predicted_is_actionable:
                predicted_actionable += 1
            if actual_is_actionable:
                actual_actionable += 1
            if predicted_is_actionable and predicted_class == actual_class:
                hits += 1

            calibration_inputs.append((float(signal.confidence_final), 1.0 if resolution.realized_hit else 0.0))

        brier_score = sum(brier_values) / len(brier_values)
        baseline_brier = sum(baseline_values) / len(baseline_values)
        calibration_bins = self._calibration_bins(calibration_inputs)
        top_k_precision = self._top_k_precision(resolved, top_k=top_k)
        calibration_error = self._ece(calibration_bins, total=len(calibration_inputs))

        return EvaluationSummary(
            resolved_signals=len(resolved),
            actionable_signals=predicted_actionable,
            brier_score=round(brier_score, 6),
            brier_skill_score=round(1 - brier_score / baseline_brier, 6) if baseline_brier > 0 else None,
            log_loss=round(sum(log_losses) / len(log_losses), 6),
            precision=round(hits / predicted_actionable, 6) if predicted_actionable else None,
            recall=round(hits / actual_actionable, 6) if actual_actionable else None,
            calibration_error=round(calibration_error, 6),
            top_k_precision=round(top_k_precision, 6) if top_k_precision is not None else None,
            top_k=top_k,
            calibration_bins=calibration_bins,
        )

    def _slice_value(self, signal: FinalSignalRecord, slice_key: str) -> str:
        if slice_key == "root":
            return str(signal.root_code)
        if slice_key == "horizon":
            return str(signal.horizon)
        if slice_key == "skeptic_verdict":
            return str(signal.skeptic_verdict)
        if slice_key == "direction_final":
            return str(signal.direction_final)
        return ""

    def _probs(self, signal: FinalSignalRecord) -> dict[str, float]:
        return {
            "up": float(signal.probability_up),
            "down": float(signal.probability_down),
            "no_edge": float(signal.probability_no_edge),
        }

    def _predicted_class(self, signal: FinalSignalRecord) -> str:
        direction = SignalDirection(signal.direction_final)
        if direction == SignalDirection.BULLISH:
            return "up"
        if direction == SignalDirection.BEARISH:
            return "down"
        return "no_edge"

    def _actual_class(self, signal: FinalSignalRecord, resolution: SignalResolutionRecord) -> str:
        predicted = self._predicted_class(signal)
        outcome = resolution.outcome
        if predicted == "up":
            if outcome == "win":
                return "up"
            if outcome == "loss":
                return "down"
            return "no_edge"
        if predicted == "down":
            if outcome == "win":
                return "down"
            if outcome == "loss":
                return "up"
            return "no_edge"
        return "no_edge"

    def _calibration_bins(self, values: list[tuple[float, float]]) -> list[CalibrationBin]:
        bins: list[list[tuple[float, float]]] = [[] for _ in range(5)]
        for confidence, hit in values:
            index = min(4, max(0, int(confidence * 5)))
            bins[index].append((confidence, hit))

        result: list[CalibrationBin] = []
        for index, bucket in enumerate(bins):
            lower = index * 0.2
            upper = lower + 0.2
            if not bucket:
                result.append(
                    CalibrationBin(
                        lower_bound=round(lower, 2),
                        upper_bound=round(upper, 2),
                        count=0,
                        avg_confidence=0.0,
                        empirical_win_rate=0.0,
                    )
                )
                continue
            result.append(
                CalibrationBin(
                    lower_bound=round(lower, 2),
                    upper_bound=round(upper, 2),
                    count=len(bucket),
                    avg_confidence=round(sum(item[0] for item in bucket) / len(bucket), 6),
                    empirical_win_rate=round(sum(item[1] for item in bucket) / len(bucket), 6),
                )
            )
        return result

    def _ece(self, bins: list[CalibrationBin], *, total: int) -> float:
        if total <= 0:
            return 0.0
        return sum((bucket.count / total) * abs(bucket.avg_confidence - bucket.empirical_win_rate) for bucket in bins)

    def _top_k_precision(
        self,
        resolved: list[tuple[FinalSignalRecord, SignalResolutionRecord]],
        *,
        top_k: int,
    ) -> float | None:
        actionable = [
            (signal, resolution)
            for signal, resolution in resolved
            if self._predicted_class(signal) in {"up", "down"}
        ]
        if not actionable:
            return None
        ordered = sorted(actionable, key=lambda item: (int(item[0].priority_score), item[0].generated_at), reverse=True)
        top = ordered[:top_k]
        if not top:
            return None
        wins = sum(1 for _, resolution in top if bool(resolution.realized_hit))
        return wins / len(top)
