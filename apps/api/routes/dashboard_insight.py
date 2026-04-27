from __future__ import annotations

from html import escape

from apps.api.routes.dashboard_formatting import format_timestamp


def render_confidence_decomposition(decomposition) -> str:
    if decomposition is None:
        return ""
    items = "".join(
        f'<article><strong>{escape(item.label)}</strong><p class="muted">{item.value:.2f} | {escape(item.detail or "")}</p></article>'
        for item in decomposition.factors
    )
    return (
        '<section class="panel">'
        '<div class="panel-head"><h2>Confidence decomposition</h2><p>'
        f"{escape(decomposition.headline)}"
        "</p></div>"
        f'<div class="metric-list">{items}</div>'
        "</section>"
    )


def render_similar_setups(items) -> str:
    body = "".join(
        f'<article><strong>{escape(item.outcome)}</strong><p class="muted">{escape(format_timestamp(item.resolved_at))} | {item.realized_return_bps:.1f} bps | similarity {item.similarity_score:.2f}</p><p class="muted">{escape(item.note)}</p></article>'
        for item in items
    ) or '<p class="empty">No similar historical setups are available yet.</p>'
    return (
        '<section class="panel">'
        '<div class="panel-head"><h2>Similar historical setups</h2><p>Resolved analogs for quick precedent checks.</p></div>'
        f'<div class="metric-list">{body}</div>'
        "</section>"
    )
