from __future__ import annotations

from html import escape

from apps.api.routes.dashboard_formatting import format_timestamp


def render_decision_timeline(items, *, title: str) -> str:
    rows = "".join(
        f'<article class="timeline-item tone-{escape(item.tone)}"><strong>{escape(item.title)}</strong><p class="muted">{escape(format_timestamp(item.at))} | {escape(item.detail)}</p></article>'
        for item in items
    ) or '<p class="empty">No decision events yet.</p>'
    return (
        '<section class="panel">'
        f'<div class="panel-head"><h2>{escape(title)}</h2><p>Narrative timeline across workflow, journal, and resolution.</p></div>'
        f'<div class="timeline-list">{rows}</div>'
        "</section>"
    )


def render_review_bundle(bundle) -> str:
    watched_roots = ", ".join(getattr(bundle, "watched_root_codes", []) or []) or "none"
    highlights = _render_list(getattr(bundle, "highlights", []), "No review highlights yet.")
    outcomes = _render_list(getattr(bundle, "outcome_summary", []), "No resolved outcomes yet.")
    tags = _render_tag_list(getattr(bundle, "tag_suggestions", []))
    next_actions = _render_list(getattr(bundle, "next_review_actions", []), "No review actions yet.")
    return (
        '<section class="panel">'
        '<div class="panel-head"><h2>Review bundle</h2><p>End-of-day and post-resolution recall in one block.</p></div>'
        '<div class="metric-list">'
        f'<article><strong>Watched roots</strong><p class="muted">{bundle.watched_roots} | {escape(watched_roots)}</p></article>'
        f'<article><strong>Watchlist review</strong><p class="muted">{getattr(bundle, "review_due_items", 0)} due / {getattr(bundle, "reviewed_today_items", 0)} done today</p></article>'
        f'<article><strong>Decisions logged</strong><p class="muted">{bundle.decisions_logged}</p></article>'
        f'<article><strong>Ignored / resolved</strong><p class="muted">{bundle.ignored_signals} / {bundle.resolved_signals}</p></article>'
        f'<article><strong>Highlights</strong><ul>{highlights}</ul></article>'
        f'<article><strong>Recent outcomes</strong><ul>{outcomes}</ul></article>'
        f'<article><strong>Suggested tags</strong><div class="filter-row">{tags}</div></article>'
        f'<article><strong>Next review actions</strong><ul>{next_actions}</ul></article>'
        "</div>"
        "</section>"
    )


def _render_list(items, empty: str) -> str:
    return "".join(f"<li>{escape(str(item))}</li>" for item in items) or f"<li>{escape(empty)}</li>"


def _render_tag_list(items) -> str:
    return "".join(f'<span class="filter-chip">{escape(str(item))}</span>' for item in items) or '<span class="filter-chip">none</span>'
