from __future__ import annotations

from html import escape

from apps.api.routes.dashboard_formatting import format_timestamp


def render_watchlist(items) -> str:
    roots = sorted({str(getattr(item, "root_code", "")) for item in items if getattr(item, "root_code", "")})
    root_options = "".join(
        f'<option value="{escape(root)}">{escape(root)}</option>'
        for root in roots
    )
    body = "".join(
        _render_watchlist_item(item)
        for item in items
    ) or '<p class="empty">No watchlist entries yet.</p>'
    return (
        '<section class="panel">'
        '<div class="panel-head">'
        '<h2>Daily Watchlist Queue</h2>'
        '<p>Promoted roots and signals stay visible between cycles, ranked by the latest review touch.</p>'
        "</div>"
        '<div class="watchlist-filters" data-watchlist-filters>'
        '<label><span>Review</span><select data-watchlist-filter-review>'
        '<option value="all">All</option>'
        '<option value="review_due">Review due</option>'
        '<option value="reviewed_today">Reviewed today</option>'
        '</select></label>'
        '<label><span>Root</span><select data-watchlist-filter-root>'
        '<option value="all">All roots</option>'
        f'{root_options}'
        '</select></label>'
        '<label><span>Link</span><select data-watchlist-filter-linked>'
        '<option value="all">All</option>'
        '<option value="signal">Signal-linked</option>'
        '<option value="root">Root-level</option>'
        '</select></label>'
        '<span class="muted" data-watchlist-filter-count></span>'
        '</div>'
        '<div class="action-row" data-watchlist-bulk-actions>'
        '<button class="button" type="button" data-watchlist-bulk-review>Mark visible reviewed</button>'
        '<button class="button ghost" type="button" data-watchlist-bulk-remove>Remove visible from queue</button>'
        '</div>'
        f'<div class="metric-list">{body}</div>'
        '<div class="status" id="watchlist-action-status"></div>'
        "</section>"
    )


def _render_watchlist_item(item) -> str:
    priority = getattr(item, "priority_rank", 0) or 0
    priority_label = f"#{priority}" if priority > 0 else "queued"
    review_state = str(getattr(item, "review_state", "review_due"))
    signal_id = getattr(item, "signal_id", None)
    watch_key = str(getattr(item, "watch_key", ""))
    signal_meta = f'<small>Signal {escape(signal_id)}</small>' if signal_id else '<small>Root-level</small>'
    reviewed_at = getattr(item, "last_reviewed_at", None) or getattr(item, "updated_at", None)
    review_button = (
        f'<button class="button" type="button" data-watchlist-review data-watch-key="{escape(watch_key)}">'
        "Mark reviewed"
        "</button>"
        if watch_key
        else ""
    )
    remove_button = (
        f'<button class="button ghost" type="button" data-watchlist-remove data-watch-key="{escape(watch_key)}">'
        "Remove"
        "</button>"
        if watch_key
        else ""
    )
    return (
        '<article class="watchlist-item" '
        f'data-watchlist-item data-watchlist-review-state="{escape(review_state)}" '
        f'data-watchlist-root="{escape(str(item.root_code))}" '
        f'data-watchlist-linked="{"signal" if signal_id else "root"}" '
        f'data-watchlist-watch-key="{escape(watch_key)}">'
        '<div class="route-head">'
        f'<div><strong>{escape(priority_label)} · {escape(item.root_code)}</strong>'
        f'<p class="muted">{escape(_watchlist_focus_reason(item))}</p></div>'
        f'<span class="badge">{escape(_watchlist_review_state_label(review_state))}</span>'
        '</div>'
        '<div class="signal-meta">'
        f'{signal_meta}'
        f'<small>Last reviewed {escape(format_timestamp(reviewed_at))}</small>'
        '</div>'
        f'<div class="action-row">{review_button}{remove_button}</div>'
        '</article>'
    )


def _watchlist_note(item) -> str:
    signal = getattr(item, "signal", None)
    return item.note or (signal.summary if signal is not None else "Root-level watch item")


def _watchlist_focus_reason(item) -> str:
    return getattr(item, "focus_reason", None) or _watchlist_note(item)


def _watchlist_review_state_label(state: str) -> str:
    labels = {
        "reviewed_today": "Reviewed today",
        "review_due": "Review due",
    }
    return labels.get(state, state.replace("_", " ").title())
