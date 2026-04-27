from __future__ import annotations


def council_bullets(values: list[str], fallback: str) -> str:
    entries = [f"- {item}" for item in values if item]
    return "\n".join(entries) if entries else f"- {fallback}"


def council_joined(values: list[str], fallback: str) -> str:
    entries = [item for item in values if item]
    return "; ".join(entries) if entries else fallback


def council_packet(items: list[tuple[str, str]], fallback: str) -> str:
    lines = [f"- {label}: {value}" for label, value in items if value]
    return "\n".join(lines) if lines else f"- {fallback}"


def council_role_labels(language: str) -> dict[str, str]:
    is_ru = language == "ru"
    return {
        "trend_vol": "Аналитик тренда и волатильности" if is_ru else "Trend / volatility analyst",
        "flow_liquidity": "Аналитик потока и ликвидности" if is_ru else "Flow / liquidity analyst",
        "oi_roll": "Аналитик OI и ролла" if is_ru else "OI / roll analyst",
        "macro_event": "Аналитик макро-событий" if is_ru else "Macro-event analyst",
        "skeptic": "Скептик" if is_ru else "Skeptic",
        "arbiter": "Арбитр" if is_ru else "Arbiter",
    }
