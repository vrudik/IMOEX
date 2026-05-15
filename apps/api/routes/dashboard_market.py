from __future__ import annotations

from html import escape
from urllib.parse import quote

from apps.api.routes.dashboard_formatting import (
    format_price_value,
    format_signed_pct,
    format_signed_value,
    format_timestamp,
)


def market_fullscreen_href(root_code: str | None) -> str:
    root_param = quote(root_code or "", safe="")
    return f"/workspace/market?root={root_param}" if root_param else "/workspace/market"


def market_overlay_style(key: str) -> tuple[str, str]:
    mapping = {
        "entry": ("#17364d", "4 3"),
        "invalidation": ("#bb7122", "5 4"),
        "target": ("#116966", "6 4"),
    }
    return mapping.get(key, ("#5c6970", "4 3"))


def format_level_distance(from_value: float | None, to_value: float | None) -> str:
    if from_value is None or to_value is None:
        return "n/a"
    base = max(abs(from_value), 0.01)
    return f"{abs(to_value - from_value) / base * 100:.2f}%"


def market_level_record(series) -> dict[str, float]:
    record: dict[str, float] = {}
    for overlay in getattr(series, "overlays", []):
        if overlay.value is not None:
            record[str(overlay.key)] = overlay.value
    return record


def market_fullscreen_action(root_code: str | None, *, language: str) -> str:
    href = market_fullscreen_href(root_code)
    label = "\u041e\u0442\u043a\u0440\u044b\u0442\u044c \u043a\u0440\u0443\u043f\u043d\u043e" if language == "ru" else "Open large"
    note = (
        "\u041e\u0442\u0434\u0435\u043b\u044c\u043d\u0430\u044f \u0432\u043a\u043b\u0430\u0434\u043a\u0430: \u0441\u0432\u0435\u0447\u0438, \u043b\u0438\u043d\u0438\u044f, \u043a\u0430\u0440\u0442\u0430 \u0443\u0440\u043e\u0432\u043d\u0435\u0439 \u0438 \u043a\u043e\u0440\u0438\u0434\u043e\u0440 \u0438\u0434\u0435\u0438."
        if language == "ru"
        else "Separate tab: candles, line, level map, and idea corridor."
    )
    return (
        '<div data-market-fullscreen-action style="display:flex;flex-wrap:wrap;align-items:center;'
        'justify-content:space-between;gap:10px;margin:0 0 14px;padding:10px 12px;border-radius:12px;'
        'border:1px solid rgba(17,105,102,0.18);background:rgba(17,105,102,0.07);">'
        f'<a class="button primary" data-market-fullscreen-link target="_blank" rel="noopener" href="{escape(href)}">{escape(label)}</a>'
        f'<span class="muted" style="font-size:13px;">{escape(note)}</span>'
        "</div>"
    )


def market_status_tone(status: str) -> str:
    normalized = status.lower()
    if normalized in {"fresh", "live", "ok"}:
        return "positive"
    if normalized in {"aging", "snapshot", "stale", "warning"}:
        return "warning"
    return "negative"


def market_overlay_copy(language: str) -> dict[str, str]:
    return {
        "entry": "\u0412\u0445\u043e\u0434" if language == "ru" else "Entry",
        "invalidation": "\u0418\u043d\u0432\u0430\u043b\u0438\u0434\u0430\u0446\u0438\u044f" if language == "ru" else "Invalidation",
        "target": "\u0426\u0435\u043b\u044c" if language == "ru" else "Target",
        "levels": "\u0423\u0440\u043e\u0432\u043d\u0438" if language == "ru" else "Levels",
    }


def market_level_copy(language: str) -> dict[str, str]:
    return {
        "price_map": "\u0426\u0435\u043d\u0430 vs \u0438\u0434\u0435\u044f" if language == "ru" else "Price vs setup",
        "price_short": "\u0426\u0435\u043d\u0430" if language == "ru" else "Price",
        "entry_short": "\u0412\u0445\u043e\u0434" if language == "ru" else "Entry",
        "target_short": "\u0426\u0435\u043b\u044c" if language == "ru" else "Target",
        "invalidation_short": "\u0418\u043d\u0432." if language == "ru" else "Invalid.",
        "idea_corridor": "\u041a\u043e\u0440\u0438\u0434\u043e\u0440 \u0438\u0434\u0435\u0438" if language == "ru" else "Idea corridor",
        "idea_change": "\u0421\u043c\u0435\u043d\u0430 \u0438\u0434\u0435\u0438" if language == "ru" else "Idea changes",
        "distance_bar": "\u0428\u043a\u0430\u043b\u0430 \u0443\u0440\u043e\u0432\u043d\u0435\u0439" if language == "ru" else "Level distance bar",
        "pending": "\u0416\u0434\u0451\u043c \u0443\u0440\u043e\u0432\u043d\u0438" if language == "ru" else "Waiting for levels",
        "pending_detail": (
            "\u041d\u0443\u0436\u043d\u044b \u0432\u0445\u043e\u0434, \u0438\u043d\u0432\u0430\u043b\u0438\u0434\u0430\u0446\u0438\u044f \u0438 \u0446\u0435\u043b\u044c."
            if language == "ru"
            else "Need entry, invalidation, and target."
        ),
        "target_hit": "\u0426\u0435\u043b\u044c \u0434\u043e\u0441\u0442\u0438\u0433\u043d\u0443\u0442\u0430" if language == "ru" else "Target reached",
        "above_entry": "\u0412\u044b\u0448\u0435 \u0432\u0445\u043e\u0434\u0430" if language == "ru" else "Above entry",
        "below_entry": "\u041d\u0438\u0436\u0435 \u0432\u0445\u043e\u0434\u0430" if language == "ru" else "Below entry",
        "above_invalidation": "\u0412\u044b\u0448\u0435 \u0438\u043d\u0432\u0430\u043b\u0438\u0434\u0430\u0446\u0438\u0438" if language == "ru" else "Above invalidation",
        "below_invalidation": "\u041d\u0438\u0436\u0435 \u0438\u043d\u0432\u0430\u043b\u0438\u0434\u0430\u0446\u0438\u0438" if language == "ru" else "Below invalidation",
        "to_target": "\u0414\u043e \u0446\u0435\u043b\u0438" if language == "ru" else "To target",
        "to_entry": "\u0414\u043e \u0432\u0445\u043e\u0434\u0430" if language == "ru" else "To entry",
        "past_target": "\u041f\u043e\u0441\u043b\u0435 \u0446\u0435\u043b\u0438" if language == "ru" else "Past target",
        "beyond_invalidation": "\u0417\u0430 \u0438\u043d\u0432\u0430\u043b\u0438\u0434\u0430\u0446\u0438\u0435\u0439" if language == "ru" else "Beyond invalidation",
    }


def market_status_label(status: str, *, language: str) -> str:
    labels = {
        "fresh": "\u0421\u0432\u0435\u0436\u0438\u0435" if language == "ru" else "Fresh",
        "live": "Live",
        "ok": "OK",
        "aging": "\u0421\u0442\u0430\u0440\u0435\u044e\u0442" if language == "ru" else "Aging",
        "snapshot": "\u0421\u043d\u0438\u043c\u043e\u043a" if language == "ru" else "Snapshot",
        "stale": "\u041d\u0435\u0441\u0432\u0435\u0436\u0438\u0435" if language == "ru" else "Stale",
        "warning": "\u041f\u0440\u0435\u0434\u0443\u043f\u0440\u0435\u0436\u0434\u0435\u043d\u0438\u0435" if language == "ru" else "Warning",
        "degraded": "\u0414\u0435\u0433\u0440\u0430\u0434\u0430\u0446\u0438\u044f" if language == "ru" else "Degraded",
    }
    return labels.get(status.lower(), status)


def market_overlay_summary(series, *, unit: str, language: str) -> str:
    overlays = getattr(series, "overlays", [])
    if not overlays:
        return ""
    labels = market_overlay_copy(language)
    unit_suffix = f" {escape(unit)}" if unit else ""
    return " | ".join(
        f"{escape(labels.get(overlay.key, overlay.key.title()))} {format_price_value(overlay.value)}{unit_suffix}"
        for overlay in overlays
        if overlay.value is not None
    )


def market_signal_horizon_label(series, *, language: str) -> str:
    horizon = getattr(series, "signal_horizon", None)
    if not horizon:
        return ""
    return ("\u0418\u0434\u0435\u044f " if language == "ru" else "Idea ") + str(horizon)


def render_market_level_strip(series, *, unit: str, language: str, compact: bool = False) -> str:
    levels = market_level_record(series)
    current_price = getattr(series, "current_price", None)
    copy = market_level_copy(language)
    unit_suffix = f" {escape(unit)}" if unit else ""
    horizon = getattr(series, "signal_horizon", None)
    signal_id = getattr(series, "signal_id", None)
    signal_attrs = (
        f' data-market-signal-horizon="{escape(str(horizon))}"' if horizon else ""
    ) + (
        f' data-market-signal-id="{escape(str(signal_id))}"' if signal_id else ""
    )
    base_style = (
        "display:flex;flex-wrap:wrap;align-items:center;gap:8px;"
        "padding:7px 8px;border-radius:10px;border:1px solid rgba(21,32,42,0.08);"
        "background:rgba(255,255,255,0.68);font-size:11px;color:#5c6970;"
        if compact
        else "display:flex;flex-wrap:wrap;align-items:center;gap:10px;"
        "padding:9px 10px;border-radius:10px;border:1px solid rgba(21,32,42,0.08);"
        "background:rgba(255,255,255,0.76);font-size:13px;color:#5c6970;"
    )
    if (
        current_price is None
        or levels.get("entry") is None
        or levels.get("target") is None
        or levels.get("invalidation") is None
    ):
        return (
            f'<div data-market-level-strip data-market-level-state="pending"{signal_attrs} style="{base_style}">'
            f'<strong style="color:#15202a;">{escape(copy["pending"])}</strong>'
            f'<span>{escape(copy["pending_detail"])}</span>'
            "</div>"
        )

    corridor_low = min(levels["invalidation"], levels["target"])
    corridor_high = max(levels["invalidation"], levels["target"])
    horizon_suffix = f' {horizon}' if horizon else ""
    corridor_text = (
        f'{copy["idea_corridor"]}{horizon_suffix}: {format_price_value(corridor_low)}-{format_price_value(corridor_high)}{unit_suffix}'
    )
    points = [
        ("entry", market_overlay_copy(language)["entry"], levels["entry"], "#17364d"),
        ("price", copy["price_short"], current_price, "#15202a"),
        ("invalidation", copy["idea_change"], levels["invalidation"], "#bb7122"),
        ("target", market_overlay_copy(language)["target"], levels["target"], "#116966"),
    ]
    chips = []
    for key, label, value, color in points:
        chips.append(
            '<span data-market-level-chip '
            f'data-level-key="{escape(key)}" '
            'style="display:inline-flex;align-items:center;gap:6px;min-width:0;padding:5px 8px;'
            'border-radius:999px;background:rgba(255,255,255,0.88);border:1px solid rgba(21,32,42,0.08);'
            'white-space:nowrap;">'
            f'<span style="width:8px;height:8px;border-radius:999px;background:{color};flex:0 0 auto;"></span>'
            f'<span>{escape(label)} {format_price_value(value)}{unit_suffix}</span>'
            "</span>"
        )
    return (
        f'<div data-market-level-strip data-market-level-state="ready"{signal_attrs} style="{base_style}">'
        f'<strong data-market-idea-corridor-summary style="color:#116966;">{escape(corridor_text)}</strong>'
        f'{"".join(chips)}'
        "</div>"
    )


def render_market_distance_bar(series, *, unit: str, language: str) -> str:
    overlays = market_level_record(series)
    current_price = getattr(series, "current_price", None)
    if (
        current_price is None
        or overlays.get("entry") is None
        or overlays.get("target") is None
        or overlays.get("invalidation") is None
    ):
        return ""

    copy = market_level_copy(language)
    points = [
        ("invalidation", copy["invalidation_short"], overlays["invalidation"], "#bb7122"),
        ("entry", copy["entry_short"], overlays["entry"], "#17364d"),
        ("price", copy["price_short"], current_price, "#15202a"),
        ("target", copy["target_short"], overlays["target"], "#116966"),
    ]
    low = min(point[2] for point in points)
    high = max(point[2] for point in points)
    span = max(high - low, max(abs(current_price), 0.01) * 0.001, 0.01)
    unit_suffix = f" {escape(unit)}" if unit else ""
    markers: list[str] = []
    chips: list[str] = []
    for key, label, value, color in points:
        left = max(0.0, min(100.0, ((value - low) / span) * 100.0))
        size = 12 if key == "price" else 9
        markers.append(
            f'<div style="position:absolute;left:calc({left:.2f}% - {size / 2:.1f}px);top:{"4px" if key == "price" else "8px"};display:grid;justify-items:center;gap:3px;">'
            f'<span style="font-size:10px;line-height:1;color:{color};font-weight:700;">{escape(label)}</span>'
            f'<span style="width:{size}px;height:{size}px;border-radius:999px;background:{color};box-shadow:0 0 0 2px rgba(255,255,255,0.94);"></span>'
            "</div>"
        )
        detail = f"{format_price_value(value)}{unit_suffix}" if key == "price" else format_level_distance(current_price, value)
        chips.append(
            '<span style="display:inline-flex;align-items:center;gap:6px;padding:6px 8px;border-radius:999px;'
            'background:rgba(255,255,255,0.82);border:1px solid rgba(21,32,42,0.08);font-size:11px;color:#5c6970;">'
            f'<span style="width:7px;height:7px;border-radius:999px;background:{color};"></span>'
            f"{escape(label)} {escape(detail)}"
            "</span>"
        )
    return (
        '<div data-market-distance-bar style="display:grid;gap:8px;">'
        f'<div style="font-size:11px;letter-spacing:0.08em;text-transform:uppercase;color:#5c6970;">{escape(copy["distance_bar"])}</div>'
        '<div style="position:relative;height:34px;">'
        '<div style="position:absolute;left:0;right:0;top:18px;height:4px;border-radius:999px;'
        'background:linear-gradient(90deg, rgba(187,113,34,0.22), rgba(23,54,77,0.18), rgba(17,105,102,0.22));"></div>'
        f'{"".join(markers)}'
        "</div>"
        f'<div style="display:flex;flex-wrap:wrap;gap:8px;">{"".join(chips)}</div>'
        "</div>"
    )


def _market_unavailable_reason(availability, *, language: str) -> tuple[str, str]:
    if availability is None:
        return (
            "no_traceable_snapshot",
            (
                "\u041d\u0435\u0442 \u0442\u0440\u0430\u0441\u0441\u0438\u0440\u0443\u0435\u043c\u043e\u0439 \u0441\u0432\u044f\u0437\u043a\u0438 \u043a\u043e\u0442\u0438\u0440\u043e\u0432\u043a\u0430+\u0441\u0432\u0435\u0447\u0438; \u0433\u0440\u0430\u0444\u0438\u043a\u0438 \u043e\u0441\u0442\u0430\u044e\u0442\u0441\u044f \u0441\u043a\u0440\u044b\u0442\u044b\u043c\u0438."
                if language == "ru"
                else "No traceable quote+candle snapshot is available; charts remain hidden."
            ),
        )

    reason_code = str(getattr(availability, "reason_code", None) or "no_traceable_snapshot")
    missing = ", ".join(str(item) for item in getattr(availability, "missing_timeframes", []) or [])
    session_type = getattr(availability, "session_type", None)
    session_value = getattr(session_type, "value", session_type)
    session_start = getattr(availability, "session_start_at", None)
    session_end = getattr(availability, "session_end_at", None)
    session_window = ""
    if session_start is not None and session_end is not None:
        session_window = f" {format_timestamp(session_start)} -> {format_timestamp(session_end)}"

    if language == "ru":
        mapping = {
            "outside_exchange_session": "\u041f\u043e \u043b\u043e\u043a\u0430\u043b\u044c\u043d\u043e\u043c\u0443 \u043a\u0430\u043b\u0435\u043d\u0434\u0430\u0440\u044e MOEX/FORTS \u0441\u0435\u0439\u0447\u0430\u0441 \u043d\u0435\u0442 \u0442\u043e\u0440\u0433\u043e\u0432\u043e\u0439 \u0441\u0435\u0441\u0441\u0438\u0438; \u0436\u0434\u0451\u043c \u0441\u043b\u0435\u0434\u0443\u044e\u0449\u0438\u0439 \u0442\u0440\u0430\u0441\u0441\u0438\u0440\u0443\u0435\u043c\u044b\u0439 \u0441\u043d\u0438\u043c\u043e\u043a \u0441\u0432\u0435\u0447\u0435\u0439.",
            "clearing_window": "\u0421\u0435\u0439\u0447\u0430\u0441 \u043e\u043a\u043d\u043e \u043a\u043b\u0438\u0440\u0438\u043d\u0433\u0430 MOEX/FORTS; \u0433\u0440\u0430\u0444\u0438\u043a\u0438 \u0432\u0435\u0440\u043d\u0443\u0442\u0441\u044f, \u043a\u043e\u0433\u0434\u0430 \u043f\u043e\u044f\u0432\u044f\u0442\u0441\u044f \u043f\u043e\u0441\u0442-\u043a\u043b\u0438\u0440\u0438\u043d\u0433\u043e\u0432\u044b\u0435 \u0441\u0432\u0435\u0447\u0438.",
            "weekend_session_no_candles": "\u041b\u043e\u043a\u0430\u043b\u044c\u043d\u044b\u0439 \u0440\u0435\u0436\u0438\u043c \u0441\u0435\u0441\u0441\u0438\u0438 - weekend; \u0441\u0432\u0435\u0447\u0438 \u043d\u0435 \u043f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u044b \u043f\u0440\u043e\u0432\u0430\u0439\u0434\u0435\u0440\u043e\u043c, \u043f\u043e\u044d\u0442\u043e\u043c\u0443 \u0433\u0440\u0430\u0444\u0438\u043a\u0438 \u0441\u043a\u0440\u044b\u0442\u044b.",
            "intraday_candles_unavailable": "\u041a\u043e\u0442\u0438\u0440\u043e\u0432\u043a\u0430 \u0435\u0441\u0442\u044c, \u043d\u043e \u043f\u0440\u043e\u0432\u0430\u0439\u0434\u0435\u0440 \u043d\u0435 \u0432\u0435\u0440\u043d\u0443\u043b \u0434\u043d\u0435\u0432\u043d\u044b\u0435 intraday-\u0441\u0432\u0435\u0447\u0438; \u043d\u0435 \u0440\u0438\u0441\u0443\u0435\u043c \u043f\u0440\u0438\u0431\u043b\u0438\u0437\u0438\u0442\u0435\u043b\u044c\u043d\u044b\u0439 1D.",
            "missing_candles": "\u041a\u043e\u0442\u0438\u0440\u043e\u0432\u043a\u0430 \u0435\u0441\u0442\u044c, \u043d\u043e \u0447\u0430\u0441\u0442\u044c \u0441\u0432\u0435\u0447\u043d\u044b\u0445 \u0441\u0440\u0435\u0437\u043e\u0432 \u043e\u0442\u0441\u0443\u0442\u0441\u0442\u0432\u0443\u0435\u0442; \u0433\u0440\u0430\u0444\u0438\u043a\u0438 \u0441\u043a\u0440\u044b\u0442\u044b \u0434\u043e \u043f\u043e\u043b\u043d\u043e\u0433\u043e \u0441\u043d\u0438\u043c\u043a\u0430.",
        }
        detail = mapping.get(reason_code, "\u041d\u0435\u0442 \u043f\u043e\u043b\u043d\u043e\u0433\u043e \u0442\u0440\u0430\u0441\u0441\u0438\u0440\u0443\u0435\u043c\u043e\u0433\u043e market-data \u0441\u043d\u0438\u043c\u043a\u0430.")
        if missing:
            detail = f"{detail} \u041d\u0435\u0442: {missing}."
        if session_value:
            detail = f"{detail} \u0421\u0435\u0441\u0441\u0438\u044f: {session_value}{session_window}."
        return reason_code, detail

    detail = str(getattr(availability, "detail", None) or "No traceable market-data snapshot is available.")
    if session_value:
        detail = f"{detail} Session: {session_value}{session_window}."
    return reason_code, detail


def render_market_unavailable_snapshot(
    *,
    language: str,
    root_code: str | None = None,
    signal_id: str | None = None,
    availability=None,
) -> str:
    copy = {
        "title": "\u0422\u0435\u043a\u0443\u0449\u0430\u044f \u0446\u0435\u043d\u0430 \u0438 \u0433\u0440\u0430\u0444\u0438\u043a\u0438" if language == "ru" else "Current price and charts",
        "subtitle": (
            "\u041f\u043e \u0432\u044b\u0431\u0440\u0430\u043d\u043d\u043e\u043c\u0443 \u0438\u043d\u0441\u0442\u0440\u0443\u043c\u0435\u043d\u0442\u0443: \u0442\u0435\u043a\u0443\u0449\u0430\u044f \u0446\u0435\u043d\u0430 \u0438 \u0442\u0440\u0438 \u043c\u0430\u0441\u0448\u0442\u0430\u0431\u0430 \u043f\u0440\u043e\u0441\u043c\u043e\u0442\u0440\u0430 \u0431\u0435\u0437 \u043f\u0435\u0440\u0435\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u044f \u0441\u0442\u0440\u0430\u043d\u0438\u0446\u044b."
            if language == "ru"
            else "Current price plus day, week, and month views for the selected instrument."
        ),
        "warning_title": (
            "\u0420\u044b\u043d\u043e\u0447\u043d\u044b\u0435 \u0434\u0430\u043d\u043d\u044b\u0435 \u0432\u0440\u0435\u043c\u0435\u043d\u043d\u043e \u043d\u0435\u0434\u043e\u0441\u0442\u0443\u043f\u043d\u044b"
            if language == "ru"
            else "Market data is temporarily unavailable"
        ),
        "warning_body": (
            "\u0413\u0440\u0430\u0444\u0438\u043a\u0438 \u0441\u043a\u0440\u044b\u0442\u044b, \u0447\u0442\u043e\u0431\u044b \u043d\u0435 \u043f\u043e\u043a\u0430\u0437\u044b\u0432\u0430\u0442\u044c \u043f\u0440\u0438\u0431\u043b\u0438\u0437\u0438\u0442\u0435\u043b\u044c\u043d\u044b\u0435 \u0438\u043b\u0438 \u0443\u0441\u0442\u0430\u0440\u0435\u0432\u0448\u0438\u0435 \u0446\u0435\u043d\u044b. \u041f\u0440\u043e\u0432\u0435\u0440\u044c\u0442\u0435 \u0441\u0442\u0430\u0442\u0443\u0441 live feed \u0432 runtime."
            if language == "ru"
            else "Charts are hidden so the app does not display approximate or stale prices. Check the live-feed status in runtime."
        ),
    }
    reason_code, reason_detail = _market_unavailable_reason(availability, language=language)
    signal_attr = f' data-market-signal-id="{escape(signal_id)}"' if signal_id else ""
    fullscreen_action = market_fullscreen_action(root_code, language=language)
    return (
        f'<section class="panel" data-market-panel data-market-root-code="{escape(root_code or "")}"{signal_attr}>'
        '<div class="panel-head">'
        "<div>"
        f'<h2>{escape(copy["title"])}</h2>'
        f'<p>{escape(copy["subtitle"])}</p>'
        "</div>"
        "</div>"
        f"{fullscreen_action}"
        '<div class="metric-list" data-market-unavailable>'
        f'<article class="action-card tone-warning" data-market-unavailable-reason="{escape(reason_code)}">'
        f'<strong>{escape(copy["warning_title"])}</strong>'
        f'<p class="muted">{escape(copy["warning_body"])}</p>'
        f'<p class="muted" data-market-unavailable-detail>{escape(reason_detail)}</p>'
        "</article>"
        "</div>"
        "</section>"
    )


def render_market_snapshot(
    snapshot,
    *,
    language: str,
    root_code: str | None = None,
    signal_id: str | None = None,
    availability=None,
) -> str:
    if snapshot is None:
        return render_market_unavailable_snapshot(
            language=language,
            root_code=root_code,
            signal_id=signal_id,
            availability=availability,
        )

    copy = {
        "title": "\u0422\u0435\u043a\u0443\u0449\u0430\u044f \u0446\u0435\u043d\u0430 \u0438 \u0433\u0440\u0430\u0444\u0438\u043a\u0438" if language == "ru" else "Current price and charts",
        "subtitle": (
            "\u041f\u043e \u0432\u044b\u0431\u0440\u0430\u043d\u043d\u043e\u043c\u0443 \u0438\u043d\u0441\u0442\u0440\u0443\u043c\u0435\u043d\u0442\u0443: \u0442\u0435\u043a\u0443\u0449\u0430\u044f \u0446\u0435\u043d\u0430 \u0438 \u0442\u0440\u0438 \u043c\u0430\u0441\u0448\u0442\u0430\u0431\u0430 \u043f\u0440\u043e\u0441\u043c\u043e\u0442\u0440\u0430 \u0431\u0435\u0437 \u043f\u0435\u0440\u0435\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u044f \u0441\u0442\u0440\u0430\u043d\u0438\u0446."
            if language == "ru"
            else "Current price plus day, week, and month views for the selected instrument."
        ),
        "current_price": "\u041f\u043e\u0441\u043b\u0435\u0434\u043d\u044f\u044f \u0446\u0435\u043d\u0430" if language == "ru" else "Last",
        "daily_change": "\u0414\u043d\u0435\u0432\u043d\u043e\u0435 \u0438\u0437\u043c\u0435\u043d\u0435\u043d\u0438\u0435" if language == "ru" else "Daily change",
        "day_high": "\u0414\u043d\u0435\u0432\u043d\u043e\u0439 \u043c\u0430\u043a\u0441\u0438\u043c\u0443\u043c" if language == "ru" else "Day high",
        "day_low": "\u0414\u043d\u0435\u0432\u043d\u043e\u0439 \u043c\u0438\u043d\u0438\u043c\u0443\u043c" if language == "ru" else "Day low",
        "updated": "\u041e\u0431\u043d\u043e\u0432\u043b\u0435\u043d\u043e" if language == "ru" else "Updated",
        "source": "\u0418\u0441\u0442\u043e\u0447\u043d\u0438\u043a" if language == "ru" else "Source",
        "warning_title": "\u041f\u043e\u0442\u043e\u043a \u0446\u0435\u043d\u044b \u0442\u0440\u0435\u0431\u0443\u0435\u0442 \u0432\u043d\u0438\u043c\u0430\u043d\u0438\u044f" if language == "ru" else "Price feed needs attention",
        "warning_body": (
            "\u0414\u0430\u043d\u043d\u044b\u0435 \u0432\u044b\u0433\u043b\u044f\u0434\u044f\u0442 \u043d\u0435\u0441\u0432\u0435\u0436\u0438\u043c\u0438 \u0438\u043b\u0438 \u0434\u0435\u0433\u0440\u0430\u0434\u0438\u0440\u043e\u0432\u0430\u0432\u0448\u0438\u043c\u0438, \u043f\u043e\u044d\u0442\u043e\u043c\u0443 \u0446\u0435\u043d\u0443 \u0441\u0442\u043e\u0438\u0442 \u0447\u0438\u0442\u0430\u0442\u044c \u0441 \u043e\u0441\u0442\u043e\u0440\u043e\u0436\u043d\u043e\u0441\u0442\u044c\u044e."
            if language == "ru"
            else "The feed looks stale or degraded, so treat the displayed price with caution."
        ),
        "status": "\u0421\u0442\u0430\u0442\u0443\u0441" if language == "ru" else "Status",
    }
    unit = f" {escape(snapshot.unit)}" if snapshot.unit else ""
    tone = market_status_tone(snapshot.status)
    fullscreen_action = market_fullscreen_action(snapshot.root_code, language=language)
    warning = ""
    if tone != "positive":
        warning_detail = snapshot.status_detail or copy["warning_body"]
        warning = (
            '<div class="metric-list" style="margin-bottom:12px;">'
            f'<article class="action-card tone-{tone}">'
            f'<strong>{escape(copy["warning_title"])}</strong>'
            f'<p class="muted">{escape(market_status_label(snapshot.status, language=language))} | {escape(warning_detail)}</p>'
            "</article>"
            "</div>"
        )
    charts = "".join(
        render_market_chart_card(series, unit=snapshot.unit, language=language)
        for series in (snapshot.daily, snapshot.weekly, snapshot.monthly)
    )
    signal_attr = f' data-market-signal-id="{escape(signal_id)}"' if signal_id else ""
    return (
        f'<section class="panel" data-market-panel data-market-root-code="{escape(snapshot.root_code)}"{signal_attr}>'
        '<div class="panel-head">'
        "<div>"
        f'<h2>{escape(copy["title"])}</h2>'
        f'<p>{escape(copy["subtitle"])}</p>'
        "</div>"
        "</div>"
        f"{fullscreen_action}"
        f"{warning}"
        '<div class="metric-list" style="grid-template-columns:repeat(auto-fit,minmax(180px,1fr));">'
        f'<article data-market-current-price><span>{escape(copy["current_price"])}</span><strong>{format_price_value(snapshot.current_price)}{unit}</strong><p class="muted">{escape(snapshot.root_code)} &middot; {escape(snapshot.contract)}</p></article>'
        f'<article><span>{escape(copy["daily_change"])}</span><strong>{format_signed_value(snapshot.price_change_abs)}{unit}</strong><p class="muted">{format_signed_pct(snapshot.price_change_pct)}</p></article>'
        f'<article><span>{escape(copy["day_high"])}</span><strong>{format_price_value(snapshot.daily.high_price)}{unit}</strong><p class="muted">{escape(snapshot.daily.points[-1].label if snapshot.daily.points else snapshot.contract)}</p></article>'
        f'<article><span>{escape(copy["day_low"])}</span><strong>{format_price_value(snapshot.daily.low_price)}{unit}</strong><p class="muted">{escape(snapshot.daily.points[0].label if snapshot.daily.points else snapshot.contract)}</p></article>'
        f'<article><span>{escape(copy["updated"])}</span><strong>{escape(format_timestamp(snapshot.as_of))}</strong><p class="muted">{escape(copy["status"])}: {escape(market_status_label(snapshot.status, language=language))}</p></article>'
        f'<article><span>{escape(copy["source"])}</span><strong>{escape(snapshot.price_source)}</strong><p class="muted">{escape(snapshot.base_asset)}</p></article>'
        "</div>"
        '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin-top:16px;">'
        f"{charts}"
        "</div>"
        "</section>"
    )


def render_market_fullscreen_page(
    snapshot,
    *,
    roots,
    selected_root: str,
    language: str,
    availability=None,
) -> str:
    copy = _market_fullscreen_copy(language)
    root_links = "".join(
        (
            f'<a class="root-pill{" is-active" if getattr(item, "root_code", "") == selected_root else ""}" '
            f'href="{escape(market_fullscreen_href(getattr(item, "root_code", "")))}">'
            f'<span>{escape(getattr(item, "root_code", ""))}</span>'
            f'<small>{escape(getattr(item, "base_asset", ""))}</small>'
            "</a>"
        )
        for item in roots
    )
    back_href = f"/workspace?root={quote(selected_root, safe='')}"
    if snapshot is None:
        reason_code, reason_detail = _market_unavailable_reason(availability, language=language)
        body = (
            f'<section class="market-empty" data-market-fullscreen-empty data-market-unavailable-reason="{escape(reason_code)}">'
            f'<h2>{escape(copy["unavailable_title"])}</h2>'
            f'<p>{escape(copy["unavailable_body"])}</p>'
            f'<p data-market-unavailable-detail>{escape(reason_detail)}</p>'
            "</section>"
        )
        source_text = copy["hidden"]
        updated_text = "n/a"
        price_text = "n/a"
        contract_text = selected_root
    else:
        body = "".join(
            render_large_market_timeframe(
                series,
                unit=snapshot.unit or "",
                language=language,
            )
            for series in (snapshot.daily, snapshot.weekly, snapshot.monthly)
            if getattr(series, "points", None)
        )
        if not body:
            body = (
                '<section class="market-empty" data-market-fullscreen-empty>'
                f'<h2>{escape(copy["unavailable_title"])}</h2>'
                f'<p>{escape(copy["unavailable_body"])}</p>'
                "</section>"
            )
        source_text = snapshot.price_source
        updated_text = format_timestamp(snapshot.as_of)
        price_text = f"{format_price_value(snapshot.current_price)} {snapshot.unit or ''}".strip()
        contract_text = f"{snapshot.root_code} {snapshot.contract} | {snapshot.base_asset}"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(copy["title"])} | {escape(selected_root)}</title>
  <style>
    :root {{
      --paper: #fbf7ef;
      --ink: #15202a;
      --muted: #5c6970;
      --line: rgba(21, 32, 42, 0.12);
      --positive: #116966;
      --negative: #b44a3d;
      --entry: #17364d;
      --risk: #bb7122;
      --target: #116966;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--paper);
      color: var(--ink);
      font-family: Inter, "Segoe UI", Arial, sans-serif;
      line-height: 1.45;
    }}
    .market-page {{
      width: min(1680px, calc(100vw - 40px));
      margin: 0 auto;
      padding: 24px 0 48px;
    }}
    .market-topbar {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 18px;
    }}
    .button, .root-pill {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      gap: 8px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgba(255, 255, 255, 0.78);
      color: var(--ink);
      text-decoration: none;
      font-weight: 700;
      padding: 9px 12px;
    }}
    .button:hover, .root-pill:hover {{ border-color: rgba(17, 105, 102, 0.45); }}
    .root-strip {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 20px;
    }}
    .root-pill {{
      min-width: 96px;
      flex-direction: column;
      align-items: flex-start;
      padding: 8px 10px;
    }}
    .root-pill small {{ color: var(--muted); font-weight: 500; }}
    .root-pill.is-active {{
      border-color: rgba(17, 105, 102, 0.55);
      background: rgba(17, 105, 102, 0.1);
      color: var(--positive);
    }}
    .market-hero {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) repeat(3, minmax(160px, 220px));
      gap: 12px;
      align-items: stretch;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgba(255, 255, 255, 0.82);
      padding: 16px;
      margin-bottom: 18px;
    }}
    h1, h2, h3, p {{ margin: 0; }}
    h1 {{ font-family: Georgia, "Times New Roman", serif; font-size: 32px; }}
    .hero-note {{ color: var(--muted); margin-top: 4px; }}
    .metric {{
      border-left: 1px solid var(--line);
      padding-left: 12px;
      display: grid;
      align-content: center;
      gap: 2px;
    }}
    .metric span {{ color: var(--muted); font-size: 12px; text-transform: uppercase; }}
    .metric strong {{ font-size: 17px; }}
    .market-nav {{
      position: sticky;
      top: 0;
      z-index: 3;
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      padding: 10px 0;
      background: linear-gradient(180deg, var(--paper), rgba(251, 247, 239, 0.9));
    }}
    .timeframe {{
      display: grid;
      gap: 14px;
      margin-top: 18px;
      padding-top: 8px;
    }}
    .timeframe-head {{
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 16px;
    }}
    .timeframe-head h2 {{
      font-family: Georgia, "Times New Roman", serif;
      font-size: 28px;
    }}
    .timeframe-head p {{ color: var(--muted); }}
    .variant-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 14px;
    }}
    .large-chart {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgba(255, 255, 255, 0.86);
      padding: 14px;
      display: grid;
      gap: 10px;
      min-width: 0;
    }}
    .chart-head {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: baseline;
    }}
    .chart-head strong {{ font-size: 18px; }}
    .chart-head span {{ color: var(--muted); font-weight: 700; }}
    .large-chart svg {{
      width: 100%;
      height: clamp(360px, 42vh, 560px);
      min-height: 360px;
      border-radius: 8px;
      background: linear-gradient(180deg, rgba(15, 108, 103, 0.06), rgba(255, 255, 255, 0.72));
      border: 1px solid rgba(21, 32, 42, 0.06);
    }}
    .chart-meta {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 8px;
      color: var(--muted);
      font-size: 13px;
    }}
    .chart-meta span {{
      padding: 7px 8px;
      border-radius: 8px;
      background: rgba(21, 32, 42, 0.04);
    }}
    .ohlc-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
      color: var(--muted);
    }}
    .ohlc-table th, .ohlc-table td {{
      text-align: right;
      padding: 8px 6px;
      border-bottom: 1px solid rgba(21, 32, 42, 0.08);
      white-space: nowrap;
    }}
    .ohlc-table th:first-child, .ohlc-table td:first-child {{ text-align: left; }}
    .market-empty {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: rgba(255, 255, 255, 0.82);
      padding: 24px;
    }}
    @media (max-width: 1180px) {{
      .market-hero {{ grid-template-columns: 1fr 1fr; }}
      .metric {{ border-left: 0; padding-left: 0; }}
      .variant-grid {{ grid-template-columns: 1fr; }}
      .large-chart svg {{ height: 420px; }}
    }}
    @media (max-width: 720px) {{
      .market-page {{ width: min(100vw - 24px, 1680px); padding-top: 14px; }}
      .market-hero {{ grid-template-columns: 1fr; }}
      h1 {{ font-size: 25px; }}
      .chart-meta {{ grid-template-columns: 1fr 1fr; }}
      .large-chart svg {{ height: 360px; }}
    }}
  </style>
</head>
<body>
  <main class="market-page" data-market-fullscreen>
    <div class="market-topbar">
      <a class="button" href="{escape(back_href)}">{escape(copy["back"])}</a>
    </div>
    <div class="root-strip" data-market-root-strip>{root_links}</div>
    <section class="market-hero">
      <div>
        <h1>{escape(copy["title"])}: {escape(contract_text)}</h1>
        <p class="hero-note">{escape(copy["subtitle"])}</p>
      </div>
      <div class="metric"><span>{escape(copy["price"])}</span><strong>{escape(price_text)}</strong></div>
      <div class="metric"><span>{escape(copy["source"])}</span><strong>{escape(source_text)}</strong></div>
      <div class="metric"><span>{escape(copy["updated"])}</span><strong>{escape(updated_text)}</strong></div>
    </section>
    <nav class="market-nav" aria-label="{escape(copy["nav"])}">
      <a class="button" href="#chart-1D">1D</a>
      <a class="button" href="#chart-1W">1W</a>
      <a class="button" href="#chart-1M">1M</a>
    </nav>
    {body}
  </main>
</body>
</html>"""


def render_large_market_timeframe(series, *, unit: str, language: str) -> str:
    if not getattr(series, "points", None):
        return ""
    labels = _market_fullscreen_copy(language)
    timeframe_title = {
        "1D": "\u0414\u0435\u043d\u044c" if language == "ru" else "Day",
        "1W": "\u041d\u0435\u0434\u0435\u043b\u044f" if language == "ru" else "Week",
        "1M": "\u041c\u0435\u0441\u044f\u0446" if language == "ru" else "Month",
    }.get(series.label, series.label)
    signal_label = market_signal_horizon_label(series, language=language)
    timeframe_note = f"{escape(series.points[0].label)} -> {escape(series.points[-1].label)} | {len(series.points)} bars"
    if signal_label:
        timeframe_note = f"{timeframe_note} | {escape(signal_label)}"
    unit_suffix = f" {escape(unit)}" if unit else ""
    meta = (
        f'<span>{escape(labels["open"])} {format_price_value(series.open_price)}{unit_suffix}</span>'
        f'<span>{escape(labels["close"])} {format_price_value(series.current_price)}{unit_suffix}</span>'
        f'<span>{escape(labels["range"])} {format_price_value(series.low_price)}-{format_price_value(series.high_price)}{unit_suffix}</span>'
        f'<span>{escape(labels["change"])} {format_signed_value(series.change_abs)}{unit_suffix} ({format_signed_pct(series.change_pct)})</span>'
    )
    variants = "".join(
        render_large_market_chart(series, variant=variant, unit=unit, language=language)
        for variant in ("candles", "line", "levels")
    )
    rows = "".join(
        "<tr>"
        f"<td>{escape(point.label)}</td>"
        f"<td>{format_price_value(point.open)}</td>"
        f"<td>{format_price_value(point.high)}</td>"
        f"<td>{format_price_value(point.low)}</td>"
        f"<td>{format_price_value(point.close)}</td>"
        "</tr>"
        for point in series.points[-12:]
    )
    return (
        f'<section class="timeframe" id="chart-{escape(series.label)}" data-market-large-timeframe="{escape(series.label)}">'
        '<div class="timeframe-head">'
        f'<div><h2>{escape(timeframe_title)} | {escape(series.label)}</h2><p>{timeframe_note}</p></div>'
        f'<strong>{format_price_value(series.current_price)}{unit_suffix}</strong>'
        "</div>"
        f'<div class="chart-meta">{meta}</div>'
        f'<div class="variant-grid">{variants}</div>'
        '<article class="large-chart" data-large-market-table>'
        f'<div class="chart-head"><strong>{escape(labels["table"])}</strong><span>{escape(series.label)}</span></div>'
        '<table class="ohlc-table"><thead><tr>'
        f'<th>{escape(labels["time"])}</th><th>O</th><th>H</th><th>L</th><th>C</th>'
        f'</tr></thead><tbody>{rows}</tbody></table>'
        "</article>"
        "</section>"
    )


def render_large_market_chart(series, *, variant: str, unit: str, language: str) -> str:
    labels = _market_fullscreen_copy(language)
    variant_labels = {
        "candles": labels["variant_candles"],
        "line": labels["variant_line"],
        "levels": labels["variant_levels"],
    }
    unit_suffix = f" {escape(unit)}" if unit else ""
    signal_label = market_signal_horizon_label(series, language=language)
    signal_hint = f'<small style="color:#5c6970;font-weight:600;">{escape(signal_label)}</small>' if signal_label else ""
    width = 960.0
    height = 480.0
    low, high = _large_market_bounds(series, include_overlays=True)
    span = max(high - low, 0.0001)

    def map_x(index: int) -> float:
        if len(series.points) == 1:
            return width / 2.0
        return (index / float(len(series.points) - 1)) * (width - 64.0) + 32.0

    def map_y(value: float) -> float:
        return height - (((value - low) / span) * (height - 64.0)) - 32.0

    grid = _large_market_grid(width=width, height=height, low=low, high=high, map_y=map_y)
    overlays = _large_market_overlay_svg(series, width=width, map_y=map_y, language=language)
    chart_overlays = overlays
    if variant == "line":
        body = _large_market_line_svg(series, map_x=map_x, map_y=map_y)
        footer_labels = (
            f'<text x="32" y="{height - 10:.1f}" fill="#5c6970" font-size="15">{escape(series.points[0].label)}</text>'
            f'<text x="{width - 32:.1f}" y="{height - 10:.1f}" text-anchor="end" fill="#5c6970" font-size="15">{escape(series.points[-1].label)}</text>'
        )
        detail_block = ""
    elif variant == "levels":
        body = _large_market_level_map_svg(
            series,
            width=width,
            height=height,
            low=low,
            high=high,
            map_y=map_y,
            language=language,
            unit=unit,
        )
        footer_labels = ""
        detail_block = render_large_market_level_map_summary(series, unit=unit, language=language)
        chart_overlays = ""
    else:
        body = _large_market_candle_svg(series, map_x=map_x, map_y=map_y, body_width=max(12.0, min(34.0, width / max(len(series.points) * 2.2, 1))))
        footer_labels = (
            f'<text x="32" y="{height - 10:.1f}" fill="#5c6970" font-size="15">{escape(series.points[0].label)}</text>'
            f'<text x="{width - 32:.1f}" y="{height - 10:.1f}" text-anchor="end" fill="#5c6970" font-size="15">{escape(series.points[-1].label)}</text>'
        )
        detail_block = ""
    current_line = ""
    if variant != "levels":
        current_y = map_y(series.current_price)
        current_line = (
            f'<line x1="24" y1="{current_y:.1f}" x2="{width - 24:.1f}" y2="{current_y:.1f}" '
            'stroke="#15202a" stroke-width="2.2" stroke-dasharray="3 5" data-market-current-line></line>'
        )
    level_strip = render_market_level_strip(series, unit=unit, language=language, compact=False)
    level_map_attr = " data-market-level-map" if variant == "levels" else ""
    return (
        f'<article class="large-chart" data-large-market-chart data-large-market-variant="{escape(variant)}">'
        '<div class="chart-head">'
        f'<strong>{escape(variant_labels.get(variant, variant))}</strong>'
        f"{signal_hint}"
        f'<span>{format_price_value(series.current_price)}{unit_suffix}</span>'
        "</div>"
        f"{level_strip}"
        f'<svg viewBox="0 0 {width:.0f} {height:.0f}" preserveAspectRatio="none" role="img"{level_map_attr}>'
        f"{grid}{chart_overlays}{current_line}{body}"
        f"{footer_labels}"
        "</svg>"
        f"{detail_block}"
        "</article>"
    )


def _large_market_bounds(series, *, include_overlays: bool) -> tuple[float, float]:
    values = [point.low for point in series.points] + [point.high for point in series.points] + [series.current_price]
    if include_overlays:
        values.extend(overlay.value for overlay in getattr(series, "overlays", []) if overlay.value is not None)
    low = min(values)
    high = max(values)
    padding = max((high - low) * 0.08, max(abs(series.current_price), 0.01) * 0.001)
    return low - padding, high + padding


def _large_market_grid(*, width: float, height: float, low: float, high: float, map_y) -> str:
    lines = []
    for index in range(5):
        value = low + ((high - low) * index / 4)
        y = map_y(value)
        lines.append(
            f'<line x1="24" y1="{y:.1f}" x2="{width - 24:.1f}" y2="{y:.1f}" '
            'stroke="rgba(21,32,42,0.08)" stroke-width="1"></line>'
            f'<text x="28" y="{max(18.0, y - 6.0):.1f}" fill="#5c6970" font-size="14">{format_price_value(value)}</text>'
        )
    return "".join(lines)


def _large_market_candle_svg(series, *, map_x, map_y, body_width: float) -> str:
    parts = []
    for index, point in enumerate(series.points):
        x = map_x(index)
        open_y = map_y(point.open)
        close_y = map_y(point.close)
        high_y = map_y(point.high)
        low_y = map_y(point.low)
        body_top = min(open_y, close_y)
        body_height = max(abs(close_y - open_y), 6.0)
        tone = "#2f7e57" if point.close >= point.open else "#b44a3d"
        parts.append(
            f'<line x1="{x:.1f}" y1="{high_y:.1f}" x2="{x:.1f}" y2="{low_y:.1f}" stroke="{tone}" stroke-width="3.2" stroke-linecap="round"></line>'
            f'<rect x="{(x - body_width / 2):.1f}" y="{body_top:.1f}" width="{body_width:.1f}" height="{body_height:.1f}" rx="4" fill="{tone}" fill-opacity="0.9"></rect>'
        )
    return "".join(parts)


def _large_market_line_svg(series, *, map_x, map_y) -> str:
    points = " ".join(f"{map_x(index):.1f},{map_y(point.close):.1f}" for index, point in enumerate(series.points))
    dots = "".join(
        f'<circle cx="{map_x(index):.1f}" cy="{map_y(point.close):.1f}" r="4.2" fill="#116966"></circle>'
        for index, point in enumerate(series.points)
    )
    area_points = f"32,448 {points} 928,448"
    return (
        f'<polygon points="{area_points}" fill="rgba(17,105,102,0.08)"></polygon>'
        f'<polyline points="{points}" fill="none" stroke="#116966" stroke-width="4.4" stroke-linecap="round" stroke-linejoin="round"></polyline>'
        f"{dots}"
    )


def render_large_market_level_map_summary(series, *, unit: str, language: str) -> str:
    levels = market_level_record(series)
    current_price = getattr(series, "current_price", None)
    if (
        current_price is None
        or levels.get("entry") is None
        or levels.get("target") is None
        or levels.get("invalidation") is None
    ):
        return ""

    copy = market_level_copy(language)
    overlay_copy = market_overlay_copy(language)
    unit_suffix = f" {escape(unit)}" if unit else ""
    items = [
        ("target", copy["to_target"], levels["target"], "#116966"),
        ("entry", copy["to_entry"], levels["entry"], "#17364d"),
        ("invalidation", copy["idea_change"], levels["invalidation"], "#bb7122"),
    ]
    chips = []
    for key, label, value, color in items:
        value_label = overlay_copy["invalidation"] if key == "invalidation" else overlay_copy.get(key, label)
        chips.append(
            '<span data-market-level-map-summary-item '
            f'data-level-key="{escape(key)}" '
            'style="display:flex;align-items:center;justify-content:space-between;gap:10px;'
            'min-width:0;padding:8px 10px;border-radius:8px;background:rgba(21,32,42,0.04);'
            'font-size:13px;color:#5c6970;">'
            f'<strong style="color:{color};white-space:nowrap;">{escape(label)}</strong>'
            f'<span>{format_level_distance(current_price, value)} | {escape(value_label)} {format_price_value(value)}{unit_suffix}</span>'
            "</span>"
        )
    return (
        '<div data-market-level-map-summary style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));'
        'gap:8px;">'
        f'{"".join(chips)}'
        "</div>"
    )


def _stack_market_label_positions(
    positions: list[tuple[str, float]],
    *,
    min_y: float,
    max_y: float,
    gap: float,
) -> dict[str, float]:
    if not positions:
        return {}
    adjusted: list[tuple[str, float]] = []
    for key, y in sorted(positions, key=lambda item: item[1]):
        next_y = max(min_y, min(max_y, y))
        if adjusted:
            next_y = max(next_y, adjusted[-1][1] + gap)
        adjusted.append((key, next_y))
    overflow = adjusted[-1][1] - max_y
    if overflow > 0:
        adjusted = [(key, max(min_y, y - overflow)) for key, y in adjusted]
        for index in range(1, len(adjusted)):
            prev_key, prev_y = adjusted[index - 1]
            key, y = adjusted[index]
            if y < prev_y + gap:
                adjusted[index] = (key, prev_y + gap)
    return dict(adjusted)


def _large_market_level_map_svg(
    series,
    *,
    width: float,
    height: float,
    low: float,
    high: float,
    map_y,
    language: str,
    unit: str,
) -> str:
    levels = market_level_record(series)
    current_price = getattr(series, "current_price", None)
    copy = market_level_copy(language)
    overlay_copy = market_overlay_copy(language)
    unit_suffix = f" {escape(unit)}" if unit else ""

    market_low = min(point.low for point in series.points)
    market_high = max(point.high for point in series.points)
    market_top = map_y(market_high)
    market_bottom = map_y(market_low)
    market_range = (
        f'<rect x="96" y="{min(market_top, market_bottom):.1f}" width="{width - 192:.1f}" '
        f'height="{max(abs(market_bottom - market_top), 6.0):.1f}" rx="14" '
        'fill="rgba(23,54,77,0.055)" stroke="rgba(23,54,77,0.12)" stroke-width="1.2"></rect>'
    )

    if (
        current_price is None
        or levels.get("entry") is None
        or levels.get("target") is None
        or levels.get("invalidation") is None
    ):
        return market_range

    markers = [
        ("target", overlay_copy["target"], levels["target"], "#116966", "6 4"),
        ("entry", overlay_copy["entry"], levels["entry"], "#17364d", "4 3"),
        ("price", copy["price_short"], current_price, "#15202a", "3 5"),
        ("invalidation", copy["idea_change"], levels["invalidation"], "#bb7122", "5 4"),
    ]
    label_positions = _stack_market_label_positions(
        [(key, map_y(value)) for key, _, value, _, _ in markers],
        min_y=48.0,
        max_y=height - 56.0,
        gap=34.0,
    )
    parts = [
        market_range,
        _market_corridor_svg(
            series,
            width=width,
            height=height,
            map_y=map_y,
            language=language,
            x1=84.0,
            x2=width - 276.0,
        ),
    ]
    horizon = getattr(series, "signal_horizon", None)
    horizon_suffix = f" {horizon}" if horizon else ""
    corridor_label = f'{copy["idea_corridor"]}{horizon_suffix}'
    corridor_y = map_y((levels["target"] + levels["invalidation"]) / 2.0)
    parts.append(
        '<text x="108" '
        f'y="{max(44.0, min(height - 42.0, corridor_y)):.1f}" '
        'fill="#116966" font-size="15" font-weight="700">'
        f"{escape(corridor_label)}</text>"
    )
    parts.append(
        f'<text x="108" y="{height - 32:.1f}" fill="#5c6970" font-size="14">'
        f'{format_price_value(market_low)}-{format_price_value(market_high)}{unit_suffix}</text>'
    )
    parts.append(
        f'<text x="{width - 108:.1f}" y="{height - 32:.1f}" text-anchor="end" fill="#5c6970" font-size="14">'
        f'{escape(series.points[0].label)} -> {escape(series.points[-1].label)}</text>'
    )
    for key, label, value, color, dasharray in markers:
        y = map_y(value)
        label_y = label_positions[key]
        is_price = key == "price"
        parts.append(
            f'<line x1="84" y1="{y:.1f}" x2="{width - 276:.1f}" y2="{y:.1f}" '
            f'stroke="{color}" stroke-width="{"3.2" if is_price else "2.4"}" '
            f'stroke-dasharray="{dasharray}" data-market-level-map-line data-level-key="{escape(key)}"></line>'
        )
        parts.append(
            f'<circle cx="{width - 276:.1f}" cy="{y:.1f}" r="{"7.0" if is_price else "5.6"}" '
            f'fill="{color}" stroke="rgba(255,255,255,0.95)" stroke-width="3"></circle>'
        )
        parts.append(
            f'<line x1="{width - 268:.1f}" y1="{y:.1f}" x2="{width - 248:.1f}" y2="{label_y - 6.0:.1f}" '
            f'stroke="{color}" stroke-width="1.2" opacity="0.45"></line>'
        )
        parts.append(
            f'<rect x="{width - 246:.1f}" y="{label_y - 24.0:.1f}" width="218" height="29" rx="8" '
            'fill="rgba(255,255,255,0.88)" stroke="rgba(21,32,42,0.09)"></rect>'
        )
        parts.append(
            f'<text x="{width - 236:.1f}" y="{label_y - 5.0:.1f}" fill="{color}" font-size="14" font-weight="700">'
            f'{escape(label)} {format_price_value(value)}{unit_suffix}</text>'
        )
    return "".join(parts)


def _market_corridor_svg(
    series,
    *,
    width: float,
    height: float,
    map_y,
    language: str,
    x1: float = 0.0,
    x2: float | None = None,
    compact: bool = False,
) -> str:
    levels = market_level_record(series)
    invalidation = levels.get("invalidation")
    target = levels.get("target")
    if invalidation is None or target is None:
        return ""
    right = width if x2 is None else x2
    y_a = map_y(invalidation)
    y_b = map_y(target)
    top = min(y_a, y_b)
    band_height = max(abs(y_a - y_b), 4.0 if compact else 8.0)
    return (
        f'<rect data-market-idea-corridor x="{x1:.1f}" y="{top:.1f}" width="{(right - x1):.1f}" '
        f'height="{band_height:.1f}" fill="rgba(17,105,102,0.09)" stroke="rgba(17,105,102,0.18)" '
        'stroke-width="1"></rect>'
    )


def _large_market_overlay_svg(series, *, width: float, map_y, language: str) -> str:
    parts = []
    parts.append(
        _market_corridor_svg(
            series,
            width=width,
            height=480.0,
            map_y=map_y,
            language=language,
            x1=24.0,
            x2=width - 24.0,
        )
    )
    for overlay in getattr(series, "overlays", []):
        if overlay.value is None:
            continue
        key = str(overlay.key)
        stroke, dasharray = market_overlay_style(overlay.key)
        y = map_y(overlay.value)
        idea_change_attr = " data-market-idea-change-line" if key == "invalidation" else ""
        parts.append(
            f'<line x1="24" y1="{y:.1f}" x2="{width - 24:.1f}" y2="{y:.1f}" stroke="{stroke}" stroke-width="2.4" '
            f'stroke-dasharray="{dasharray}" data-market-overlay-line data-overlay-key="{escape(key)}"{idea_change_attr}></line>'
        )
    return "".join(parts)


def _market_fullscreen_copy(language: str) -> dict[str, str]:
    if language == "ru":
        return {
            "title": "\u041a\u0440\u0443\u043f\u043d\u044b\u0435 \u0433\u0440\u0430\u0444\u0438\u043a\u0438",
            "subtitle": "\u041a\u0440\u0443\u043f\u043d\u044b\u0439 \u043f\u0440\u043e\u0441\u043c\u043e\u0442\u0440 live-\u0446\u0435\u043d\u044b MOEX: \u0441\u0432\u0435\u0447\u0438, \u043b\u0438\u043d\u0438\u044f \u0438 \u043a\u0430\u0440\u0442\u0430 \u0443\u0440\u043e\u0432\u043d\u0435\u0439 \u043f\u043e \u0434\u043d\u044e, \u043d\u0435\u0434\u0435\u043b\u0435 \u0438 \u043c\u0435\u0441\u044f\u0446\u0443.",
            "back": "\u041d\u0430\u0437\u0430\u0434 \u0432 workspace",
            "nav": "\u041f\u0435\u0440\u0438\u043e\u0434\u044b",
            "price": "\u0426\u0435\u043d\u0430",
            "source": "\u0418\u0441\u0442\u043e\u0447\u043d\u0438\u043a",
            "updated": "\u041e\u0431\u043d\u043e\u0432\u043b\u0435\u043d\u043e",
            "hidden": "\u0441\u043a\u0440\u044b\u0442\u043e",
            "unavailable_title": "\u0413\u0440\u0430\u0444\u0438\u043a\u0438 \u0441\u043a\u0440\u044b\u0442\u044b",
            "unavailable_body": "\u041d\u0435\u0442 \u0442\u0440\u0430\u0441\u0441\u0438\u0440\u0443\u0435\u043c\u043e\u0439 live-\u0446\u0435\u043d\u044b \u0438 \u0441\u0432\u0435\u0447\u043d\u043e\u0433\u043e \u0441\u043d\u0438\u043c\u043a\u0430, \u043f\u043e\u044d\u0442\u043e\u043c\u0443 \u0433\u0440\u0430\u0444\u0438\u043a\u0438 \u0441\u043a\u0440\u044b\u0442\u044b.",
            "variant_candles": "\u0421\u0432\u0435\u0447\u0438",
            "variant_line": "\u041b\u0438\u043d\u0438\u044f",
            "variant_levels": "\u0423\u0440\u043e\u0432\u043d\u0438 \u0438\u0434\u0435\u0438",
            "table": "OHLC",
            "time": "\u0412\u0440\u0435\u043c\u044f",
            "open": "\u041e\u0442\u043a\u0440.",
            "close": "\u0417\u0430\u043a\u0440.",
            "range": "\u0414\u0438\u0430\u043f.",
            "change": "\u0418\u0437\u043c.",
            "price_short": "\u0426\u0435\u043d\u0430",
        }
    return {
        "title": "Large Charts",
        "subtitle": "MOEX live price view with candles, line, and level map by day, week, and month.",
        "back": "Back to workspace",
        "nav": "Timeframes",
        "price": "Price",
        "source": "Source",
        "updated": "Updated",
        "hidden": "hidden",
        "unavailable_title": "Charts are hidden",
        "unavailable_body": "No traceable live quote plus candle snapshot is available.",
        "variant_candles": "Candles",
        "variant_line": "Line",
        "variant_levels": "Level map",
        "table": "OHLC",
        "time": "Time",
        "open": "Open",
        "close": "Close",
        "range": "Range",
        "change": "Change",
        "price_short": "Price",
    }


def render_market_chart_card(series, *, unit: str, language: str) -> str:
    if not series.points:
        return ""
    overlay_copy = market_overlay_copy(language)
    chart_labels = {
        "1D": "\u0414\u0435\u043d\u044c" if language == "ru" else "Day",
        "1W": "\u041d\u0435\u0434\u0435\u043b\u044f" if language == "ru" else "Week",
        "1M": "\u041c\u0435\u0441\u044f\u0446" if language == "ru" else "Month",
    }
    label = chart_labels.get(series.label, series.label)
    overlay_values = [overlay.value for overlay in getattr(series, "overlays", []) if overlay.value is not None]
    low = min([point.low for point in series.points] + overlay_values + [series.current_price])
    high = max([point.high for point in series.points] + overlay_values + [series.current_price])
    span = max(high - low, 0.0001)
    width = 220.0
    height = 92.0
    tone = "#2f7e57" if series.change_abs >= 0 else "#b44a3d"
    unit_suffix = f" {escape(unit)}" if unit else ""
    first_label = escape(series.points[0].label)
    last_label = escape(series.points[-1].label)
    range_label = "\u0414\u0438\u0430\u043f\u0430\u0437\u043e\u043d" if language == "ru" else "Range"
    open_label = "\u041e\u0442\u043a\u0440\u044b\u0442\u0438\u0435" if language == "ru" else "Open"
    close_label = "\u0417\u0430\u043a\u0440\u044b\u0442\u0438\u0435" if language == "ru" else "Close"
    change_label = "\u0418\u0437\u043c\u0435\u043d\u0435\u043d\u0438\u0435" if language == "ru" else "Change"
    levels_label = overlay_copy["levels"]
    candles: list[str] = []
    overlay_lines: list[str] = []
    body_width = max(6.0, min(16.0, width / max(len(series.points) * 1.9, 1)))

    def _map_price_y(value: float) -> float:
        return height - (((value - low) / span) * (height - 14.0)) - 7.0

    for index, point in enumerate(series.points):
        x = width / 2 if len(series.points) == 1 else (index / float(len(series.points) - 1)) * width
        open_y = _map_price_y(point.open)
        close_y = _map_price_y(point.close)
        high_y = _map_price_y(point.high)
        low_y = _map_price_y(point.low)
        body_top = min(open_y, close_y)
        body_height = max(abs(close_y - open_y), 3.0)
        candle_tone = "#2f7e57" if point.close >= point.open else "#b44a3d"
        candles.append(
            f'<line x1="{x:.1f}" y1="{high_y:.1f}" x2="{x:.1f}" y2="{low_y:.1f}" '
            f'stroke="{candle_tone}" stroke-width="1.8" stroke-linecap="round"></line>'
            f'<rect x="{(x - (body_width / 2)):.1f}" y="{body_top:.1f}" width="{body_width:.1f}" '
            f'height="{body_height:.1f}" rx="2" fill="{candle_tone}" fill-opacity="0.92"></rect>'
        )
    for overlay in getattr(series, "overlays", []):
        if overlay.value is None:
            continue
        key = str(overlay.key)
        stroke, dasharray = market_overlay_style(key)
        y = _map_price_y(overlay.value)
        idea_change_attr = " data-market-idea-change-line" if key == "invalidation" else ""
        overlay_lines.append(
            f'<line x1="0" y1="{y:.1f}" x2="{width:.1f}" y2="{y:.1f}" '
            f'stroke="{stroke}" stroke-width="1.2" stroke-dasharray="{dasharray}" opacity="0.95" '
            f'data-market-overlay-line data-overlay-key="{escape(key)}"{idea_change_attr}></line>'
        )
    current_y = _map_price_y(series.current_price)
    current_line = (
        f'<line x1="0" y1="{current_y:.1f}" x2="{width:.1f}" y2="{current_y:.1f}" stroke="#15202a" '
        'stroke-width="1.3" opacity="0.78" data-market-current-line></line>'
        f'<circle cx="{width - 6:.1f}" cy="{current_y:.1f}" r="3.4" fill="#15202a"></circle>'
    )
    overlay_summary = market_overlay_summary(series, unit=unit, language=language)
    signal_label = market_signal_horizon_label(series, language=language)
    signal_hint = f'<small style="color:#5c6970;font-weight:600;">{escape(signal_label)}</small>' if signal_label else ""
    level_strip = render_market_level_strip(series, unit=unit, language=language, compact=True)
    distance_bar = render_market_distance_bar(series, unit=unit, language=language)
    levels_line = f'<p class="muted">{escape(levels_label)} {overlay_summary}</p>' if overlay_summary else ""
    return (
        f'<article data-market-chart-card data-market-timeframe="{escape(series.label)}" style="padding:14px 16px;border-radius:18px;border:1px solid rgba(21, 32, 42, 0.1);background:rgba(255,255,255,0.72);display:grid;gap:10px;">'
        '<div style="display:flex;justify-content:space-between;gap:12px;align-items:baseline;">'
        f'<strong>{escape(label)} \u00b7 {escape(series.label)}</strong>{signal_hint}'
        f'<span style="font-weight:700;color:{tone};">{format_price_value(series.current_price)}{unit_suffix}</span>'
        "</div>"
        f"{level_strip}"
        f'<svg viewBox="0 0 220 92" preserveAspectRatio="none" data-market-chart-svg style="width:100%;height:92px;border-radius:14px;background:linear-gradient(180deg, rgba(15,108,103,0.06), rgba(255,255,255,0.6));">'
        f'<line x1="0" y1="{_map_price_y(series.open_price):.1f}" x2="220" y2="{_map_price_y(series.open_price):.1f}" stroke="rgba(21,32,42,0.08)" stroke-width="1" stroke-dasharray="4 4"></line>'
        f'{_market_corridor_svg(series, width=width, height=height, map_y=_map_price_y, language=language, compact=True)}'
        f'{"".join(overlay_lines)}'
        f"{current_line}"
        f'{"".join(candles)}'
        "</svg>"
        '<div style="display:flex;justify-content:space-between;gap:8px;font-size:12px;color:#5c6970;">'
        f"<span>{first_label}</span><span>{last_label}</span>"
        "</div>"
        f'<p class="muted">{escape(open_label)} {format_price_value(series.open_price)}{unit_suffix} | {escape(close_label)} {format_price_value(series.current_price)}{unit_suffix} | {escape(change_label)} {format_signed_value(series.change_abs)}{unit_suffix} ({format_signed_pct(series.change_pct)})</p>'
        f'<p class="muted">{escape(range_label)} {format_price_value(series.low_price)}{unit_suffix} - {format_price_value(series.high_price)}{unit_suffix}</p>'
        f"{distance_bar}"
        f"{levels_line}"
        "</article>"
    )
