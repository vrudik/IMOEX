from __future__ import annotations

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

MOSCOW_TIMEZONE = ZoneInfo("Europe/Moscow")


def format_price_value(value: float | None) -> str:
    if value is None:
        return "n/a"
    if abs(value) >= 1000:
        return f"{value:,.2f}".replace(",", " ")
    return f"{value:.2f}"


def format_signed_value(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:+.2f}"


def format_signed_pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:+.2%}"


def format_optional(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.4f}"


def format_timestamp(value: datetime | None) -> str:
    if value is None:
        return "n/a"
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(MOSCOW_TIMEZONE).strftime("%Y-%m-%d %H:%M:%S MSK")


def format_calendar_date(value: date | None, *, language: str) -> str:
    if value is None:
        return "n/a"
    if language == "ru":
        return value.strftime("%d.%m.%Y")
    return value.isoformat()


def format_expiry_countdown(days_to_expiry: int, expiry_date: date | None, *, language: str) -> str:
    if expiry_date is None:
        return str(days_to_expiry)
    formatted_date = format_calendar_date(expiry_date, language=language)
    if language == "ru":
        return f"{days_to_expiry} \u00b7 \u0434\u043e {formatted_date}"
    return f"{days_to_expiry} \u00b7 until {formatted_date}"
