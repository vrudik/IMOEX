from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from libs.session.rules import SessionRuleSet


@dataclass(frozen=True)
class MoexCalendarDay:
    calendar_day: date
    trading_day: date
    is_weekend_session: bool
    rule_set: SessionRuleSet


@dataclass(frozen=True)
class MoexContractReference:
    contract_code: str
    root_code: str
    expiry_date: date
    last_trade_date: date
    tick_size: float
    lot_size: int
    currency: str
    active_flag: bool = True
