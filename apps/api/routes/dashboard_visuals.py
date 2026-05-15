from __future__ import annotations

from html import escape

from apps.api.routes.dashboard_formatting import format_timestamp


def render_metric_bars(items, *, compact: bool) -> str:
    if not items:
        return '<p class="empty">No chart data available yet.</p>'
    rendered = []
    for item in items:
        ratio = 0.0
        if item.max_value > 0:
            ratio = max(0.0, min(float(item.value) / float(item.max_value), 1.0))
        detail = f'<p class="muted">{escape(item.detail)}</p>' if item.detail and not compact else ""
        rendered.append(
            '<article class="metric-bar">'
            '<div class="metric-bar-head">'
            f"<strong>{escape(item.label)}</strong>"
            f"<span>{item.value:.2f}</span>"
            "</div>"
            '<div class="metric-bar-track">'
            f'<div class="metric-bar-fill tone-{escape(item.tone)}" style="width:{ratio * 100:.0f}%"></div>'
            "</div>"
            f"{detail}"
            "</article>"
        )
    return "".join(rendered)


def render_timeline(items, *, compact: bool) -> str:
    if not items:
        return '<p class="empty">No lifecycle events recorded yet.</p>'
    limit = 4 if compact else len(items)
    rendered = []
    for item in items[-limit:]:
        rendered.append(
            f'<article class="timeline-item tone-{escape(item.tone)}">'
            f"<strong>{escape(item.title)}</strong>"
            f'<p class="muted">{escape(format_timestamp(item.at))} | {escape(item.kind)}</p>'
            f'<p class="muted">{escape(item.detail)}</p>'
            "</article>"
        )
    return "".join(rendered)


def render_horizon_pulse(items) -> str:
    if not items:
        return '<p class="empty">No horizon pulse data available yet.</p>'
    rendered = []
    for item in items:
        rendered.append(
            f'<article class="horizon-card tone-{escape(item.tone)}">'
            f"<strong>{escape(item.horizon)}</strong>"
            f'<p class="muted">signal probability {item.signal_probability:.2f}</p>'
            f'<p class="muted">return score {item.return_score:.2f}</p>'
            f'<p class="muted">volatility {item.realized_volatility:.2f} | trend {item.trend_slope:.2f}</p>'
            "</article>"
        )
    return "".join(rendered)
