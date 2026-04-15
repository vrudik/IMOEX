from __future__ import annotations

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

from libs.domain.contracts import SessionSnapshot, SessionType
from libs.reference.service import MoexReferenceService, get_moex_reference_service
from libs.session.rules import DEFAULT_RULE_SETS, SessionRuleSet, SessionWindow

MOEX_TIMEZONE = ZoneInfo("Europe/Moscow")


class SessionEngine:
    def __init__(
        self,
        rule_sets: tuple[SessionRuleSet, ...] = DEFAULT_RULE_SETS,
        reference_service: MoexReferenceService | None = None,
    ) -> None:
        self.rule_sets = tuple(sorted(rule_sets, key=lambda item: item.effective_from))
        self.reference_service = reference_service or get_moex_reference_service()

    def resolve(
        self,
        *,
        at: datetime,
        last_trade_date: date | None = None,
    ) -> SessionSnapshot:
        moment_local = self._to_moscow_time(at)
        calendar_day = moment_local.date()
        calendar_ref = self.reference_service.resolve_calendar_day(calendar_day)
        rule_set = calendar_ref.rule_set

        window = self._match_window(rule_set, moment_local)
        if window is None:
            return SessionSnapshot(
                calendar_day=calendar_day,
                trading_day=calendar_ref.trading_day,
                session_type=SessionType.HALTED,
                session_start_at=moment_local,
                session_end_at=moment_local,
                is_weekend_linked=calendar_ref.is_weekend_session,
                is_clearing_window=False,
                is_near_expiry=self._is_near_expiry(calendar_day, last_trade_date, rule_set),
                effective_rule_set=rule_set.code,
            )

        return SessionSnapshot(
            calendar_day=calendar_day,
            trading_day=self._resolve_trading_day(calendar_ref, window),
            session_type=window.session_type,
            session_start_at=self._combine(calendar_day, window.start),
            session_end_at=self._combine(calendar_day, window.end),
            is_weekend_linked=window.session_type == SessionType.WEEKEND,
            is_clearing_window=window.session_type == SessionType.CLEARING,
            is_near_expiry=self._is_near_expiry(calendar_day, last_trade_date, rule_set),
            effective_rule_set=rule_set.code,
        )

    def _match_window(self, rule_set: SessionRuleSet, moment_local: datetime) -> SessionWindow | None:
        current_time = moment_local.timetz().replace(tzinfo=None)
        weekday = moment_local.weekday()
        for window in rule_set.windows:
            if weekday not in window.weekdays:
                continue
            if window.start <= current_time <= window.end:
                return window
        return None

    def _resolve_trading_day(self, calendar_ref, window: SessionWindow | None) -> date:
        if window is None:
            return calendar_ref.trading_day
        if window.session_type == SessionType.WEEKEND:
            return calendar_ref.trading_day
        return calendar_ref.calendar_day

    def _is_near_expiry(self, calendar_day: date, last_trade_date: date | None, rule_set: SessionRuleSet) -> bool:
        if last_trade_date is None:
            return False
        delta = (last_trade_date - calendar_day).days
        return delta <= rule_set.near_expiry_days

    def _combine(self, day: date, value) -> datetime:
        return datetime.combine(day, value, tzinfo=MOEX_TIMEZONE)

    def _to_moscow_time(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(MOEX_TIMEZONE)
