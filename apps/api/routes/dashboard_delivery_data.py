from __future__ import annotations

import json
from datetime import UTC, datetime

from libs.bootstrap.container import get_app_container
from libs.dashboard.contracts import DeliveryHistoryWorkspaceSnapshot
from libs.preferences.contracts import (
    NotificationDeliveryActivityAction,
    NotificationDeliveryActivityFilters,
    NotificationDeliveryActivityGroup,
    NotificationDeliveryActivityItem,
    NotificationDeliveryActivityPagination,
    NotificationDeliveryWindow,
    NotificationEventKind,
)


def build_delivery_windows(*, selected_root: str | None = None) -> list[NotificationDeliveryWindow]:
    container = get_app_container()
    preferences = container.preference_service.get_preferences()
    plan = container.scheduler_service.plan()
    windows: list[NotificationDeliveryWindow] = []
    for job in plan.jobs:
        if job.command != "notify-telegram":
            continue
        event_kind = NotificationEventKind(str(job.payload.get("event_kind") or "digest"))
        root_scope = str(job.payload.get("root") or selected_root or preferences.default_root or "profile default")
        windows.append(
            NotificationDeliveryWindow(
                job_id=job.job_id,
                label=job.description,
                event_kind=event_kind,
                root_scope=root_scope,
                next_run_at=job.next_run_at,
                due_now=job.due_now,
                subscription_enabled=event_kind in preferences.subscribed_event_kinds,
                skip_next_pending=event_kind in preferences.skip_next_event_kinds,
                quiet_hours_policy=(
                    "suppressed during quiet hours"
                    if preferences.suppress_during_quiet_hours
                    else "allowed during quiet hours"
                ),
                last_run_status=job.last_run_status,
                last_run_detail=job.last_run_detail,
            )
        )
    return windows


def build_delivery_activity_snapshot(
    *,
    selected_root: str | None = None,
    root_scope: str | None = None,
    event_kind: NotificationEventKind | None = None,
    status: str | None = None,
    page: int = 1,
    page_size: int = 8,
    limit: int = 8,
    source_limit: int = 64,
) -> tuple[
    list[NotificationDeliveryActivityItem],
    NotificationDeliveryActivityFilters,
    list[NotificationDeliveryActivityGroup],
    list[NotificationDeliveryActivityGroup],
    list[NotificationDeliveryActivityGroup],
    NotificationDeliveryActivityPagination,
]:
    container = get_app_container()
    normalized_page = max(1, int(page))
    normalized_page_size = max(1, min(int(page_size), 50))
    effective_root_scope = root_scope or selected_root
    total_items = container.repository.count_notification_delivery_events(
        profile_id="default",
        root_code=effective_root_scope,
        event_kind=event_kind.value if event_kind is not None else None,
        status=status,
    )
    total_pages = max(1, (total_items + normalized_page_size - 1) // normalized_page_size)
    normalized_page = min(normalized_page, total_pages)
    offset = (normalized_page - 1) * normalized_page_size
    effective_source_limit = max(source_limit, offset + normalized_page_size, 128)
    rows = container.repository.list_recent_notification_delivery_events(
        profile_id="default",
        root_code=effective_root_scope,
        offset=0,
        limit=effective_source_limit,
    )
    paged_rows = container.repository.list_recent_notification_delivery_events(
        profile_id="default",
        root_code=effective_root_scope,
        event_kind=event_kind.value if event_kind is not None else None,
        status=status,
        offset=offset,
        limit=normalized_page_size,
    )
    all_items: list[NotificationDeliveryActivityItem] = []
    for row in rows:
        try:
            signal_ids = json.loads(row.signal_ids_json)
        except json.JSONDecodeError:
            signal_ids = []
        all_items.append(
            NotificationDeliveryActivityItem(
                activity_id=row.activity_id,
                action=NotificationDeliveryActivityAction(row.action),
                event_kind=NotificationEventKind(row.event_kind),
                delivery_source=row.delivery_source,
                root_scope=row.root_code,
                status=row.status,
                detail=row.detail,
                signal_ids=[str(item) for item in signal_ids if isinstance(item, str)],
                provider_message_id=row.provider_message_id,
                created_at=row.created_at,
            )
        )
    paged_ids = {row.activity_id for row in paged_rows}
    paged_items = [item for item in all_items if item.activity_id in paged_ids]
    paged_items.sort(key=lambda item: item.created_at, reverse=True)
    paged_items = paged_items[:limit]
    return (
        paged_items,
        NotificationDeliveryActivityFilters(
            root_scope=effective_root_scope,
            event_kind=event_kind,
            status=status,
        ),
        group_delivery_activity(
            all_items,
            value_getter=lambda item: item.event_kind.value,
            label_getter=lambda item: item.event_kind.value,
        ),
        group_delivery_activity(
            all_items,
            value_getter=lambda item: item.root_scope or "profile default",
            label_getter=lambda item: item.root_scope or "profile default",
        ),
        group_delivery_activity(
            all_items,
            value_getter=lambda item: item.status,
            label_getter=lambda item: item.status,
        ),
        NotificationDeliveryActivityPagination(
            page=normalized_page,
            page_size=normalized_page_size,
            total_items=total_items,
            total_pages=total_pages,
            has_previous=normalized_page > 1,
            has_next=normalized_page < total_pages,
        ),
    )


def group_delivery_activity(items, *, value_getter, label_getter) -> list[NotificationDeliveryActivityGroup]:
    grouped: dict[str, NotificationDeliveryActivityGroup] = {}
    for item in items:
        value = str(value_getter(item))
        if value not in grouped:
            grouped[value] = NotificationDeliveryActivityGroup(
                value=value,
                label=str(label_getter(item)),
                count=0,
            )
        grouped[value].count += 1
    return sorted(grouped.values(), key=lambda entry: (-entry.count, entry.label))


def build_delivery_history_snapshot(
    *,
    selected_root: str | None = None,
    activity_root_scope: str | None = None,
    activity_event_kind: NotificationEventKind | None = None,
    activity_status: str | None = None,
    activity_page: int = 1,
    activity_page_size: int = 24,
) -> DeliveryHistoryWorkspaceSnapshot:
    container = get_app_container()
    roots = container.contract_master_service.list_roots()
    resolved_root = selected_root or container.preference_service.resolve_default_root()
    preference_snapshot = container.preference_service.build_workspace_snapshot()
    (
        delivery_activity,
        delivery_activity_filters,
        delivery_activity_by_event_kind,
        delivery_activity_by_root_scope,
        delivery_activity_by_status,
        delivery_activity_pagination,
    ) = build_delivery_activity_snapshot(
        selected_root=resolved_root,
        root_scope=activity_root_scope,
        event_kind=activity_event_kind,
        status=activity_status,
        page=activity_page,
        page_size=activity_page_size,
        limit=activity_page_size,
        source_limit=max(256, activity_page_size * 8),
    )
    return DeliveryHistoryWorkspaceSnapshot(
        generated_at=datetime.now(UTC),
        roots=roots,
        selected_root=resolved_root,
        delivery_activity=delivery_activity,
        delivery_activity_filters=delivery_activity_filters,
        delivery_activity_by_event_kind=delivery_activity_by_event_kind,
        delivery_activity_by_root_scope=delivery_activity_by_root_scope,
        delivery_activity_by_status=delivery_activity_by_status,
        delivery_activity_pagination=delivery_activity_pagination,
        telegram_configured=bool(preference_snapshot.telegram_configured),
        telegram_enabled=bool(preference_snapshot.telegram_enabled),
    )
