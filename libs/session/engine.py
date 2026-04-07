from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from libs.domain.contracts import SessionSnapshot, SessionType
from libs.session.rules import DEFAULT_RULE_SETS, SessionRuleSet, SessionWindow

MOEX_TIMEZONE = ZoneInfo("Europe/Moscow")


class SessionEngine:
    def __init__(self, rule_sets: tuple[SessionRuleSet, ...] = DEFAULT_RULE_SETS) -> None:
        self.rule_sets = tuple(sorted(rule_sets, key=lambda item: item.effective_from))

    def resolve(
        self,
        *,
        at: datetime,
        last_trade_date: date | None = None,
    ) -> SessionSnapshot:
        moment_local = self._to_moscow_time(at)
        calendar_day = moment_local.date()
        rule_set = self._get_rule_set(calendar_day)

        window = self._match_window(rule_set, moment_local)
        if window is None:
            return SessionSnapshot(
                calendar_day=calendar_day,
                trading_day=self._resolve_trading_day(calendar_day, None),
                session_type=SessionType.HALTED,
                session_start_at=moment_local,
                session_end_at=moment_local,
                is_weekend_linked=calendar_day.weekday() >= 5,
                is_clearing_window=False,
                is_near_expiry=self._is_near_expiry(calendar_day, last_trade_date, rule_set),
                effective_rule_set=rule_set.code,
            )

        return SessionSnapshot(
            calendar_day=calendar_day,
            trading_day=self._resolve_trading_day(calendar_day, window),
            session_type=window.session_type,
            session_start_at=self._combine(calendar_day, window.start),
            session_end_at=self._combine(calendar_day, window.end),
            is_weekend_linked=window.session_type == SessionType.WEEKEND,
            is_clearing_window=window.session_type == SessionType.CLEARING,
            is_near_expiry=self._is_near_expiry(calendar_day, last_trade_date, rule_set),
            effective_rule_set=rule_set.code,
        )

    def _get_rule_set(self, day: date) -> SessionRuleSet:
        active = self.rule_sets[0]
        for rule_set in self.rule_sets:
            if day >= rule_set.effective_from:
                active = rule_set
        return active

    def _match_window(self, rule_set: SessionRuleSet, moment_local: datetime) -> SessionWindow | None:
        current_time = moment_local.timetz().replace(tzinfo=None)
        weekday = moment_local.weekday()
        for window in rule_set.windows:
            if weekday not in window.weekdays:
                continue
            if window.start <= current_time <= window.end:
                return window
        return None

    def _resolve_trading_day(self, calendar_day: date, window: SessionWindow | None) -> date:
        if window is None:
            if calendar_day.weekday() >= 5:
                return self._next_weekday(calendar_day)
            return calendar_day
        if window.session_type == SessionType.WEEKEND:
            return self._next_weekday(calendar_day)
        return calendar_day

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

    def _next_weekday(self, current_day: date) -> date:
        candidate = current_day + timedelta(days=1)
        while candidate.weekday() >= 5:
            candidate += timedelta(days=1)
        return candidate
