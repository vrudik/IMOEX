from __future__ import annotations

from datetime import UTC, date, datetime

from libs.domain.contracts import SessionType
from libs.session.engine import SessionEngine


def test_unified_rule_set_marks_weekend_session_as_next_trading_day() -> None:
    engine = SessionEngine()

    session = engine.resolve(
        at=datetime(2026, 4, 4, 12, 0, tzinfo=UTC),
        last_trade_date=date(2026, 4, 20),
    )

    assert session.calendar_day == date(2026, 4, 4)
    assert session.trading_day == date(2026, 4, 6)
    assert session.session_type == SessionType.WEEKEND
    assert session.is_weekend_linked is True


def test_unified_rule_set_marks_clearing_window() -> None:
    engine = SessionEngine()

    session = engine.resolve(
        at=datetime(2026, 4, 6, 11, 5, tzinfo=UTC),
        last_trade_date=date(2026, 4, 20),
    )

    assert session.calendar_day == date(2026, 4, 6)
    assert session.trading_day == date(2026, 4, 6)
    assert session.session_type == SessionType.CLEARING
    assert session.is_clearing_window is True


def test_unified_rule_set_sets_near_expiry_flag() -> None:
    engine = SessionEngine()

    session = engine.resolve(
        at=datetime(2026, 4, 6, 8, 0, tzinfo=UTC),
        last_trade_date=date(2026, 4, 8),
    )

    assert session.session_type == SessionType.MAIN
    assert session.is_near_expiry is True


def test_legacy_rule_set_is_selected_before_unified_effective_date() -> None:
    engine = SessionEngine()

    session = engine.resolve(
        at=datetime(2026, 3, 20, 5, 30, tzinfo=UTC),
        last_trade_date=date(2026, 4, 1),
    )

    assert session.effective_rule_set == "moex-split-legacy-2020-01-01"
    assert session.session_type == SessionType.MORNING
