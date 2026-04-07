from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, time

from libs.domain.contracts import SessionType


@dataclass(frozen=True)
class SessionWindow:
    session_type: SessionType
    start: time
    end: time
    weekdays: tuple[int, ...]


@dataclass(frozen=True)
class SessionRuleSet:
    code: str
    effective_from: date
    windows: tuple[SessionWindow, ...]
    near_expiry_days: int = 3
    clearing_window_minutes: int = 15
    notes: tuple[str, ...] = field(default_factory=tuple)


PRE_UNIFIED_RULE_SET = SessionRuleSet(
    code="moex-split-legacy-2020-01-01",
    effective_from=date(2020, 1, 1),
    windows=(
        SessionWindow(SessionType.MORNING, time(hour=7, minute=0), time(hour=9, minute=59), (0, 1, 2, 3, 4)),
        SessionWindow(SessionType.CLEARING, time(hour=14, minute=0), time(hour=14, minute=14), (0, 1, 2, 3, 4)),
        SessionWindow(SessionType.MAIN, time(hour=10, minute=0), time(hour=18, minute=44), (0, 1, 2, 3, 4)),
        SessionWindow(SessionType.CLEARING, time(hour=18, minute=45), time(hour=18, minute=59), (0, 1, 2, 3, 4)),
        SessionWindow(SessionType.EVENING, time(hour=19, minute=0), time(hour=23, minute=49), (0, 1, 2, 3, 4)),
    ),
    notes=(
        "Temporary heuristic split-session model until MOEX calendar adapter becomes the source of truth.",
    ),
)


UNIFIED_RULE_SET = SessionRuleSet(
    code="moex-unified-2026-03-23",
    effective_from=date(2026, 3, 23),
    windows=(
        SessionWindow(SessionType.MAIN, time(hour=6, minute=50), time(hour=13, minute=59), (0, 1, 2, 3, 4)),
        SessionWindow(SessionType.CLEARING, time(hour=14, minute=0), time(hour=14, minute=14), (0, 1, 2, 3, 4)),
        SessionWindow(SessionType.MAIN, time(hour=14, minute=15), time(hour=23, minute=49), (0, 1, 2, 3, 4)),
        SessionWindow(SessionType.WEEKEND, time(hour=10, minute=0), time(hour=18, minute=59), (5, 6)),
    ),
    notes=(
        "Weekend session maps to the next trading day.",
        "Session windows are inferred defaults until MOEX reference/calendar sync is implemented.",
    ),
)


DEFAULT_RULE_SETS: tuple[SessionRuleSet, ...] = tuple(
    sorted((PRE_UNIFIED_RULE_SET, UNIFIED_RULE_SET), key=lambda item: item.effective_from)
)
