from __future__ import annotations

from fastapi import HTTPException

from apps.api.routes.dashboard_delivery_data import build_delivery_activity_snapshot, build_delivery_windows
from libs.bootstrap.container import get_app_container
from libs.dashboard.contracts import MorningBriefItem, MorningBriefSnapshot, WorkspaceSignalSnapshot, WorkspaceSnapshot
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
            "morning_brief": build_morning_brief(snapshot, telegram_delivery_ready=telegram_delivery_ready),
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


def build_morning_brief(snapshot: WorkspaceSnapshot, *, telegram_delivery_ready: bool) -> MorningBriefSnapshot:
    market_snapshot = snapshot.market_snapshot
    market_status = market_snapshot.status if market_snapshot is not None else "hidden"
    market_detail = None
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
