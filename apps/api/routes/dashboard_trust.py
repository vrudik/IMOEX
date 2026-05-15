from __future__ import annotations

from html import escape


def render_trust_ribbon(ribbon) -> str:
    items = "".join(
        f'<article class="action-card tone-{escape(item.tone)}"><strong>{escape(item.label)}</strong><p class="muted">{escape(item.value)} | {escape(item.detail or "")}</p></article>'
        for item in ribbon.items
    )
    return (
        '<section class="panel">'
        '<div class="panel-head">'
        '<h2>Trust ribbon</h2>'
        f'<p>{escape(ribbon.headline)}</p>'
        "</div>"
        f'<div class="action-list">{items}</div>'
        "</section>"
    )
