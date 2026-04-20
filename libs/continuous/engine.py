from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from libs.domain.contracts import ContinuousSeriesSnapshot, RollEventPreview
from libs.domain.models import ContractMetaRecord


@dataclass(frozen=True)
class RollRuleSet:
    roll_window_days: int = 10
    hard_roll_days: int = 3
    base_next_share: float = 0.05
    max_next_share: float = 0.95


@dataclass(frozen=True)
class ContinuousSeriesDecision:
    snapshot: ContinuousSeriesSnapshot
    roll_event: RollEventPreview | None


class ContinuousSeriesEngine:
    def __init__(self, rules: RollRuleSet | None = None) -> None:
        self.rules = rules or RollRuleSet()

    def resolve(
        self,
        *,
        root_code: str,
        trading_day: date,
        contracts: list[ContractMetaRecord],
        preferred_active_contract: str | None = None,
        preferred_next_contract: str | None = None,
    ) -> ContinuousSeriesDecision | None:
        eligible = [item for item in contracts if item.active_flag and item.last_trade_date >= trading_day]
        if not eligible:
            return None

        eligible.sort(key=lambda item: (item.last_trade_date, item.expiry_date, item.contract_code))
        front = self._pick_front_contract(eligible, preferred_active_contract)
        next_contract = self._pick_next_contract(eligible, front, preferred_next_contract)

        days_to_expiry = max(0, (front.expiry_date - trading_day).days)
        days_to_last_trade = max(0, (front.last_trade_date - trading_day).days)
        next_contract_share = self._estimate_next_share(days_to_last_trade)

        if days_to_last_trade <= self.rules.hard_roll_days:
            roll_state = "hard_roll"
        elif days_to_last_trade <= self.rules.roll_window_days:
            roll_state = "roll_window"
        else:
            roll_state = "stable"

        snapshot = ContinuousSeriesSnapshot(
            active_contract=front.contract_code,
            next_contract=next_contract.contract_code,
            days_to_expiry=days_to_expiry,
            expiry_date=front.expiry_date,
            days_to_last_trade=days_to_last_trade,
            roll_risk_flag=days_to_last_trade <= self.rules.roll_window_days,
            next_contract_share=next_contract_share,
            roll_state=roll_state,
            back_adjustment_method="difference_on_roll",
            estimated_roll_date=front.last_trade_date,
        )
        return ContinuousSeriesDecision(
            snapshot=snapshot,
            roll_event=self._build_roll_event(
                root_code=root_code,
                trading_day=trading_day,
                preferred_active_contract=preferred_active_contract,
                front=front,
                next_contract=next_contract,
                snapshot=snapshot,
            ),
        )

    def _pick_front_contract(
        self,
        contracts: list[ContractMetaRecord],
        preferred_active_contract: str | None,
    ) -> ContractMetaRecord:
        if preferred_active_contract:
            for item in contracts:
                if item.contract_code == preferred_active_contract:
                    return item
        return contracts[0]

    def _pick_next_contract(
        self,
        contracts: list[ContractMetaRecord],
        front: ContractMetaRecord,
        preferred_next_contract: str | None,
    ) -> ContractMetaRecord:
        if preferred_next_contract:
            for item in contracts:
                if item.contract_code == preferred_next_contract and item.contract_code != front.contract_code:
                    return item
        for item in contracts:
            if item.contract_code != front.contract_code:
                return item
        return front

    def _estimate_next_share(self, days_to_last_trade: int) -> float:
        if days_to_last_trade <= self.rules.hard_roll_days:
            return self.rules.max_next_share
        if days_to_last_trade > self.rules.roll_window_days:
            return self.rules.base_next_share

        span = self.rules.roll_window_days - self.rules.hard_roll_days
        progress = (self.rules.roll_window_days - days_to_last_trade) / max(1, span)
        share = self.rules.base_next_share + progress * (self.rules.max_next_share - self.rules.base_next_share)
        return round(min(self.rules.max_next_share, max(self.rules.base_next_share, share)), 4)

    def _build_roll_event(
        self,
        *,
        root_code: str,
        trading_day: date,
        preferred_active_contract: str | None,
        front: ContractMetaRecord,
        next_contract: ContractMetaRecord,
        snapshot: ContinuousSeriesSnapshot,
    ) -> RollEventPreview | None:
        if front.contract_code == next_contract.contract_code:
            return None

        if preferred_active_contract and preferred_active_contract != front.contract_code:
            return RollEventPreview(
                root_code=root_code,
                from_contract=preferred_active_contract,
                to_contract=front.contract_code,
                event_type="roll_detected",
                effective_trading_day=trading_day,
                reason="Preferred front contract is no longer eligible for the current trading day.",
                status="applied",
            )

        if snapshot.roll_risk_flag:
            return RollEventPreview(
                root_code=root_code,
                from_contract=front.contract_code,
                to_contract=next_contract.contract_code,
                event_type="roll_detected",
                effective_trading_day=front.last_trade_date,
                reason="Current front contract entered the configured roll window.",
                status="pending",
            )

        return None
