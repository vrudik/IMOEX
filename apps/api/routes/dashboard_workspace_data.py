from __future__ import annotations

from urllib.parse import quote

from fastapi import HTTPException

from apps.api.routes.dashboard_delivery_data import build_delivery_activity_snapshot, build_delivery_windows
from libs.bootstrap.container import get_app_container
from libs.dashboard.contracts import (
    MarketFreshnessAlert,
    MorningBriefItem,
    MorningBriefSnapshot,
    ReadinessNextStepItem,
    ReadinessNextStepsSnapshot,
    WatchlistWorkbenchSnapshot,
    WorkspaceSignalSnapshot,
    WorkspaceSnapshot,
)
from libs.preferences.contracts import NotificationEventKind, NotificationPreferenceWorkspaceSnapshot


def build_workspace_snapshot(
    root: str | None = None,
    signal_id: str | None = None,
    activity_event_kind: NotificationEventKind | None = None,
    activity_status: str | None = None,
    activity_page: int = 1,
    activity_page_size: int = 8,
) -> WorkspaceSnapshot:
    container = get_app_container()
    resolved_root = root
    if resolved_root is None:
        resolved_root = container.preference_service.resolve_default_root()
    snapshot = container.dashboard_service.build_workspace_snapshot(root=resolved_root, signal_id=signal_id)
    preview = container.telegram_notification_service.preview(root=snapshot.selected_root, limit=3)
    telegram_delivery_ready = bool(preview.enabled and preview.configured)
    (
        delivery_activity,
        delivery_activity_filters,
        delivery_activity_by_event_kind,
        delivery_activity_by_root_scope,
        delivery_activity_by_status,
        delivery_activity_pagination,
    ) = build_delivery_activity_snapshot(
        selected_root=snapshot.selected_root,
        event_kind=activity_event_kind,
        status=activity_status,
        page=activity_page,
        page_size=activity_page_size,
    )
    return snapshot.model_copy(
        update={
            "telegram_preview_message": preview.message,
            "telegram_delivery_ready": telegram_delivery_ready,
            "market_freshness_alerts": build_market_freshness_alerts(snapshot),
            "morning_brief": build_morning_brief(snapshot, telegram_delivery_ready=telegram_delivery_ready),
            "watchlist_workbench": build_watchlist_workbench(snapshot),
            "readiness_next_steps": build_readiness_next_steps(
                snapshot,
                telegram_delivery_ready=telegram_delivery_ready,
                delivery_activity=delivery_activity,
            ),
            "delivery_windows": build_delivery_windows(selected_root=snapshot.selected_root),
            "delivery_activity": delivery_activity,
            "delivery_activity_filters": delivery_activity_filters,
            "delivery_activity_by_event_kind": delivery_activity_by_event_kind,
            "delivery_activity_by_root_scope": delivery_activity_by_root_scope,
            "delivery_activity_by_status": delivery_activity_by_status,
            "delivery_activity_pagination": delivery_activity_pagination,
        },
        deep=True,
    )


def build_market_freshness_alerts(snapshot: WorkspaceSnapshot) -> list[MarketFreshnessAlert]:
    root_param = quote(snapshot.selected_root, safe="")
    alerts: list[MarketFreshnessAlert] = []

    def add_alert(
        key: str,
        status: str,
        title: str,
        detail: str,
        href: str,
        *,
        tone: str = "warning",
    ) -> None:
        alerts.append(
            MarketFreshnessAlert(
                key=key,
                root_code=snapshot.selected_root,
                status=status,
                title=title,
                detail=detail,
                href=href,
                tone=tone,
                signals_only=True,
            )
        )

    market_snapshot = snapshot.market_snapshot
    if market_snapshot is None:
        availability = getattr(snapshot, "market_availability", None)
        detail = (
            getattr(availability, "detail", None)
            or "Selected root has no traceable quote and chart snapshot; prices and charts stay hidden."
        )
        status = getattr(availability, "status", None) or "hidden"
        add_alert(
            "market_data_hidden",
            str(status),
            "Market data is hidden",
            str(detail),
            f"/api/v1/health/product-readiness?root={root_param}",
        )
    else:
        market_status = str(market_snapshot.status or "unknown").lower()
        if market_status not in {"fresh", "live"}:
            detail = market_snapshot.status_detail or "Review product-readiness before relying on this setup."
            add_alert(
                "market_data_not_fresh",
                market_status,
                f"Market data is {market_status}",
                f"{market_status}: {detail}",
                f"/api/v1/health/product-readiness?root={root_param}",
            )

    data_mode = str(getattr(snapshot.control_panel, "data_mode", "") or "").lower()
    if data_mode == "degraded_feed":
        detail = (
            getattr(snapshot.control_panel, "data_mode_detail", None)
            or "Primary price source is degraded or unavailable."
        )
        add_alert(
            "runtime_data_mode_degraded",
            "degraded_feed",
            "Runtime feed posture is degraded",
            str(detail),
            f"/workspace/runtime?root={root_param}",
        )

    return alerts


def build_readiness_next_steps(
    snapshot: WorkspaceSnapshot,
    *,
    telegram_delivery_ready: bool,
    delivery_activity: list[object],
) -> ReadinessNextStepsSnapshot:
    root_param = quote(snapshot.selected_root, safe="")
    items: list[ReadinessNextStepItem] = []

    def add_item(
        key: str,
        title: str,
        detail: str,
        href: str,
        *,
        status: str = "review",
        tone: str = "neutral",
    ) -> None:
        items.append(
            ReadinessNextStepItem(
                key=key,
                title=title,
                detail=detail,
                href=href,
                status=status,
                tone=tone,
            )
        )

    market_snapshot = snapshot.market_snapshot
    if market_snapshot is None:
        availability = getattr(snapshot, "market_availability", None)
        detail = (
            getattr(availability, "detail", None)
            or "Prices and charts stay hidden until a traceable feed is available for this environment."
        )
        add_item(
            "market_data_truth",
            "Market data is hidden",
            str(detail),
            f"/api/v1/health/product-readiness?root={root_param}",
            status="blocked",
            tone="warning",
        )
    else:
        market_status = str(market_snapshot.status or "unknown").lower()
        if market_status in {"fresh", "live"}:
            add_item(
                "market_data_truth",
                "Market data is traceable",
                "Current price and charts are visible with a truthful feed status.",
                f"/api/v1/health/product-readiness?root={root_param}",
                status="ready",
                tone="positive",
            )
        else:
            detail = market_snapshot.status_detail or "Review product-readiness before accepting this evidence."
            add_item(
                "market_data_truth",
                "Market data needs review",
                f"{market_status}: {detail}",
                f"/api/v1/health/product-readiness?root={root_param}",
                status="review",
                tone="warning",
            )

    if telegram_delivery_ready:
        add_item(
            "telegram_mode",
            "Telegram delivery is configured",
            "Keep preview evidence attached and confirm the chosen mode in release notes.",
            f"/api/v1/notifications/telegram/preview?root={root_param}",
            status="ready",
            tone="positive",
        )
    else:
        add_item(
            "telegram_mode",
            "Telegram remains preview-only",
            "Preview evidence is available; enable delivery only by explicit operator decision.",
            f"/api/v1/notifications/telegram/preview?root={root_param}",
            status="review",
            tone="neutral",
        )

    if snapshot.review_bundle.review_due_items > 0:
        add_item(
            "daily_review",
            "Daily queue still needs review",
            f"{snapshot.review_bundle.review_due_items} watchlist item(s) need review before final notes are prepared.",
            f"/workspace?root={root_param}",
            status="open",
            tone="warning",
        )
    else:
        add_item(
            "daily_review",
            "Daily queue is reviewed",
            "Today's Operating Queue has no overdue review items.",
            f"/workspace?root={root_param}",
            status="ready",
            tone="positive",
        )

    if delivery_activity:
        add_item(
            "delivery_reason_trails",
            "Delivery reason trails exist",
            "Recent delivery activity can be reviewed with send, skip, suppress, or dry-run reasons.",
            f"/workspace/delivery-history?root={root_param}",
            status="ready",
            tone="positive",
        )
    else:
        add_item(
            "delivery_reason_trails",
            "Delivery reason trails are empty",
            "Archive preview, dry-run, skip, or suppression evidence before acceptance review.",
            f"/workspace/delivery-history?root={root_param}",
            status="review",
            tone="neutral",
        )

    open_items = sum(1 for item in items if item.status != "ready")
    ready_items = len(items) - open_items
    next_step = (
        "Close the open readiness items, then update release notes with evidence paths."
        if open_items
        else "Review evidence paths in release notes before any private-beta decision."
    )
    return ReadinessNextStepsSnapshot(
        open_items=open_items,
        ready_items=ready_items,
        items=items,
        next_step=next_step,
        signals_only=True,
    )


def build_watchlist_workbench(snapshot: WorkspaceSnapshot) -> WatchlistWorkbenchSnapshot:
    items = list(snapshot.watchlist)
    review_due_items = [item for item in items if item.review_state == "review_due"]
    reviewed_today_items = [item for item in items if item.review_state == "reviewed_today"]
    signal_linked_items = [item for item in items if item.signal_id]
    roots = sorted({item.root_code for item in items if item.root_code})
    first_due = review_due_items[0] if review_due_items else None
    next_step = "No watchlist items are queued yet."
    if first_due is not None:
        next_step = (
            "Open the linked signal context after the Morning Brief, compare it with the current evidence, then mark reviewed."
            if first_due.signal_id
            else "Open the root lane after the Morning Brief, compare current candidates, then mark reviewed."
        )
    elif items:
        next_step = "All queued watchlist items are reviewed today; keep the queue open for changed evidence."
    return WatchlistWorkbenchSnapshot(
        total_items=len(items),
        review_due_items=len(review_due_items),
        reviewed_today_items=len(reviewed_today_items),
        watched_roots=roots,
        signal_linked_items=len(signal_linked_items),
        root_level_items=len(items) - len(signal_linked_items),
        first_due_watch_key=first_due.watch_key if first_due is not None else None,
        first_due_root_code=first_due.root_code if first_due is not None else None,
        first_due_signal_id=first_due.signal_id if first_due is not None else None,
        first_due_focus_reason=first_due.focus_reason if first_due is not None else None,
        next_step=next_step,
        signals_only=True,
    )


def build_morning_brief(snapshot: WorkspaceSnapshot, *, telegram_delivery_ready: bool) -> MorningBriefSnapshot:
    market_snapshot = snapshot.market_snapshot
    market_status = market_snapshot.status if market_snapshot is not None else "hidden"
    availability = getattr(snapshot, "market_availability", None)
    market_detail = getattr(availability, "detail", None) if market_snapshot is None else None
    last_price = None
    price_unit = None
    if market_snapshot is not None:
        market_detail = market_snapshot.status_detail
        last_price = market_snapshot.current_price
        price_unit = market_snapshot.unit

    top_attention = [
        MorningBriefItem(title=item.title, detail=item.reason, href=item.href, tone=item.tone)
        for item in snapshot.attention_inbox[:3]
    ]
    dont_chase = [
        MorningBriefItem(
            title=item.title,
            detail=(
                f"{item.market_status}: {item.market_status_detail}"
                if item.market_status_detail
                else item.market_status
            ),
            href=item.href,
            tone="warning",
        )
        for item in snapshot.attention_inbox
        if item.market_status.lower() not in {"fresh", "live"}
    ][:3]
    review_highlights = list(snapshot.review_bundle.highlights or snapshot.review_bundle.outcome_summary)
    return MorningBriefSnapshot(
        market_status=market_status,
        market_detail=market_detail,
        last_price=last_price,
        price_unit=price_unit,
        top_attention=top_attention,
        review_highlights=review_highlights[:3],
        dont_chase=dont_chase,
        review_due_items=snapshot.review_bundle.review_due_items,
        watched_roots=snapshot.review_bundle.watched_root_codes[:4],
        telegram_status="ready" if telegram_delivery_ready else "preview",
        data_mode=snapshot.control_panel.data_mode,
        signals_only=True,
    )


def build_preference_workspace_snapshot(
    *,
    activity_root_scope: str | None = None,
    activity_event_kind: NotificationEventKind | None = None,
    activity_status: str | None = None,
    activity_page: int = 1,
    activity_page_size: int = 12,
) -> NotificationPreferenceWorkspaceSnapshot:
    container = get_app_container()
    snapshot = container.preference_service.build_workspace_snapshot()
    (
        delivery_activity,
        delivery_activity_filters,
        delivery_activity_by_event_kind,
        delivery_activity_by_root_scope,
        delivery_activity_by_status,
        delivery_activity_pagination,
    ) = build_delivery_activity_snapshot(
        root_scope=activity_root_scope,
        event_kind=activity_event_kind,
        status=activity_status,
        limit=activity_page_size,
        page=activity_page,
        page_size=activity_page_size,
    )
    return snapshot.model_copy(
        update={
            "delivery_windows": build_delivery_windows(selected_root=snapshot.preferences.default_root),
            "delivery_activity": delivery_activity,
            "delivery_activity_filters": delivery_activity_filters,
            "delivery_activity_by_event_kind": delivery_activity_by_event_kind,
            "delivery_activity_by_root_scope": delivery_activity_by_root_scope,
            "delivery_activity_by_status": delivery_activity_by_status,
            "delivery_activity_pagination": delivery_activity_pagination,
        },
        deep=True,
    )


def build_signal_workspace_snapshot(signal_id: str) -> WorkspaceSignalSnapshot:
    container = get_app_container()
    snapshot = container.dashboard_service.build_signal_snapshot(signal_id=signal_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail=f"Unknown signal: {signal_id}")
    preview = container.telegram_notification_service.preview(root=snapshot.signal.root, limit=3)
    return snapshot.model_copy(
        update={
            "telegram_preview_message": preview.message,
            "telegram_delivery_ready": bool(preview.enabled and preview.configured),
        },
        deep=True,
    )
