from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class ContractClosePoint:
    trading_day: date
    contract_code: str
    close: float


@dataclass(frozen=True)
class RollTransition:
    from_contract: str
    to_contract: str
    effective_trading_day: date


@dataclass(frozen=True)
class BackAdjustedPoint:
    trading_day: date
    contract_code: str
    raw_close: float
    adjusted_close: float
    cumulative_adjustment: float


class BackAdjustedSeriesBuilder:
    def build(
        self,
        *,
        points: list[ContractClosePoint],
        transitions: list[RollTransition],
        start_contract: str,
    ) -> list[BackAdjustedPoint]:
        if not points:
            return []

        points_by_contract: dict[str, list[ContractClosePoint]] = {}
        for point in sorted(points, key=lambda item: (item.trading_day, item.contract_code)):
            points_by_contract.setdefault(point.contract_code, []).append(point)

        ordered_transitions = sorted(transitions, key=lambda item: item.effective_trading_day)
        gaps = [self._compute_gap(points_by_contract, item) for item in ordered_transitions]
        raw_series = self._build_raw_series(
            points_by_contract=points_by_contract,
            transitions=ordered_transitions,
            start_contract=start_contract,
        )

        adjusted: list[BackAdjustedPoint] = []
        for point in raw_series:
            cumulative_adjustment = 0.0
            for transition, gap in zip(ordered_transitions, gaps, strict=False):
                if point.trading_day < transition.effective_trading_day:
                    cumulative_adjustment += gap
            adjusted.append(
                BackAdjustedPoint(
                    trading_day=point.trading_day,
                    contract_code=point.contract_code,
                    raw_close=point.close,
                    adjusted_close=round(point.close + cumulative_adjustment, 10),
                    cumulative_adjustment=round(cumulative_adjustment, 10),
                )
            )
        return adjusted

    def _build_raw_series(
        self,
        *,
        points_by_contract: dict[str, list[ContractClosePoint]],
        transitions: list[RollTransition],
        start_contract: str,
    ) -> list[ContractClosePoint]:
        active_contract = start_contract
        result: list[ContractClosePoint] = []

        for index, transition in enumerate(transitions):
            contract_points = points_by_contract.get(active_contract, [])
            for point in contract_points:
                if point.trading_day < transition.effective_trading_day:
                    result.append(point)
            active_contract = transition.to_contract

        for point in points_by_contract.get(active_contract, []):
            result.append(point)

        unique_by_day: dict[date, ContractClosePoint] = {}
        for point in sorted(result, key=lambda item: (item.trading_day, item.contract_code)):
            unique_by_day[point.trading_day] = point
        return [unique_by_day[item] for item in sorted(unique_by_day)]

    def _compute_gap(
        self,
        points_by_contract: dict[str, list[ContractClosePoint]],
        transition: RollTransition,
    ) -> float:
        from_reference = self._latest_point_on_or_before(
            points_by_contract.get(transition.from_contract, []),
            transition.effective_trading_day,
        )
        to_reference = self._earliest_point_on_or_after(
            points_by_contract.get(transition.to_contract, []),
            transition.effective_trading_day,
        )

        if from_reference is None or to_reference is None:
            return 0.0
        return round(to_reference.close - from_reference.close, 10)

    def _latest_point_on_or_before(
        self,
        points: list[ContractClosePoint],
        effective_day: date,
    ) -> ContractClosePoint | None:
        candidates = [item for item in points if item.trading_day <= effective_day]
        if not candidates:
            return None
        return max(candidates, key=lambda item: item.trading_day)

    def _earliest_point_on_or_after(
        self,
        points: list[ContractClosePoint],
        effective_day: date,
    ) -> ContractClosePoint | None:
        candidates = [item for item in points if item.trading_day >= effective_day]
        if not candidates:
            return None
        return min(candidates, key=lambda item: item.trading_day)
