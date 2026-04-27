from __future__ import annotations

from html import escape

from apps.api.routes.dashboard_formatting import (
    format_price_value,
    format_signed_pct,
    format_signed_value,
    format_timestamp,
)


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


def render_market_unavailable_snapshot(
    *,
    language: str,
    root_code: str | None = None,
    signal_id: str | None = None,
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
    signal_attr = f' data-market-signal-id="{escape(signal_id)}"' if signal_id else ""
    return (
        f'<section class="panel" data-market-panel data-market-root-code="{escape(root_code or "")}"{signal_attr}>'
        '<div class="panel-head">'
        f'<h2>{escape(copy["title"])}</h2>'
        f'<p>{escape(copy["subtitle"])}</p>'
        "</div>"
        '<div class="metric-list" data-market-unavailable>'
        '<article class="action-card tone-warning">'
        f'<strong>{escape(copy["warning_title"])}</strong>'
        f'<p class="muted">{escape(copy["warning_body"])}</p>'
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
) -> str:
    if snapshot is None:
        return render_market_unavailable_snapshot(language=language, root_code=root_code, signal_id=signal_id)

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
        f'<h2>{escape(copy["title"])}</h2>'
        f'<p>{escape(copy["subtitle"])}</p>'
        "</div>"
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


def render_market_chart_card(series, *, unit: str, language: str) -> str:
    if not series.points:
        return ""
    overlay_copy = market_overlay_copy(language)
    level_copy = market_level_copy(language)
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
        stroke, dasharray = market_overlay_style(overlay.key)
        y = _map_price_y(overlay.value)
        overlay_label = escape(overlay_copy.get(overlay.key, overlay.key.title()))
        overlay_lines.append(
            f'<line x1="0" y1="{y:.1f}" x2="{width:.1f}" y2="{y:.1f}" '
            f'stroke="{stroke}" stroke-width="1.2" stroke-dasharray="{dasharray}" opacity="0.95"></line>'
            f'<text x="{width - 6:.1f}" y="{max(12.0, min(height - 4.0, y - 2.0)):.1f}" '
            f'text-anchor="end" fill="{stroke}" font-size="10" font-weight="700">{overlay_label}</text>'
        )
    current_y = _map_price_y(series.current_price)
    current_line = (
        f'<line x1="0" y1="{current_y:.1f}" x2="{width:.1f}" y2="{current_y:.1f}" stroke="#15202a" '
        'stroke-width="1.3" opacity="0.78" data-market-current-line></line>'
        f'<circle cx="{width - 6:.1f}" cy="{current_y:.1f}" r="3.4" fill="#15202a"></circle>'
        f'<text x="6" y="{max(12.0, min(height - 4.0, current_y - 4.0)):.1f}" fill="#15202a" '
        f'font-size="10" font-weight="700">{escape(level_copy["price_short"])}</text>'
    )
    overlay_summary = market_overlay_summary(series, unit=unit, language=language)
    distance_bar = render_market_distance_bar(series, unit=unit, language=language)
    levels_line = f'<p class="muted">{escape(levels_label)} {overlay_summary}</p>' if overlay_summary else ""
    return (
        f'<article data-market-chart-card data-market-timeframe="{escape(series.label)}" style="padding:14px 16px;border-radius:18px;border:1px solid rgba(21, 32, 42, 0.1);background:rgba(255,255,255,0.72);display:grid;gap:10px;">'
        '<div style="display:flex;justify-content:space-between;gap:12px;align-items:baseline;">'
        f'<strong>{escape(label)} \u00b7 {escape(series.label)}</strong>'
        f'<span style="font-weight:700;color:{tone};">{format_price_value(series.current_price)}{unit_suffix}</span>'
        "</div>"
        f'<svg viewBox="0 0 220 92" preserveAspectRatio="none" data-market-chart-svg style="width:100%;height:92px;border-radius:14px;background:linear-gradient(180deg, rgba(15,108,103,0.06), rgba(255,255,255,0.6));">'
        f'<line x1="0" y1="{_map_price_y(series.open_price):.1f}" x2="220" y2="{_map_price_y(series.open_price):.1f}" stroke="rgba(21,32,42,0.08)" stroke-width="1" stroke-dasharray="4 4"></line>'
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
