from __future__ import annotations

from html import escape
from urllib.parse import urlencode

from apps.api.routes.dashboard_formatting import format_timestamp
from libs.preferences.contracts import (
    NotificationDeliveryActivityAction,
    NotificationDeliveryActivityFilters,
    NotificationDeliveryActivityGroup,
    NotificationDeliveryActivityPagination,
    NotificationEventKind,
)


def render_delivery_windows(items) -> str:
    if not items:
        return '<p class="empty">No delivery windows configured yet.</p>'
    rendered = []
    for item in items:
        next_run = escape(format_timestamp(item.next_run_at)) if item.next_run_at is not None else "not scheduled"
        last_status = escape(item.last_run_status or "never")
        detail = escape(item.last_run_detail or item.quiet_hours_policy)
        skip_label = "Mute next digest" if item.event_kind == NotificationEventKind.DIGEST else "Skip next brief"
        skip_button = (
            f'<button class="button delivery-undo-skip" type="button" data-event-kind="{escape(item.event_kind.value)}">Undo skip</button>'
            if item.skip_next_pending
            else f'<button class="button delivery-skip-next" type="button" data-event-kind="{escape(item.event_kind.value)}">{escape(skip_label)}</button>'
        )
        rendered.append(
            f'<article class="delivery-card tone-{"positive" if item.subscription_enabled else "warning"}">'
            f"<strong>{escape(item.event_kind.value)}</strong>"
            f'<p class="muted">{escape(item.label)}</p>'
            f'<p class="muted">root {escape(item.root_scope)} | next {next_run}</p>'
            f'<p class="muted">subscription {"on" if item.subscription_enabled else "off"} | {escape(item.quiet_hours_policy)}</p>'
            f'<p class="muted">skip next {"pending" if item.skip_next_pending else "off"}</p>'
            f'<p class="muted">last run {last_status} | {detail}</p>'
            '<div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:10px;">'
            f'<button class="button delivery-send-now" type="button" data-event-kind="{escape(item.event_kind.value)}">Send now</button>'
            f'<button class="button delivery-send-now-force" type="button" data-event-kind="{escape(item.event_kind.value)}">Send now ignoring quiet hours</button>'
            f"{skip_button}"
            "</div>"
            "</article>"
        )
    return "".join(rendered)


def _delivery_activity_tone(status: str) -> str:
    if status == "sent":
        return "positive"
    if status in {"disabled", "error", "failed", "not_configured"}:
        return "negative"
    return "warning"


def delivery_activity_reason(status: str) -> str:
    reasons = {
        "sent": "Sent because delivery was allowed and Telegram accepted the message.",
        "dry_run": "Skipped because this was a dry run.",
        "quiet_hours": "Suppressed because quiet hours are active.",
        "skip_next": "Skipped because the next run was muted by the operator.",
        "event_disabled": "Suppressed because this event type is disabled in preferences.",
        "no_candidates": "Skipped because no matching signals were found.",
        "disabled": "Suppressed because Telegram delivery is disabled.",
        "not_configured": "Suppressed because Telegram credentials or chat id are missing.",
    }
    return reasons.get(status, f"Delivery ended with status {status}.")


def render_delivery_activity(items) -> str:
    if not items:
        return '<p class="empty">No delivery actions recorded yet.</p>'
    rendered = []
    for item in items:
        title = {
            NotificationDeliveryActivityAction.SEND_NOW: "Manual send",
            NotificationDeliveryActivityAction.SEND_NOW_FORCE: "Manual send with quiet-hours override",
            NotificationDeliveryActivityAction.SCHEDULE_DELIVERY: "Scheduled delivery",
            NotificationDeliveryActivityAction.SKIP_NEXT: "Skip next",
            NotificationDeliveryActivityAction.UNDO_SKIP: "Undo skip",
        }.get(item.action, item.action.value)
        signal_info = (
            f"signals {len(item.signal_ids)}"
            if item.signal_ids
            else "no signal ids"
        )
        source = escape(item.delivery_source or "manual")
        root_scope = escape(item.root_scope or "profile default")
        tone = escape(_delivery_activity_tone(item.status))
        reason = escape(delivery_activity_reason(item.status))
        rendered.append(
            f'<article class="delivery-card tone-{tone}">'
            f"<strong>{escape(title)}</strong>"
            f'<p class="muted">{escape(item.event_kind.value)} | {escape(format_timestamp(item.created_at))}</p>'
            f'<p class="muted">root {root_scope} | source {source} | status {escape(item.status)}</p>'
            f'<p class="muted" data-delivery-reason><strong>Reason trail:</strong> {reason}</p>'
            f'<p class="muted" data-delivery-evidence><strong>Evidence:</strong> {escape(item.detail)}</p>'
            f'<p class="muted">{escape(signal_info)}'
            f'{" | provider message " + escape(item.provider_message_id) if item.provider_message_id else ""}</p>'
            "</article>"
        )
    return "".join(rendered)


def delivery_activity_filter_href(
    base_path: str,
    *,
    root: str | None = None,
    signal_id: str | None = None,
    activity_root_scope: str | None = None,
    activity_event_kind: NotificationEventKind | None = None,
    activity_status: str | None = None,
) -> str:
    params: dict[str, str] = {}
    if root is not None:
        params["root"] = root
    if signal_id is not None:
        params["signal_id"] = signal_id
    if activity_root_scope is not None:
        params["activity_root_scope"] = activity_root_scope
    if activity_event_kind is not None:
        params["activity_event_kind"] = activity_event_kind.value
    if activity_status is not None:
        params["activity_status"] = activity_status
    if not params:
        return base_path
    return f"{base_path}?{urlencode(params)}"


def render_delivery_activity_controls(
    *,
    base_path: str,
    filters: NotificationDeliveryActivityFilters,
    by_event_kind: list[NotificationDeliveryActivityGroup],
    by_root_scope: list[NotificationDeliveryActivityGroup],
    by_status: list[NotificationDeliveryActivityGroup],
    root: str | None = None,
    signal_id: str | None = None,
) -> str:
    clear_href = delivery_activity_filter_href(base_path, root=root, signal_id=signal_id)
    event_links = [
        (
            '<a class="filter-chip'
            f'{" is-active" if filters.event_kind is None else ""}" '
            f'href="{escape(clear_href)}">All events</a>'
        )
    ]
    for item in by_event_kind:
        href = delivery_activity_filter_href(
            base_path,
            root=root,
            signal_id=signal_id,
            activity_root_scope=filters.root_scope,
            activity_event_kind=NotificationEventKind(item.value),
            activity_status=filters.status,
        )
        event_links.append(
            '<a class="filter-chip'
            f'{" is-active" if filters.event_kind is not None and filters.event_kind.value == item.value else ""}" '
            f'href="{escape(href)}">{escape(item.label)} ({item.count})</a>'
        )
    root_links: list[str] = []
    if len(by_root_scope) > 1:
        root_links.append(
            '<a class="filter-chip'
            f'{" is-active" if filters.root_scope is None else ""}" '
            f'href="{escape(delivery_activity_filter_href(base_path, root=root, signal_id=signal_id, activity_event_kind=filters.event_kind, activity_status=filters.status))}">All roots</a>'
        )
        for item in by_root_scope:
            href = delivery_activity_filter_href(
                base_path,
                root=root,
                signal_id=signal_id,
                activity_root_scope=item.value,
                activity_event_kind=filters.event_kind,
                activity_status=filters.status,
            )
            root_links.append(
                '<a class="filter-chip'
                f'{" is-active" if filters.root_scope == item.value else ""}" '
                f'href="{escape(href)}">{escape(item.label)} ({item.count})</a>'
            )
    status_links = [
        (
            '<a class="filter-chip'
            f'{" is-active" if filters.status is None else ""}" '
            f'href="{escape(delivery_activity_filter_href(base_path, root=root, signal_id=signal_id, activity_root_scope=filters.root_scope, activity_event_kind=filters.event_kind))}">All statuses</a>'
        )
    ]
    for item in by_status:
        href = delivery_activity_filter_href(
            base_path,
            root=root,
            signal_id=signal_id,
            activity_root_scope=filters.root_scope,
            activity_event_kind=filters.event_kind,
            activity_status=item.value,
        )
        status_links.append(
            '<a class="filter-chip'
            f'{" is-active" if filters.status == item.value else ""}" '
            f'href="{escape(href)}">{escape(item.label)} ({item.count})</a>'
        )
    summary_cards = []
    for group_title, groups in (
        ("By event", by_event_kind),
        ("By root", by_root_scope),
        ("By status", by_status),
    ):
        if not groups:
            continue
        summary_cards.append(
            '<article class="summary-card">'
            f"<strong>{escape(group_title)}</strong>"
            f'<span>{escape(", ".join(f"{item.label} {item.count}" for item in groups[:4]))}</span>'
            "</article>"
        )
    blocks = [
        '<div class="filter-stack">',
        '<div><strong>Event kind</strong><div class="filter-row">' + "".join(event_links) + "</div></div>",
    ]
    if root_links:
        blocks.append('<div><strong>Root scope</strong><div class="filter-row">' + "".join(root_links) + "</div></div>")
    blocks.append('<div><strong>Status</strong><div class="filter-row">' + "".join(status_links) + "</div></div>")
    blocks.append('<div class="stack" style="margin-top:8px;">' + "".join(summary_cards) + "</div>")
    blocks.append("</div>")
    return "".join(blocks)


def render_delivery_activity_footer(
    *,
    base_path: str,
    export_path: str,
    filters: NotificationDeliveryActivityFilters,
    pagination: NotificationDeliveryActivityPagination,
    root: str | None = None,
    signal_id: str | None = None,
) -> str:
    links: list[str] = []
    if pagination.has_previous:
        prev_href = delivery_activity_filter_href(
            base_path,
            root=root,
            signal_id=signal_id,
            activity_root_scope=filters.root_scope,
            activity_event_kind=filters.event_kind,
            activity_status=filters.status,
        )
        sep = "&" if "?" in prev_href else "?"
        links.append(f'<a class="filter-chip" href="{escape(prev_href)}{sep}activity_page={pagination.page - 1}&activity_page_size={pagination.page_size}">Previous</a>')
    if pagination.has_next:
        next_href = delivery_activity_filter_href(
            base_path,
            root=root,
            signal_id=signal_id,
            activity_root_scope=filters.root_scope,
            activity_event_kind=filters.event_kind,
            activity_status=filters.status,
        )
        sep = "&" if "?" in next_href else "?"
        links.append(f'<a class="filter-chip" href="{escape(next_href)}{sep}activity_page={pagination.page + 1}&activity_page_size={pagination.page_size}">Next</a>')
    export_base = delivery_activity_filter_href(
        export_path,
        root=root,
        signal_id=signal_id,
        activity_root_scope=filters.root_scope,
        activity_event_kind=filters.event_kind,
        activity_status=filters.status,
    )
    export_csv = f'{escape(export_base)}{"&" if "?" in export_base else "?"}export_format=csv'
    export_jsonl = f'{escape(export_base)}{"&" if "?" in export_base else "?"}export_format=jsonl'
    meta = (
        f'<p class="muted">Page {pagination.page} of {pagination.total_pages} | '
        f'{pagination.total_items} total events | page size {pagination.page_size}</p>'
    )
    return (
        '<div class="filter-stack" style="margin-top:14px;">'
        f"{meta}"
        '<div class="filter-row">'
        + "".join(links)
        + f'<a class="filter-chip" href="{export_csv}">Export CSV</a>'
        + f'<a class="filter-chip" href="{export_jsonl}">Export JSONL</a>'
        + "</div></div>"
    )
