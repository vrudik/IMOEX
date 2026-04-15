from __future__ import annotations

import json
from datetime import UTC, datetime
from html import escape
from urllib.parse import urlencode

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse

from libs.bootstrap.container import get_app_container
from libs.dashboard.contracts import (
    DashboardQualityPair,
    DashboardSnapshot,
    DeliveryHistoryWorkspaceSnapshot,
    JournalWorkspaceSnapshot,
    WorkspaceActionItem,
    WorkspaceSignalSnapshot,
    WorkspaceSnapshot,
)
from libs.domain.contracts import JournalEntryKind, SignalStatus
from libs.notifications.contracts import TelegramNotificationSendRequest, TelegramNotificationSendResult
from libs.preferences.contracts import (
    NotificationDeliveryActivityAction,
    NotificationDeliveryActivityExportFormat,
    NotificationDeliveryActivityFilters,
    NotificationDeliveryActivityGroup,
    NotificationDeliveryActivityItem,
    NotificationDeliveryActivityPagination,
    NotificationDeliveryWindow,
    NotificationEventKind,
    NotificationDeliverySkipRequest,
    NotificationPreferenceUpdate,
    NotificationPreferenceWorkspaceSnapshot,
)
from libs.runtime.feature_flags import is_feature_enabled

router = APIRouter(tags=["dashboard"])


def _ensure_dashboard_enabled() -> None:
    if not is_feature_enabled("dashboard_ui"):
        raise HTTPException(status_code=404, detail="Dashboard feature is disabled.")


def _build_delivery_windows(*, selected_root: str | None = None) -> list[NotificationDeliveryWindow]:
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


def _build_delivery_activity_snapshot(
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
        _group_delivery_activity(
            all_items,
            value_getter=lambda item: item.event_kind.value,
            label_getter=lambda item: item.event_kind.value,
        ),
        _group_delivery_activity(
            all_items,
            value_getter=lambda item: item.root_scope or "profile default",
            label_getter=lambda item: item.root_scope or "profile default",
        ),
        _group_delivery_activity(
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


def _group_delivery_activity(items, *, value_getter, label_getter) -> list[NotificationDeliveryActivityGroup]:
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


def _build_workspace_snapshot(
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
    (
        delivery_activity,
        delivery_activity_filters,
        delivery_activity_by_event_kind,
        delivery_activity_by_root_scope,
        delivery_activity_by_status,
        delivery_activity_pagination,
    ) = _build_delivery_activity_snapshot(
        selected_root=snapshot.selected_root,
        event_kind=activity_event_kind,
        status=activity_status,
        page=activity_page,
        page_size=activity_page_size,
    )
    return snapshot.model_copy(
        update={
            "telegram_preview_message": preview.message,
            "telegram_delivery_ready": bool(preview.enabled and preview.configured),
            "delivery_windows": _build_delivery_windows(selected_root=snapshot.selected_root),
            "delivery_activity": delivery_activity,
            "delivery_activity_filters": delivery_activity_filters,
            "delivery_activity_by_event_kind": delivery_activity_by_event_kind,
            "delivery_activity_by_root_scope": delivery_activity_by_root_scope,
            "delivery_activity_by_status": delivery_activity_by_status,
            "delivery_activity_pagination": delivery_activity_pagination,
        },
        deep=True,
    )


def _build_preference_workspace_snapshot(
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
    ) = _build_delivery_activity_snapshot(
        root_scope=activity_root_scope,
        event_kind=activity_event_kind,
        status=activity_status,
        limit=activity_page_size,
        page=activity_page,
        page_size=activity_page_size,
    )
    return snapshot.model_copy(
        update={
            "delivery_windows": _build_delivery_windows(selected_root=snapshot.preferences.default_root),
            "delivery_activity": delivery_activity,
            "delivery_activity_filters": delivery_activity_filters,
            "delivery_activity_by_event_kind": delivery_activity_by_event_kind,
            "delivery_activity_by_root_scope": delivery_activity_by_root_scope,
            "delivery_activity_by_status": delivery_activity_by_status,
            "delivery_activity_pagination": delivery_activity_pagination,
        },
        deep=True,
    )


def _build_signal_workspace_snapshot(signal_id: str) -> WorkspaceSignalSnapshot:
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


def _build_delivery_history_snapshot(
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
    ) = _build_delivery_activity_snapshot(
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


@router.get("/", include_in_schema=False)
async def get_root_redirect() -> RedirectResponse:
    _ensure_dashboard_enabled()
    return RedirectResponse(url="/workspace", status_code=307)


@router.get("/api/v1/workspace", response_model=WorkspaceSnapshot)
async def get_workspace_snapshot(
    root: str | None = None,
    signal_id: str | None = None,
    activity_event_kind: NotificationEventKind | None = None,
    activity_status: str | None = None,
    activity_page: int = 1,
    activity_page_size: int = 8,
) -> WorkspaceSnapshot:
    _ensure_dashboard_enabled()
    return _build_workspace_snapshot(
        root=root,
        signal_id=signal_id,
        activity_event_kind=activity_event_kind,
        activity_status=activity_status,
        activity_page=activity_page,
        activity_page_size=activity_page_size,
    )


@router.get("/api/v1/workspace/preferences", response_model=NotificationPreferenceWorkspaceSnapshot)
async def get_workspace_preferences_snapshot(
    activity_root_scope: str | None = None,
    activity_event_kind: NotificationEventKind | None = None,
    activity_status: str | None = None,
    activity_page: int = 1,
    activity_page_size: int = 12,
) -> NotificationPreferenceWorkspaceSnapshot:
    _ensure_dashboard_enabled()
    return _build_preference_workspace_snapshot(
        activity_root_scope=activity_root_scope,
        activity_event_kind=activity_event_kind,
        activity_status=activity_status,
        activity_page=activity_page,
        activity_page_size=activity_page_size,
    )


@router.post("/api/v1/workspace/preferences", response_model=NotificationPreferenceWorkspaceSnapshot)
async def update_workspace_preferences(payload: NotificationPreferenceUpdate) -> NotificationPreferenceWorkspaceSnapshot:
    _ensure_dashboard_enabled()
    container = get_app_container()
    container.preference_service.update_preferences(payload)
    return _build_preference_workspace_snapshot()


@router.post("/api/v1/workspace/delivery/send-now", response_model=TelegramNotificationSendResult)
async def send_workspace_delivery_now(payload: TelegramNotificationSendRequest) -> TelegramNotificationSendResult:
    _ensure_dashboard_enabled()
    return get_app_container().telegram_notification_service.send(payload)


@router.post("/api/v1/workspace/delivery/skip-next", response_model=NotificationPreferenceWorkspaceSnapshot)
async def skip_next_workspace_delivery(payload: NotificationDeliverySkipRequest) -> NotificationPreferenceWorkspaceSnapshot:
    _ensure_dashboard_enabled()
    container = get_app_container()
    container.preference_service.mark_skip_next_event(payload.event_kind)
    return _build_preference_workspace_snapshot()


@router.post("/api/v1/workspace/delivery/undo-skip", response_model=NotificationPreferenceWorkspaceSnapshot)
async def undo_skip_workspace_delivery(payload: NotificationDeliverySkipRequest) -> NotificationPreferenceWorkspaceSnapshot:
    _ensure_dashboard_enabled()
    container = get_app_container()
    container.preference_service.clear_skip_next_event(payload.event_kind)
    return _build_preference_workspace_snapshot()


@router.get("/workspace", response_class=HTMLResponse)
async def get_workspace_page(
    root: str | None = None,
    signal_id: str | None = None,
    activity_event_kind: NotificationEventKind | None = None,
    activity_status: str | None = None,
    activity_page: int = 1,
    activity_page_size: int = 8,
) -> HTMLResponse:
    _ensure_dashboard_enabled()
    snapshot = _build_workspace_snapshot(
        root=root,
        signal_id=signal_id,
        activity_event_kind=activity_event_kind,
        activity_status=activity_status,
        activity_page=activity_page,
        activity_page_size=activity_page_size,
    )
    return HTMLResponse(_render_workspace(snapshot))


@router.get("/workspace/preferences", response_class=HTMLResponse)
async def get_workspace_preferences_page(
    activity_root_scope: str | None = None,
    activity_event_kind: NotificationEventKind | None = None,
    activity_status: str | None = None,
    activity_page: int = 1,
    activity_page_size: int = 12,
) -> HTMLResponse:
    _ensure_dashboard_enabled()
    snapshot = _build_preference_workspace_snapshot(
        activity_root_scope=activity_root_scope,
        activity_event_kind=activity_event_kind,
        activity_status=activity_status,
        activity_page=activity_page,
        activity_page_size=activity_page_size,
    )
    return HTMLResponse(_render_workspace_preferences(snapshot))


@router.get("/api/v1/workspace/delivery-history", response_model=DeliveryHistoryWorkspaceSnapshot)
async def get_workspace_delivery_history_snapshot(
    root: str | None = None,
    activity_root_scope: str | None = None,
    activity_event_kind: NotificationEventKind | None = None,
    activity_status: str | None = None,
    activity_page: int = 1,
    activity_page_size: int = 24,
) -> DeliveryHistoryWorkspaceSnapshot:
    _ensure_dashboard_enabled()
    return _build_delivery_history_snapshot(
        selected_root=root,
        activity_root_scope=activity_root_scope,
        activity_event_kind=activity_event_kind,
        activity_status=activity_status,
        activity_page=activity_page,
        activity_page_size=activity_page_size,
    )


@router.get("/workspace/delivery-history", response_class=HTMLResponse)
async def get_workspace_delivery_history_page(
    root: str | None = None,
    activity_root_scope: str | None = None,
    activity_event_kind: NotificationEventKind | None = None,
    activity_status: str | None = None,
    activity_page: int = 1,
    activity_page_size: int = 24,
) -> HTMLResponse:
    _ensure_dashboard_enabled()
    snapshot = _build_delivery_history_snapshot(
        selected_root=root,
        activity_root_scope=activity_root_scope,
        activity_event_kind=activity_event_kind,
        activity_status=activity_status,
        activity_page=activity_page,
        activity_page_size=activity_page_size,
    )
    return HTMLResponse(_render_delivery_history_workspace(snapshot))


@router.get("/api/v1/workspace/delivery/activity/export")
async def export_workspace_delivery_activity(
    root: str | None = None,
    signal_id: str | None = None,
    activity_root_scope: str | None = None,
    activity_event_kind: NotificationEventKind | None = None,
    activity_status: str | None = None,
    export_format: NotificationDeliveryActivityExportFormat = NotificationDeliveryActivityExportFormat.CSV,
) -> PlainTextResponse:
    _ensure_dashboard_enabled()
    snapshot = _build_delivery_activity_snapshot(
        selected_root=root,
        root_scope=activity_root_scope,
        event_kind=activity_event_kind,
        status=activity_status,
        page=1,
        page_size=500,
        limit=500,
        source_limit=500,
    )
    items = snapshot[0]
    if export_format == NotificationDeliveryActivityExportFormat.JSONL:
        body = "\n".join(json.dumps(item.model_dump(mode="json"), ensure_ascii=False) for item in items)
        return PlainTextResponse(body, media_type="application/x-ndjson")
    lines = [
        "activity_id,action,event_kind,delivery_source,root_scope,status,detail,signal_count,provider_message_id,created_at"
    ]
    for item in items:
        cells = [
            item.activity_id,
            item.action.value,
            item.event_kind.value,
            item.delivery_source or "",
            item.root_scope or "",
            item.status,
            item.detail.replace('"', "'"),
            str(len(item.signal_ids)),
            item.provider_message_id or "",
            item.created_at.isoformat(),
        ]
        lines.append(",".join(f'"{cell}"' for cell in cells))
    return PlainTextResponse("\n".join(lines), media_type="text/csv")


@router.get("/api/v1/workspace/journal", response_model=JournalWorkspaceSnapshot)
async def get_workspace_journal_snapshot(
    root: str | None = None,
    status: SignalStatus | None = None,
    kind: JournalEntryKind | None = None,
    signal_id: str | None = None,
) -> JournalWorkspaceSnapshot:
    _ensure_dashboard_enabled()
    return get_app_container().dashboard_service.build_journal_snapshot(
        root=root,
        status=status,
        kind=kind,
        signal_id=signal_id,
    )


@router.get("/workspace/journal", response_class=HTMLResponse)
async def get_workspace_journal_page(
    root: str | None = None,
    status: SignalStatus | None = None,
    kind: JournalEntryKind | None = None,
    signal_id: str | None = None,
) -> HTMLResponse:
    _ensure_dashboard_enabled()
    snapshot = get_app_container().dashboard_service.build_journal_snapshot(
        root=root,
        status=status,
        kind=kind,
        signal_id=signal_id,
    )
    return HTMLResponse(_render_journal_workspace(snapshot))


@router.get("/api/v1/workspace/signals/{signal_id}", response_model=WorkspaceSignalSnapshot)
async def get_workspace_signal_snapshot(signal_id: str) -> WorkspaceSignalSnapshot:
    _ensure_dashboard_enabled()
    return _build_signal_workspace_snapshot(signal_id)


@router.get("/workspace/signals/{signal_id}", response_class=HTMLResponse)
async def get_workspace_signal_page(signal_id: str) -> HTMLResponse:
    _ensure_dashboard_enabled()
    snapshot = _build_signal_workspace_snapshot(signal_id)
    return HTMLResponse(_render_signal_workspace(snapshot))


@router.get("/api/v1/dashboard", response_model=DashboardSnapshot)
async def get_dashboard_snapshot(root: str | None = None) -> DashboardSnapshot:
    _ensure_dashboard_enabled()
    return get_app_container().dashboard_service.build_snapshot(root=root)


@router.get("/dashboard", response_class=HTMLResponse)
async def get_dashboard_page(root: str | None = None) -> HTMLResponse:
    _ensure_dashboard_enabled()
    snapshot = get_app_container().dashboard_service.build_snapshot(root=root)
    return HTMLResponse(_render_dashboard(snapshot))


def _render_dashboard(snapshot: DashboardSnapshot) -> str:
    root_links = "".join(
        (
            f'<a class="root-pill{" is-active" if item.root_code == snapshot.selected_root else ""}" '
            f'href="/dashboard?root={escape(item.root_code)}">'
            f'<span>{escape(item.root_code)}</span>'
            f'<small>{escape(item.base_asset)}</small>'
            "</a>"
        )
        for item in snapshot.roots
    )
    kpis = "".join(
        (
            f'<article class="kpi-card tone-{escape(item.tone)}">'
            f"<span>{escape(item.label)}</span>"
            f"<strong>{escape(item.value)}</strong>"
            f"<p>{escape(item.detail or '')}</p>"
            "</article>"
        )
        for item in snapshot.kpis
    )
    spotlight = "".join(_render_signal_card(item) for item in snapshot.spotlight_signals) or '<p class="empty">No active signals yet.</p>'
    recent = "".join(_render_signal_row(item) for item in snapshot.recent_signals) or '<p class="empty">No recent signals yet.</p>'
    quality = "".join(_render_quality_pair(item) for item in snapshot.quality_pairs)

    session_block = ""
    if snapshot.root_details is not None:
        root = snapshot.root_details.root
        session = snapshot.root_details.session
        continuous = snapshot.root_details.continuous_series
        session_block = (
            '<section class="panel spotlight">'
            '<div class="panel-head"><h2>Root Control Room</h2>'
            f'<a class="ghost-link" href="/api/v1/roots/{escape(root.root_code)}/deep-dive">Open deep-dive JSON</a>'
            "</div>"
            '<div class="spotlight-grid">'
            f'<div><label>Universe</label><strong>{escape(root.universe_status.value)}</strong></div>'
            f'<div><label>Session</label><strong>{escape(session.session_type.value)}</strong></div>'
            f'<div><label>Trading Day</label><strong>{escape(session.trading_day.isoformat())}</strong></div>'
            f'<div><label>Rule Set</label><strong>{escape(session.effective_rule_set)}</strong></div>'
            f'<div><label>Active Contract</label><strong>{escape(continuous.active_contract)}</strong></div>'
            f'<div><label>Next Contract</label><strong>{escape(continuous.next_contract)}</strong></div>'
            f'<div><label>Days To Last Trade</label><strong>{continuous.days_to_last_trade}</strong></div>'
            f'<div><label>Next Share</label><strong>{continuous.next_contract_share:.0%}</strong></div>'
            "</div>"
            "</section>"
        )

    payload = escape(json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False))
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>IMOEX Signal Dashboard</title>
  <style>
    :root {{
      --bg-1: #f4efe6;
      --bg-2: #dceae4;
      --ink: #16222b;
      --muted: #5f6d73;
      --panel: rgba(255, 251, 245, 0.82);
      --line: rgba(22, 34, 43, 0.08);
      --teal: #116b6a;
      --orange: #c46b1d;
      --red: #b8483b;
      --green: #2f7f54;
      --shadow: 0 20px 50px rgba(17, 34, 43, 0.12);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      font-family: "Trebuchet MS", "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(196, 107, 29, 0.18), transparent 30%),
        radial-gradient(circle at right, rgba(17, 107, 106, 0.18), transparent 25%),
        linear-gradient(160deg, var(--bg-1), var(--bg-2));
      min-height: 100vh;
    }}
    a {{ color: inherit; text-decoration: none; }}
    .shell {{
      width: min(1240px, calc(100% - 32px));
      margin: 24px auto 40px;
    }}
    .hero, .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      box-shadow: var(--shadow);
      backdrop-filter: blur(16px);
      border-radius: 28px;
    }}
    .hero {{
      padding: 28px;
      position: relative;
      overflow: hidden;
    }}
    .hero::after {{
      content: "";
      position: absolute;
      inset: auto -40px -50px auto;
      width: 220px;
      height: 220px;
      background: linear-gradient(135deg, rgba(17, 107, 106, 0.2), rgba(196, 107, 29, 0.08));
      border-radius: 44px;
      transform: rotate(18deg);
    }}
    .eyebrow {{
      display: inline-flex;
      gap: 10px;
      align-items: center;
      padding: 8px 14px;
      border-radius: 999px;
      background: rgba(17, 107, 106, 0.08);
      color: var(--teal);
      font-size: 12px;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    h1 {{
      margin: 14px 0 10px;
      font-family: Georgia, "Palatino Linotype", serif;
      font-size: clamp(34px, 6vw, 58px);
      line-height: 0.95;
      max-width: 8ch;
    }}
    .hero p {{
      max-width: 700px;
      color: var(--muted);
      font-size: 16px;
      line-height: 1.55;
    }}
    .hero-actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-top: 18px;
    }}
    .hero-actions a {{
      padding: 12px 16px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.6);
    }}
    .hero-actions a.primary {{
      background: var(--ink);
      color: #fff8f0;
    }}
    .root-strip {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
      gap: 12px;
      margin: 20px 0 22px;
    }}
    .root-pill {{
      padding: 14px 16px;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.62);
      display: flex;
      flex-direction: column;
      gap: 4px;
      transition: transform 120ms ease, border-color 120ms ease;
    }}
    .root-pill:hover {{ transform: translateY(-1px); }}
    .root-pill span {{ font-size: 20px; font-weight: 700; }}
    .root-pill small {{ color: var(--muted); }}
    .root-pill.is-active {{
      border-color: rgba(17, 107, 106, 0.35);
      background: linear-gradient(135deg, rgba(17, 107, 106, 0.12), rgba(255, 255, 255, 0.78));
    }}
    .kpi-grid, .content-grid {{
      display: grid;
      gap: 16px;
    }}
    .kpi-grid {{
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      margin-bottom: 16px;
    }}
    .kpi-card {{
      padding: 16px 18px;
      border-radius: 20px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.62);
    }}
    .kpi-card span {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 12px;
    }}
    .kpi-card strong {{
      font-size: 28px;
      line-height: 1;
      display: block;
      margin-bottom: 8px;
    }}
    .kpi-card p {{ margin: 0; color: var(--muted); font-size: 13px; line-height: 1.4; }}
    .tone-positive strong {{ color: var(--green); }}
    .tone-warning strong {{ color: var(--orange); }}
    .tone-negative strong {{ color: var(--red); }}
    .content-grid {{
      grid-template-columns: minmax(0, 1.35fr) minmax(0, 1fr);
      align-items: start;
    }}
    .stack {{ display: grid; gap: 16px; }}
    .panel {{ padding: 22px; }}
    .panel-head {{
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 12px;
      margin-bottom: 18px;
    }}
    .panel h2 {{
      margin: 0;
      font-size: 22px;
      font-family: Georgia, "Palatino Linotype", serif;
    }}
    .ghost-link {{ color: var(--teal); font-size: 14px; }}
    .signal-card {{
      padding: 16px;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.7);
      display: grid;
      gap: 10px;
      margin-bottom: 12px;
    }}
    .signal-card:last-child {{ margin-bottom: 0; }}
    .signal-top, .signal-meta, .signal-row {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      gap: 10px;
      align-items: center;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 7px 10px;
      border-radius: 999px;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      background: rgba(17, 107, 106, 0.09);
      color: var(--teal);
    }}
    .signal-summary, .metric-list p, .signal-row small, .empty {{
      color: var(--muted);
      line-height: 1.45;
    }}
    .signal-table {{
      display: grid;
      gap: 10px;
    }}
    .signal-row {{
      padding: 14px 0;
      border-top: 1px solid var(--line);
    }}
    .signal-row:first-child {{ border-top: 0; padding-top: 0; }}
    .signal-row:last-child {{ padding-bottom: 0; }}
    .metric-list {{
      display: grid;
      gap: 12px;
    }}
    .metric-list article {{
      padding: 14px 16px;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.62);
    }}
    .metric-list strong {{ display: block; margin-bottom: 4px; }}
    .spotlight-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 14px;
    }}
    .spotlight-grid div {{
      padding: 14px 16px;
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.66);
      border: 1px solid var(--line);
    }}
    .spotlight-grid label {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 8px;
    }}
    .spotlight-grid strong {{
      font-size: 18px;
    }}
    pre {{
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-family: Consolas, "Courier New", monospace;
      font-size: 12px;
      color: var(--muted);
    }}
    @media (max-width: 960px) {{
      .content-grid {{ grid-template-columns: 1fr; }}
      .shell {{ width: min(100% - 18px, 1240px); }}
      .hero {{ padding: 22px; }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <span class="eyebrow">IMOEX Signals · Dashboard</span>
      <h1>Signal room for {escape(snapshot.selected_root)}</h1>
      <p>
        Delivery-layer dashboard over the live signal pipeline: roots, current signal inventory,
        evaluation status, source quality and operational health in one place.
      </p>
      <div class="hero-actions">
        <a class="primary" href="/api/v1/dashboard?root={escape(snapshot.selected_root)}">Open JSON snapshot</a>
        <a href="/api/v1/signals?root={escape(snapshot.selected_root)}">Inspect signals API</a>
        <a href="/api/v1/admin/health">Inspect admin health</a>
      </div>
    </section>
    <section class="root-strip">{root_links}</section>
    <section class="kpi-grid">{kpis}</section>
    <section class="content-grid">
      <div class="stack">
        <section class="panel">
          <div class="panel-head">
            <h2>Active Signal Spotlight</h2>
            <a class="ghost-link" href="/api/v1/signals?root={escape(snapshot.selected_root)}&status=active">Open API list</a>
          </div>
          {spotlight}
        </section>
        {session_block}
        <section class="panel">
          <div class="panel-head">
            <h2>Recent Signal Tape</h2>
          </div>
          <div class="signal-table">{recent}</div>
        </section>
      </div>
      <div class="stack">
        <section class="panel">
          <div class="panel-head">
            <h2>Evaluation</h2>
            <a class="ghost-link" href="/api/v1/quality/evaluation-report?root={escape(snapshot.selected_root)}">Open report</a>
          </div>
          <div class="metric-list">
            <article><strong>Resolved signals</strong><p>{snapshot.evaluation.resolved_signals}</p></article>
            <article><strong>Brier score</strong><p>{_format_optional(snapshot.evaluation.brier_score)}</p></article>
            <article><strong>Log loss</strong><p>{_format_optional(snapshot.evaluation.log_loss)}</p></article>
            <article><strong>Top-{snapshot.evaluation.top_k} precision</strong><p>{_format_optional(snapshot.evaluation.top_k_precision)}</p></article>
          </div>
        </section>
        <section class="panel">
          <div class="panel-head">
            <h2>Platform Health</h2>
            <a class="ghost-link" href="/api/v1/admin/health">Open health JSON</a>
          </div>
          <div class="metric-list">
            <article><strong>Status</strong><p>{escape(snapshot.admin_health.status)}</p></article>
            <article><strong>DB status</strong><p>{escape(snapshot.admin_health.database_status)}</p></article>
            <article><strong>Active / resolved</strong><p>{snapshot.admin_health.active_signals} / {snapshot.admin_health.resolved_signals}</p></article>
            <article><strong>Backups</strong><p>{snapshot.admin_health.backup_artifacts}</p></article>
          </div>
        </section>
        <section class="panel">
          <div class="panel-head">
            <h2>Source Quality</h2>
            <a class="ghost-link" href="/api/v1/quality/summary?provider_a=moex&provider_b=finam">Open quality API</a>
          </div>
          <div class="metric-list">{quality}</div>
        </section>
        <section class="panel">
          <div class="panel-head">
            <h2>Snapshot Payload</h2>
          </div>
          <pre id="dashboard-data">{payload}</pre>
        </section>
      </div>
    </section>
  </main>
</body>
</html>"""


def _render_workspace(snapshot: WorkspaceSnapshot) -> str:
    focus = snapshot.focus_signal
    root_details = snapshot.root_details
    focus_visual = snapshot.focus_visual
    root_links = "".join(
        (
            f'<a class="rail-card tone-{escape(item.tone)}{" is-active" if item.root_code == snapshot.selected_root else ""}" '
            f'href="/workspace?root={escape(item.root_code)}">'
            f"<strong>{escape(item.root_code)}</strong>"
            f"<span>{escape(item.base_asset)}</span>"
            f"<small>{escape(item.headline)}</small>"
            f"<em>{item.active_signals} active | roll {item.next_contract_share:.0%}</em>"
            "</a>"
        )
        for item in snapshot.pulses
    )
    signal_lane = "".join(
        _render_workspace_signal_tile(item, snapshot.selected_signal_id) for item in snapshot.signal_lane
    ) or '<p class="empty">No signals available for the selected root yet.</p>'
    actions = "".join(_render_action_item(item) for item in snapshot.action_items)
    visual_bars = _render_metric_bars(focus_visual.metric_bars if focus_visual is not None else [], compact=True)
    visual_timeline = _render_timeline(focus_visual.timeline if focus_visual is not None else [], compact=True)
    drivers = "".join(f"<li>{escape(item)}</li>" for item in (focus.drivers if focus is not None else [])) or "<li>No drivers recorded yet.</li>"
    objections = "".join(f"<li>{escape(item)}</li>" for item in (focus.objections if focus is not None else [])) or "<li>No objections recorded yet.</li>"
    invalidations = "".join(f"<li>{escape(item)}</li>" for item in (focus.invalidation_conditions if focus is not None else [])) or "<li>No invalidation conditions recorded yet.</li>"
    journal_rows = "".join(_render_journal_entry(item) for item in (focus.journal_entries if focus is not None else [])) or '<p class="empty">No journal entries yet. Capture thesis and risk before acting.</p>'

    focus_header = "No focus signal yet"
    focus_summary = "Select a root or wait for the next recalculation cycle."
    focus_badge = "watch mode"
    confidence = "n/a"
    skeptic = "n/a"
    if focus is not None:
        focus_header = f"{focus.root} | {focus.contract} | {focus.horizon.value}"
        focus_summary = focus.summary
        focus_badge = f"{focus.direction_final.value} | {focus.status.value}"
        confidence = f"{focus.confidence_final:.2f}"
        skeptic = f"{focus.skeptic_score:.2f}"

    session_band = ""
    if root_details is not None:
        session_band = (
            '<section class="panel band">'
            "<h2>Context band</h2>"
            '<div class="band-grid">'
            f'<article><span>Session</span><strong>{escape(root_details.session.session_type.value)}</strong><p>Trading day {escape(root_details.session.trading_day.isoformat())}</p></article>'
            f'<article><span>Active contract</span><strong>{escape(root_details.continuous_series.active_contract)}</strong><p>Next {escape(root_details.continuous_series.next_contract)}</p></article>'
            f'<article><span>Roll risk</span><strong>{root_details.continuous_series.next_contract_share:.0%}</strong><p>{escape(root_details.continuous_series.roll_state)}</p></article>'
            f'<article><span>Universe</span><strong>{escape(root_details.root.universe_status.value)}</strong><p>Liquidity rank {root_details.root.liquidity_rank}</p></article>'
            "</div>"
            "</section>"
        )

    telegram_preview = escape(snapshot.telegram_preview_message or "Telegram preview is not available.")
    delivery_windows = _render_delivery_windows(snapshot.delivery_windows)
    delivery_activity = _render_delivery_activity(snapshot.delivery_activity)
    delivery_activity_controls = _render_delivery_activity_controls(
        base_path="/workspace",
        root=snapshot.selected_root,
        signal_id=snapshot.selected_signal_id,
        filters=snapshot.delivery_activity_filters,
        by_event_kind=snapshot.delivery_activity_by_event_kind,
        by_root_scope=snapshot.delivery_activity_by_root_scope,
        by_status=snapshot.delivery_activity_by_status,
    )
    delivery_activity_footer = _render_delivery_activity_footer(
        base_path="/workspace",
        export_path="/api/v1/workspace/delivery/activity/export",
        root=snapshot.selected_root,
        signal_id=snapshot.selected_signal_id,
        filters=snapshot.delivery_activity_filters,
        pagination=snapshot.delivery_activity_pagination,
    )
    quality = "".join(_render_quality_pair(item) for item in snapshot.quality_pairs)
    payload = escape(json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False))
    selected_signal_id = escape(snapshot.selected_signal_id or "")
    form_disabled = "disabled" if focus is None else ""
    primary_label = "This browser workspace"
    if snapshot.telegram_delivery_ready:
        primary_label = "Browser workspace + Telegram brief"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>IMOEX Workspace</title>
  <style>
    :root {{
      --bg: #f6f1e7;
      --paper: rgba(255, 250, 241, 0.88);
      --ink: #17222c;
      --muted: #5e6b73;
      --line: rgba(23, 34, 44, 0.1);
      --navy: #193a52;
      --teal: #0f6c67;
      --amber: #b66d1f;
      --coral: #b64b3d;
      --mint: #2f7d5b;
      --shadow: 0 18px 46px rgba(23, 34, 44, 0.11);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      font-family: "Segoe UI", "Trebuchet MS", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(182, 109, 31, 0.17), transparent 26%),
        radial-gradient(circle at top right, rgba(15, 108, 103, 0.18), transparent 24%),
        linear-gradient(180deg, #fbf7f0, var(--bg));
    }}
    a {{ color: inherit; text-decoration: none; }}
    .shell {{ width: min(1320px, calc(100% - 28px)); margin: 18px auto 36px; }}
    .hero, .panel {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 30px;
      box-shadow: var(--shadow);
      backdrop-filter: blur(14px);
    }}
    .hero {{
      display: grid;
      grid-template-columns: minmax(0, 1.55fr) minmax(300px, 0.9fr);
      gap: 18px;
      padding: 24px;
      overflow: hidden;
    }}
    .hero-copy, .panel {{ animation: rise 320ms ease; }}
    .eyebrow {{
      display: inline-flex;
      gap: 8px;
      align-items: center;
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(25, 58, 82, 0.08);
      color: var(--navy);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 12px;
    }}
    h1 {{
      margin: 14px 0 10px;
      font-family: Georgia, "Palatino Linotype", serif;
      font-size: clamp(34px, 5vw, 58px);
      line-height: 0.96;
      max-width: 10ch;
    }}
    h2 {{
      margin: 0;
      font-family: Georgia, "Palatino Linotype", serif;
      font-size: 22px;
    }}
    h3 {{ margin: 0 0 10px; font-size: 16px; }}
    .hero-copy p, .muted, .empty {{
      color: var(--muted);
      line-height: 1.55;
    }}
    .hero-actions, .top-links {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 18px;
    }}
    .button {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 12px 16px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.62);
      font-weight: 600;
      cursor: pointer;
    }}
    .button.primary {{
      background: var(--navy);
      border-color: transparent;
      color: #fdf8f0;
    }}
    .hero-side {{
      padding: 18px;
      border-radius: 24px;
      background: linear-gradient(160deg, rgba(25, 58, 82, 0.96), rgba(15, 108, 103, 0.88));
      color: #f5efe6;
      display: grid;
      gap: 14px;
      animation: rise 420ms ease;
    }}
    .hero-side p, .hero-side small {{ color: rgba(245, 239, 230, 0.82); line-height: 1.5; }}
    .hero-kpis {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }}
    .hero-kpis article {{
      padding: 12px;
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.1);
    }}
    .hero-kpis span, .focus-grid span, .metric-list span, .band-grid span {{
      display: block;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 8px;
      color: rgba(245, 239, 230, 0.74);
    }}
    .layout {{
      display: grid;
      grid-template-columns: minmax(0, 1.5fr) minmax(320px, 0.92fr);
      gap: 16px;
      margin-top: 16px;
    }}
    .stack {{ display: grid; gap: 16px; }}
    .panel {{ padding: 22px; }}
    .panel-head {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      gap: 12px;
      align-items: baseline;
      margin-bottom: 16px;
    }}
    .rail {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 12px;
    }}
    .rail-card {{
      display: grid;
      gap: 6px;
      padding: 16px;
      border-radius: 22px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.62);
      transition: transform 140ms ease, border-color 140ms ease;
    }}
    .rail-card:hover {{ transform: translateY(-2px); }}
    .rail-card.is-active {{
      border-color: rgba(25, 58, 82, 0.35);
      background: linear-gradient(145deg, rgba(25, 58, 82, 0.12), rgba(255, 255, 255, 0.72));
    }}
    .rail-card strong {{ font-size: 24px; }}
    .rail-card span {{ color: var(--muted); font-size: 14px; }}
    .rail-card small {{ line-height: 1.45; min-height: 44px; }}
    .rail-card em {{ font-style: normal; color: var(--navy); font-size: 12px; text-transform: uppercase; letter-spacing: 0.08em; }}
    .signal-lane, .action-list, .journal-list, .metric-list {{
      display: grid;
      gap: 12px;
    }}
    .visual-grid, .timeline-list {{
      display: grid;
      gap: 12px;
    }}
    .signal-tile, .focus-grid article, .metric-list article, .band-grid article, .action-card, .journal-entry, .delivery-card {{
        padding: 14px 16px;
        border-radius: 18px;
        border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.68);
    }}
    .signal-tile.is-focus {{
      border-color: rgba(15, 108, 103, 0.34);
      box-shadow: inset 0 0 0 1px rgba(15, 108, 103, 0.14);
    }}
    .signal-top, .metric-row {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      gap: 10px;
      align-items: center;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 7px 10px;
      border-radius: 999px;
      background: rgba(15, 108, 103, 0.08);
      color: var(--teal);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 12px;
    }}
    .focus-card {{
      display: grid;
      gap: 16px;
      padding: 20px;
      border-radius: 24px;
      border: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(255, 255, 255, 0.76), rgba(255, 248, 239, 0.92));
    }}
    .focus-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
      gap: 12px;
    }}
    .focus-grid span, .metric-list span, .band-grid span {{
      color: var(--muted);
    }}
    .focus-grid strong, .metric-list strong, .band-grid strong {{
      font-size: 20px;
    }}
    .band-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 12px;
    }}
    .split {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
    }}
    .split article {{
      padding: 14px 16px;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.68);
    }}
    .split ul {{
      margin: 0;
      padding-left: 18px;
      color: var(--muted);
      line-height: 1.55;
    }}
    .journal-entry strong {{ display: block; margin-bottom: 6px; }}
    .journal-entry small {{ color: var(--muted); display: block; margin-bottom: 8px; }}
    form {{ display: grid; gap: 10px; }}
    select, input, textarea {{
      width: 100%;
      padding: 12px 14px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.85);
      color: var(--ink);
      font: inherit;
    }}
    textarea {{ min-height: 120px; resize: vertical; }}
    .status {{ min-height: 20px; color: var(--teal); font-size: 14px; }}
    .filter-stack {{ display: grid; gap: 12px; margin-bottom: 14px; }}
    .filter-row {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }}
    .filter-chip {{
      display: inline-flex;
      padding: 8px 12px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.72);
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }}
    .filter-chip.is-active {{
      background: rgba(17, 104, 102, 0.12);
      color: var(--teal);
      border-color: rgba(17, 104, 102, 0.28);
    }}
    .summary-card {{
      display: flex;
      flex-direction: column;
      gap: 6px;
      padding: 14px 16px;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.68);
    }}
    .metric-bar {{
      padding: 12px 14px;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.68);
    }}
    .metric-bar-head {{
      display: flex;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 8px;
      font-size: 13px;
    }}
    .metric-bar-track {{
      width: 100%;
      height: 10px;
      border-radius: 999px;
      background: rgba(23, 34, 44, 0.08);
      overflow: hidden;
    }}
    .metric-bar-fill {{
      height: 100%;
      border-radius: 999px;
      background: linear-gradient(90deg, var(--navy), var(--teal));
    }}
    .metric-bar-fill.tone-positive {{ background: linear-gradient(90deg, #2f7d5b, #57a36f); }}
    .metric-bar-fill.tone-warning {{ background: linear-gradient(90deg, #b66d1f, #d7953c); }}
    .metric-bar-fill.tone-negative {{ background: linear-gradient(90deg, #b64b3d, #df6d58); }}
    .timeline-item {{
      position: relative;
      padding: 12px 14px 12px 28px;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.68);
    }}
    .timeline-item::before {{
      content: "";
      position: absolute;
      left: 12px;
      top: 18px;
      width: 8px;
      height: 8px;
      border-radius: 999px;
      background: var(--navy);
    }}
    .timeline-item.tone-positive::before {{ background: #2f7d5b; }}
    .timeline-item.tone-warning::before {{ background: #b66d1f; }}
    .timeline-item.tone-negative::before {{ background: #b64b3d; }}
    pre {{
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-family: Consolas, "Courier New", monospace;
      font-size: 12px;
      color: var(--muted);
    }}
    @keyframes rise {{
      from {{ opacity: 0; transform: translateY(12px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}
    @media (max-width: 980px) {{
      .hero, .layout, .split {{
        grid-template-columns: 1fr;
      }}
      .shell {{ width: min(100% - 16px, 1320px); }}
      .hero {{ padding: 18px; }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <div class="hero-copy">
        <span class="eyebrow">User Workspace | Signals-only</span>
        <h1>What should I do with {escape(snapshot.selected_root)} right now?</h1>
        <p>
          The primary user experience is this browser workspace at <strong>/workspace</strong>.
          Telegram gives the portable brief, and <strong>/dashboard</strong> remains the operations console.
        </p>
        <div class="hero-actions">
          <a class="button primary" href="/api/v1/workspace?root={escape(snapshot.selected_root)}">Open workspace JSON</a>
          <a class="button" href="/workspace/preferences">Preferences</a>
          <a class="button" href="/workspace/delivery-history?root={escape(snapshot.selected_root)}">Delivery history</a>
          <a class="button" href="/dashboard?root={escape(snapshot.selected_root)}">Open ops console</a>
          <a class="button" href="/api/v1/signals?root={escape(snapshot.selected_root)}&status=active">Inspect active signals API</a>
        </div>
      </div>
      <aside class="hero-side">
        <div>
          <h2>Focus signal</h2>
          <p><strong>{escape(focus_header)}</strong></p>
          <small>{escape(focus_summary)}</small>
        </div>
        <div class="hero-kpis">
          <article><span>Primary surface</span><strong>{escape(primary_label)}</strong></article>
          <article><span>Bias</span><strong>{escape(focus_badge)}</strong></article>
          <article><span>Confidence</span><strong>{escape(confidence)}</strong></article>
          <article><span>Skeptic</span><strong>{escape(skeptic)}</strong></article>
        </div>
        <div class="top-links">
          <a class="button" href="/api/v1/notifications/telegram/preview?root={escape(snapshot.selected_root)}">Telegram JSON</a>
          <a class="button" href="/api/v1/admin/health">Admin health</a>
        </div>
      </aside>
    </section>
    <section class="panel">
      <div class="panel-head">
        <h2>Root lane</h2>
        <p>Each card answers whether this root deserves attention now.</p>
      </div>
      <div class="rail">{root_links}</div>
    </section>
    {session_band}
    <section class="layout">
      <div class="stack">
        <section class="panel">
          <div class="panel-head">
            <h2>Signal lane</h2>
            <p>Pick the signal you want to review in detail.</p>
          </div>
          <div class="signal-lane">{signal_lane}</div>
        </section>
        <section class="panel">
          <div class="panel-head">
            <h2>Decision pack</h2>
            <p>The minimum context a human needs before acting.</p>
          </div>
          <article class="focus-card">
            <div class="signal-top">
              <div>
                <strong>{escape(focus_header)}</strong>
                <p class="muted">{escape(focus_summary)}</p>
              </div>
              <span class="badge">{escape(focus_badge)}</span>
            </div>
            <div class="focus-grid">
              <article><span>Priority</span><strong>{focus.priority_score if focus is not None else "n/a"}</strong></article>
              <article><span>Freshness</span><strong>{f"{focus.freshness_score:.2f}" if focus is not None else "n/a"}</strong></article>
              <article><span>Roll risk</span><strong>{f"{focus.roll_risk:.2f}" if focus is not None else "n/a"}</strong></article>
              <article><span>Expiry risk</span><strong>{f"{focus.expiry_risk:.2f}" if focus is not None else "n/a"}</strong></article>
            </div>
            <div class="split">
              <article>
                <h3>Why now</h3>
                <ul>{drivers}</ul>
              </article>
              <article>
                <h3>Pushback</h3>
                <ul>{objections}</ul>
              </article>
              <article>
                <h3>Invalidation</h3>
                <ul>{invalidations}</ul>
              </article>
            </div>
            <div class="hero-actions" style="margin-top:0;">
              <a class="button primary" href="{f'/workspace/signals/{escape(focus.signal_id)}' if focus is not None else '#'}">Open full signal page</a>
              <a class="button" href="{f'/api/v1/signals/{escape(focus.signal_id)}' if focus is not None else '#'}">Open signal JSON</a>
            </div>
          </article>
        </section>
        <section class="panel">
          <div class="panel-head">
            <h2>Visual pulse</h2>
            <p>Compact chart of confidence, risk and recent lifecycle events.</p>
          </div>
          <div class="visual-grid">{visual_bars}</div>
          <div class="timeline-list" style="margin-top:16px;">{visual_timeline}</div>
        </section>
        <section class="panel">
          <div class="panel-head">
            <h2>Journal</h2>
            <p>Capture thesis, risk, execution notes and post-mortems without leaving the page.</p>
          </div>
          <div class="journal-list">{journal_rows}</div>
          <div class="panel-head" style="margin-top:18px;">
            <h2>Quick capture</h2>
            <p>{'Writes straight into the signal journal.' if focus is not None else 'Pick a signal first to enable quick capture.'}</p>
          </div>
          <form id="workspace-journal-form" data-signal-id="{selected_signal_id}">
            <select name="kind" {form_disabled}>
              <option value="thesis">Thesis</option>
              <option value="risk_note">Risk note</option>
              <option value="execution_note">Execution note</option>
              <option value="post_mortem">Post-mortem</option>
            </select>
            <input type="text" name="title" placeholder="Short title" {form_disabled}>
            <textarea name="note" placeholder="Write what changed, why it matters, and what you will watch next." {form_disabled}></textarea>
            <button class="button primary" type="submit" {form_disabled}>Save journal note</button>
            <div class="status" id="journal-status"></div>
          </form>
        </section>
      </div>
      <div class="stack">
        <section class="panel">
          <div class="panel-head">
            <h2>Action plan</h2>
            <p>What the product thinks the user should do next.</p>
          </div>
          <div class="action-list">{actions}</div>
        </section>
        <section class="panel">
          <div class="panel-head">
            <h2>Telegram brief</h2>
            <p>{'Ready to send.' if snapshot.telegram_delivery_ready else 'Preview available even if delivery is not configured yet.'}</p>
          </div>
          <pre>{telegram_preview}</pre>
        </section>
        <section class="panel">
          <div class="panel-head">
            <h2>Delivery calendar</h2>
            <p>The next scheduled Telegram windows for this workspace.</p>
          </div>
          <div class="list">{delivery_windows}</div>
          <div class="status" id="delivery-action-status"></div>
        </section>
        <section class="panel">
          <div class="panel-head">
            <h2>Delivery activity</h2>
            <p>Recent sends, suppressions and one-shot calendar actions for this root.</p>
          </div>
          {delivery_activity_controls}
          <div class="list">{delivery_activity}</div>
          {delivery_activity_footer}
        </section>
        <section class="panel">
          <div class="panel-head">
            <h2>Evaluation and health</h2>
            <p>Quality and operational context next to the trading idea.</p>
          </div>
          <div class="metric-list">
            <article><span>Resolved signals</span><strong>{snapshot.evaluation.resolved_signals}</strong><p class="muted">Brier {_format_optional(snapshot.evaluation.brier_score)} | log loss {_format_optional(snapshot.evaluation.log_loss)}</p></article>
            <article><span>Platform</span><strong>{escape(snapshot.admin_health.status)}</strong><p class="muted">DB {escape(snapshot.admin_health.database_status)} | active {snapshot.admin_health.active_signals}</p></article>
          </div>
        </section>
        <section class="panel">
          <div class="panel-head">
            <h2>Source quality</h2>
            <p>Provider comparison stays visible to the user, not only to ops.</p>
          </div>
          <div class="metric-list">{quality}</div>
        </section>
        <section class="panel">
          <div class="panel-head">
            <h2>Raw snapshot</h2>
            <p>Useful when you need to inspect the exact payload behind the page.</p>
          </div>
          <pre id="workspace-data">{payload}</pre>
        </section>
      </div>
    </section>
  </main>
  <script>
    const journalForm = document.getElementById("workspace-journal-form");
    const journalStatus = document.getElementById("journal-status");
    const deliveryStatus = document.getElementById("delivery-action-status");
    if (journalForm) {{
      journalForm.addEventListener("submit", async (event) => {{
        event.preventDefault();
        const signalId = journalForm.dataset.signalId;
        if (!signalId) {{
          if (journalStatus) {{
            journalStatus.textContent = "Select a signal first.";
          }}
          return;
        }}
        const formData = new FormData(journalForm);
        const payload = {{
          kind: formData.get("kind"),
          title: formData.get("title"),
          note: formData.get("note"),
          author: "workspace",
        }};
        if (!payload.title || !payload.note) {{
          if (journalStatus) {{
            journalStatus.textContent = "Title and note are required.";
          }}
          return;
        }}
        if (journalStatus) {{
          journalStatus.textContent = "Saving...";
        }}
        const response = await fetch(`/api/v1/journal/${{signalId}}`, {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify(payload),
        }});
        if (!response.ok) {{
          if (journalStatus) {{
            journalStatus.textContent = "Journal save failed.";
          }}
          return;
        }}
        if (journalStatus) {{
          journalStatus.textContent = "Saved. Reloading...";
        }}
        const url = new URL(window.location.href);
        url.searchParams.set("signal_id", signalId);
        window.location.href = url.toString();
      }});
    }}
    const deliverySendButtons = document.querySelectorAll(".delivery-send-now");
    const deliverySendForceButtons = document.querySelectorAll(".delivery-send-now-force");
    const deliverySkipButtons = document.querySelectorAll(".delivery-skip-next");
    const deliveryUndoButtons = document.querySelectorAll(".delivery-undo-skip");
    const runDeliveryAction = async (eventKind, ignoreQuietHours) => {{
      if (deliveryStatus) {{
        deliveryStatus.textContent = ignoreQuietHours ? "Sending with quiet-hours override..." : "Sending...";
      }}
      const response = await fetch("/api/v1/workspace/delivery/send-now", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{
          root: "{escape(snapshot.selected_root)}",
          event_kind: eventKind,
          limit: 3,
          ignore_quiet_hours: ignoreQuietHours,
        }}),
      }});
      const payload = await response.json();
      if (!response.ok) {{
        if (deliveryStatus) {{
          deliveryStatus.textContent = "Delivery action failed.";
        }}
        return;
      }}
      if (deliveryStatus) {{
        deliveryStatus.textContent = payload.detail || payload.delivery_status || "Delivery action completed.";
      }}
      window.setTimeout(() => window.location.reload(), 800);
    }};
    for (const button of deliverySendButtons) {{
      button.addEventListener("click", async () => {{
        await runDeliveryAction(button.dataset.eventKind, false);
      }});
    }}
    for (const button of deliverySendForceButtons) {{
      button.addEventListener("click", async () => {{
        await runDeliveryAction(button.dataset.eventKind, true);
      }});
    }}
    for (const button of deliverySkipButtons) {{
      button.addEventListener("click", async () => {{
        const eventKind = button.dataset.eventKind;
        if (deliveryStatus) {{
          deliveryStatus.textContent = "Updating next run...";
        }}
        const response = await fetch("/api/v1/workspace/delivery/skip-next", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ event_kind: eventKind }}),
        }});
        if (!response.ok) {{
          if (deliveryStatus) {{
            deliveryStatus.textContent = "Skip-next action failed.";
          }}
          return;
        }}
        if (deliveryStatus) {{
          deliveryStatus.textContent = "Next run updated. Reloading...";
        }}
        window.setTimeout(() => window.location.reload(), 600);
      }});
    }}
    for (const button of deliveryUndoButtons) {{
      button.addEventListener("click", async () => {{
        const eventKind = button.dataset.eventKind;
        if (deliveryStatus) {{
          deliveryStatus.textContent = "Undoing skip...";
        }}
        const response = await fetch("/api/v1/workspace/delivery/undo-skip", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ event_kind: eventKind }}),
        }});
        if (!response.ok) {{
          if (deliveryStatus) {{
            deliveryStatus.textContent = "Undo-skip action failed.";
          }}
          return;
        }}
        if (deliveryStatus) {{
          deliveryStatus.textContent = "Skip removed. Reloading...";
        }}
        window.setTimeout(() => window.location.reload(), 600);
      }});
    }}
  </script>
</body>
</html>"""


def _render_journal_workspace(snapshot: JournalWorkspaceSnapshot) -> str:
    root_filters = ['<a class="chip{}" href="/workspace/journal">All roots</a>'.format(" is-active" if snapshot.selected_root is None else "")]
    for root in snapshot.roots:
        query = urlencode({"root": root.root_code, **({"status": snapshot.selected_status.value} if snapshot.selected_status is not None else {}), **({"kind": snapshot.selected_kind.value} if snapshot.selected_kind is not None else {})})
        root_filters.append(
            f'<a class="chip{" is-active" if snapshot.selected_root == root.root_code else ""}" href="/workspace/journal?{escape(query)}">{escape(root.root_code)}</a>'
        )

    status_filters = ['<a class="chip{}" href="{}">All statuses</a>'.format(" is-active" if snapshot.selected_status is None else "", escape(_journal_filter_href(root=snapshot.selected_root, kind=snapshot.selected_kind)))]
    for status in SignalStatus:
        status_filters.append(
            f'<a class="chip{" is-active" if snapshot.selected_status == status else ""}" href="{escape(_journal_filter_href(root=snapshot.selected_root, status=status, kind=snapshot.selected_kind))}">{escape(status.value)}</a>'
        )

    kind_filters = ['<a class="chip{}" href="{}">All kinds</a>'.format(" is-active" if snapshot.selected_kind is None else "", escape(_journal_filter_href(root=snapshot.selected_root, status=snapshot.selected_status)))]
    for kind in JournalEntryKind:
        kind_filters.append(
            f'<a class="chip{" is-active" if snapshot.selected_kind == kind else ""}" href="{escape(_journal_filter_href(root=snapshot.selected_root, status=snapshot.selected_status, kind=kind))}">{escape(kind.value)}</a>'
        )

    entry_cards = "".join(_render_journal_workspace_entry(item) for item in snapshot.entries) or '<p class="empty">No journal entries match the current filters yet.</p>'
    related = "".join(_render_related_signal(item) for item in snapshot.related_signals) or '<p class="empty">No related signals in the current filter window.</p>'
    payload = escape(json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Journal Workspace</title>
  <style>
    :root {{
      --bg: #f6f0e7;
      --paper: rgba(255, 250, 241, 0.9);
      --ink: #18222b;
      --muted: #5d6b72;
      --line: rgba(24, 34, 43, 0.1);
      --navy: #17384f;
      --teal: #116866;
      --amber: #ba7021;
      --shadow: 0 18px 46px rgba(24, 34, 43, 0.11);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      font-family: "Segoe UI", "Trebuchet MS", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(186, 112, 33, 0.16), transparent 24%),
        radial-gradient(circle at right, rgba(17, 104, 102, 0.18), transparent 22%),
        linear-gradient(180deg, #fbf7f0, var(--bg));
    }}
    a {{ color: inherit; text-decoration: none; }}
    .shell {{ width: min(1280px, calc(100% - 28px)); margin: 20px auto 36px; display: grid; gap: 16px; }}
    .hero, .panel {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 30px;
      box-shadow: var(--shadow);
      padding: 24px;
    }}
    .hero {{
      display: grid;
      grid-template-columns: minmax(0, 1.5fr) minmax(260px, 0.9fr);
      gap: 18px;
    }}
    .eyebrow {{
      display: inline-flex;
      gap: 8px;
      align-items: center;
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(23, 56, 79, 0.08);
      color: var(--navy);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 12px;
    }}
    h1 {{
      margin: 14px 0 10px;
      font-family: Georgia, "Palatino Linotype", serif;
      font-size: clamp(34px, 5vw, 56px);
      line-height: 0.98;
      max-width: 11ch;
    }}
    h2 {{
      margin: 0;
      font-family: Georgia, "Palatino Linotype", serif;
      font-size: 22px;
    }}
    .muted, .empty {{ color: var(--muted); line-height: 1.55; }}
    .actions, .chips {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 14px;
    }}
    .button, .chip {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 11px 14px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.64);
      font-weight: 600;
    }}
    .button.primary, .chip.is-active {{
      background: var(--navy);
      color: #fff8ef;
      border-color: transparent;
    }}
    .hero-side {{
      display: grid;
      gap: 10px;
      padding: 18px;
      border-radius: 24px;
      background: linear-gradient(160deg, rgba(23, 56, 79, 0.96), rgba(17, 104, 102, 0.88));
      color: #f6efe5;
    }}
    .hero-side p {{ color: rgba(246, 239, 229, 0.84); margin: 0; }}
    .hero-side strong {{ font-size: 24px; }}
    .layout {{
      display: grid;
      grid-template-columns: minmax(0, 1.45fr) minmax(300px, 0.95fr);
      gap: 16px;
    }}
    .stack, .entry-list, .related-list, .metric-grid {{ display: grid; gap: 12px; }}
    .metric-grid {{
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    }}
    .metric-grid article, .entry-card, .related-card, .raw-box {{
      padding: 14px 16px;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.68);
    }}
    .metric-grid span {{
      display: block;
      margin-bottom: 8px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 11px;
    }}
    .metric-grid strong {{ font-size: 20px; }}
    .entry-meta {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      gap: 10px;
      margin-bottom: 10px;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 7px 10px;
      border-radius: 999px;
      background: rgba(17, 104, 102, 0.08);
      color: var(--teal);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 12px;
    }}
    pre {{
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-family: Consolas, "Courier New", monospace;
      font-size: 12px;
      color: var(--muted);
    }}
    @media (max-width: 980px) {{
      .hero, .layout {{
        grid-template-columns: 1fr;
      }}
      .shell {{ width: min(100% - 16px, 1280px); }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <div>
        <span class="eyebrow">Journal Workspace | User Workflow</span>
        <h1>Trading memory for the signal system</h1>
        <p class="muted">
          This is the user-facing journal hub: thesis notes, risk notes, execution notes and post-mortems
          across the current signal inventory.
        </p>
        <div class="actions">
          <a class="button primary" href="/api/v1/workspace/journal">Open journal JSON</a>
          <a class="button" href="/workspace">Open workspace</a>
          <a class="button" href="/workspace/preferences">Preferences</a>
        </div>
      </div>
      <aside class="hero-side">
        <p>Total entries</p>
        <strong>{snapshot.total_entries}</strong>
        <p>Thesis {snapshot.thesis_entries} | Risk {snapshot.risk_entries} | Post-mortems {snapshot.post_mortems}</p>
      </aside>
    </section>
    <section class="panel">
      <h2>Filters</h2>
      <div class="chips">{''.join(root_filters)}</div>
      <div class="chips">{''.join(status_filters)}</div>
      <div class="chips">{''.join(kind_filters)}</div>
    </section>
    <section class="layout">
      <div class="stack">
        <section class="panel">
          <h2>Journal tape</h2>
          <div class="metric-grid">
            <article><span>Total</span><strong>{snapshot.total_entries}</strong></article>
            <article><span>Thesis</span><strong>{snapshot.thesis_entries}</strong></article>
            <article><span>Risk</span><strong>{snapshot.risk_entries}</strong></article>
            <article><span>Post-mortems</span><strong>{snapshot.post_mortems}</strong></article>
          </div>
          <div class="entry-list" style="margin-top:16px;">{entry_cards}</div>
        </section>
      </div>
      <div class="stack">
        <section class="panel">
          <h2>Current signal lane</h2>
          <div class="related-list">{related}</div>
        </section>
        <section class="panel">
          <h2>Raw snapshot</h2>
          <div class="raw-box">
            <pre id="journal-workspace-data">{payload}</pre>
          </div>
        </section>
      </div>
    </section>
  </main>
</body>
</html>"""


def _render_delivery_history_workspace(snapshot: DeliveryHistoryWorkspaceSnapshot) -> str:
    selected_root = snapshot.selected_root
    root_links = ['<a class="chip{}" href="/workspace/delivery-history">All roots</a>'.format(" is-active" if selected_root is None and snapshot.delivery_activity_filters.root_scope is None else "")]
    for root in snapshot.roots:
        href = _delivery_activity_filter_href(
            "/workspace/delivery-history",
            root=root.root_code,
            activity_root_scope=root.root_code,
            activity_event_kind=snapshot.delivery_activity_filters.event_kind,
            activity_status=snapshot.delivery_activity_filters.status,
        )
        root_links.append(
            f'<a class="chip{" is-active" if snapshot.delivery_activity_filters.root_scope == root.root_code else ""}" href="{escape(href)}">{escape(root.root_code)}</a>'
        )

    delivery_activity = _render_delivery_activity(snapshot.delivery_activity)
    delivery_activity_controls = _render_delivery_activity_controls(
        base_path="/workspace/delivery-history",
        root=selected_root,
        filters=snapshot.delivery_activity_filters,
        by_event_kind=snapshot.delivery_activity_by_event_kind,
        by_root_scope=snapshot.delivery_activity_by_root_scope,
        by_status=snapshot.delivery_activity_by_status,
    )
    delivery_activity_footer = _render_delivery_activity_footer(
        base_path="/workspace/delivery-history",
        export_path="/api/v1/workspace/delivery/activity/export",
        root=selected_root,
        filters=snapshot.delivery_activity_filters,
        pagination=snapshot.delivery_activity_pagination,
    )
    payload = escape(json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Delivery History</title>
  <style>
    :root {{
      --bg: #f6f0e6;
      --paper: rgba(255, 250, 242, 0.9);
      --ink: #18232c;
      --muted: #5e6b73;
      --line: rgba(24, 35, 44, 0.1);
      --navy: #17384f;
      --teal: #116866;
      --shadow: 0 18px 46px rgba(24, 35, 44, 0.11);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      font-family: "Segoe UI", "Trebuchet MS", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(187, 113, 34, 0.15), transparent 24%),
        radial-gradient(circle at right, rgba(17, 104, 102, 0.16), transparent 22%),
        linear-gradient(180deg, #fbf7f1, var(--bg));
    }}
    a {{ color: inherit; text-decoration: none; }}
    .shell {{ width: min(1320px, calc(100% - 28px)); margin: 20px auto 36px; display: grid; gap: 16px; }}
    .hero, .panel {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 28px;
      box-shadow: var(--shadow);
      padding: 24px;
    }}
    .hero {{
      display: grid;
      grid-template-columns: minmax(0, 1.45fr) minmax(280px, 0.85fr);
      gap: 18px;
    }}
    .eyebrow {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(23, 56, 79, 0.08);
      color: var(--navy);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 12px;
    }}
    h1 {{
      margin: 14px 0 10px;
      font-family: Georgia, "Palatino Linotype", serif;
      font-size: clamp(34px, 5vw, 52px);
      line-height: 0.98;
      max-width: 12ch;
    }}
    h2 {{
      margin: 0;
      font-family: Georgia, "Palatino Linotype", serif;
      font-size: 22px;
    }}
    .muted, .empty {{ color: var(--muted); line-height: 1.55; }}
    .actions, .chip-row, .layout, .stack {{ display: flex; flex-wrap: wrap; gap: 10px; }}
    .layout {{ display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(300px, 0.9fr); gap: 16px; align-items: start; }}
    .stack {{ display: grid; gap: 16px; }}
    .button, .chip, .filter-chip {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 10px 14px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.7);
      font-weight: 600;
    }}
    .button.primary {{ background: var(--navy); color: #fff8ef; border-color: transparent; }}
    .chip, .filter-chip {{
      border-radius: 999px;
      font-size: 12px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.06em;
      padding: 8px 12px;
    }}
    .chip.is-active, .filter-chip.is-active {{
      background: rgba(17, 104, 102, 0.12);
      color: var(--teal);
      border-color: rgba(17, 104, 102, 0.28);
    }}
    .hero-side, .summary-card, .raw-box, .delivery-card {{
      padding: 14px 16px;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.68);
    }}
    .hero-side {{ display: grid; gap: 12px; }}
    .filter-stack {{ display: grid; gap: 12px; margin-bottom: 14px; }}
    .filter-row {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }}
    .summary-card {{ display: flex; flex-direction: column; gap: 6px; }}
    pre {{
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-family: Consolas, "Courier New", monospace;
      font-size: 12px;
      color: var(--muted);
    }}
    @media (max-width: 980px) {{
      .hero, .layout {{ grid-template-columns: 1fr; }}
      .shell {{ width: min(100% - 16px, 1320px); }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <div>
        <span class="eyebrow">Delivery History | User Workflow</span>
        <h1>Audit trail for Telegram delivery</h1>
        <p class="muted">
          This page keeps the full user-facing history of Telegram sends, suppressions, skip controls and scheduled delivery outcomes.
        </p>
        <div class="actions">
          <a class="button primary" href="/api/v1/workspace/delivery-history">Open history JSON</a>
          <a class="button" href="/workspace">Open workspace</a>
          <a class="button" href="/workspace/preferences">Preferences</a>
          <a class="button" href="/workspace/journal">Journal</a>
        </div>
      </div>
      <aside class="hero-side">
        <p>Selected root: <strong>{escape(selected_root or "all")}</strong></p>
        <p>Telegram enabled: <strong>{str(snapshot.telegram_enabled).lower()}</strong></p>
        <p>Telegram configured: <strong>{str(snapshot.telegram_configured).lower()}</strong></p>
        <p>Total events: <strong>{snapshot.delivery_activity_pagination.total_items}</strong></p>
        <p>Current page: <strong>{snapshot.delivery_activity_pagination.page} / {snapshot.delivery_activity_pagination.total_pages}</strong></p>
      </aside>
    </section>
    <section class="panel">
      <h2>Root scope</h2>
      <div class="chip-row">{''.join(root_links)}</div>
    </section>
    <section class="layout">
      <section class="panel">
        <h2>Delivery activity</h2>
        <p class="muted">The same audit trail as the workspace block, but with a longer page size and dedicated navigation.</p>
        {delivery_activity_controls}
        <div class="stack">{delivery_activity}</div>
        {delivery_activity_footer}
      </section>
      <div class="stack">
        <section class="panel">
          <h2>Grouped summary</h2>
          <div class="stack">
            <article class="summary-card"><strong>By event</strong><span>{escape(', '.join(f"{item.label} {item.count}" for item in snapshot.delivery_activity_by_event_kind[:6]) or 'none')}</span></article>
            <article class="summary-card"><strong>By root</strong><span>{escape(', '.join(f"{item.label} {item.count}" for item in snapshot.delivery_activity_by_root_scope[:6]) or 'none')}</span></article>
            <article class="summary-card"><strong>By status</strong><span>{escape(', '.join(f"{item.label} {item.count}" for item in snapshot.delivery_activity_by_status[:6]) or 'none')}</span></article>
          </div>
        </section>
        <section class="panel">
          <h2>Raw snapshot</h2>
          <div class="raw-box">
            <pre id="delivery-history-data">{payload}</pre>
          </div>
        </section>
      </div>
    </section>
  </main>
</body>
</html>"""


def _render_workspace_preferences(snapshot: NotificationPreferenceWorkspaceSnapshot) -> str:
    preferences = snapshot.preferences
    root_options = ['<option value="">Auto root</option>']
    for root in snapshot.roots:
        selected = " selected" if preferences.default_root == root.root_code else ""
        root_options.append(f'<option value="{escape(root.root_code)}"{selected}>{escape(root.root_code)} · {escape(root.base_asset)}</option>')

    root_checks = "".join(
        (
            '<label class="check-card">'
            f'<input type="checkbox" name="subscribed_roots" value="{escape(root.root_code)}"{" checked" if root.root_code in preferences.subscribed_roots else ""}>'
            f'<span><strong>{escape(root.root_code)}</strong><small>{escape(root.base_asset)}</small></span>'
            "</label>"
        )
        for root in snapshot.roots
    )
    horizon_checks = "".join(
        (
            '<label class="check-card">'
            f'<input type="checkbox" name="subscribed_horizons" value="{escape(horizon.value)}"{" checked" if horizon in preferences.subscribed_horizons else ""}>'
            f"<span><strong>{escape(horizon.value)}</strong><small>Signal horizon</small></span>"
            "</label>"
        )
        for horizon in snapshot.available_horizons
    )
    event_checks = "".join(
        (
            '<label class="check-card">'
            f'<input type="checkbox" name="subscribed_event_kinds" value="{escape(event_kind.value)}"{" checked" if event_kind in preferences.subscribed_event_kinds else ""}>'
            f"<span><strong>{escape(event_kind.value)}</strong><small>Telegram event type</small></span>"
            "</label>"
        )
        for event_kind in NotificationEventKind
    )
    delivery_windows = _render_delivery_windows(snapshot.delivery_windows)
    delivery_activity = _render_delivery_activity(snapshot.delivery_activity)
    delivery_activity_controls = _render_delivery_activity_controls(
        base_path="/workspace/preferences",
        filters=snapshot.delivery_activity_filters,
        by_event_kind=snapshot.delivery_activity_by_event_kind,
        by_root_scope=snapshot.delivery_activity_by_root_scope,
        by_status=snapshot.delivery_activity_by_status,
    )
    delivery_activity_footer = _render_delivery_activity_footer(
        base_path="/workspace/preferences",
        export_path="/api/v1/workspace/delivery/activity/export",
        filters=snapshot.delivery_activity_filters,
        pagination=snapshot.delivery_activity_pagination,
    )
    payload = escape(json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False))

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Notification Preferences</title>
  <style>
    :root {{
      --bg: #f6f0e7;
      --paper: rgba(255, 250, 241, 0.9);
      --ink: #18222b;
      --muted: #5d6b72;
      --line: rgba(24, 34, 43, 0.1);
      --navy: #17384f;
      --teal: #116866;
      --shadow: 0 18px 46px rgba(24, 34, 43, 0.11);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      font-family: "Segoe UI", "Trebuchet MS", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(186, 112, 33, 0.16), transparent 24%),
        radial-gradient(circle at right, rgba(17, 104, 102, 0.18), transparent 22%),
        linear-gradient(180deg, #fbf7f0, var(--bg));
    }}
    a {{ color: inherit; text-decoration: none; }}
    .shell {{ width: min(1240px, calc(100% - 28px)); margin: 20px auto 36px; display: grid; gap: 16px; }}
    .hero, .panel {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 30px;
      box-shadow: var(--shadow);
      padding: 24px;
    }}
    .hero {{
      display: grid;
      grid-template-columns: minmax(0, 1.45fr) minmax(260px, 0.95fr);
      gap: 18px;
    }}
    .eyebrow {{
      display: inline-flex;
      gap: 8px;
      align-items: center;
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(23, 56, 79, 0.08);
      color: var(--navy);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 12px;
    }}
    h1 {{
      margin: 14px 0 10px;
      font-family: Georgia, "Palatino Linotype", serif;
      font-size: clamp(34px, 5vw, 56px);
      line-height: 0.98;
      max-width: 11ch;
    }}
    h2 {{
      margin: 0;
      font-family: Georgia, "Palatino Linotype", serif;
      font-size: 22px;
    }}
    .muted {{ color: var(--muted); line-height: 1.55; }}
    .actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 16px;
    }}
    .button {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 12px 16px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.64);
      font-weight: 600;
      cursor: pointer;
    }}
    .button.primary {{
      background: var(--navy);
      border-color: transparent;
      color: #fff8ef;
    }}
    .hero-side {{
      display: grid;
      gap: 12px;
      padding: 18px;
      border-radius: 24px;
      background: linear-gradient(160deg, rgba(23, 56, 79, 0.96), rgba(17, 104, 102, 0.88));
      color: #f6efe5;
    }}
    .hero-side p {{ margin: 0; color: rgba(246, 239, 229, 0.84); }}
    .layout {{
      display: grid;
      grid-template-columns: minmax(0, 1.45fr) minmax(300px, 0.95fr);
      gap: 16px;
    }}
    .stack, form, .checks {{ display: grid; gap: 12px; }}
    label span {{
      display: flex;
      flex-direction: column;
      gap: 2px;
    }}
    select, input {{
      width: 100%;
      padding: 12px 14px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.85);
      color: var(--ink);
      font: inherit;
    }}
    .field {{
      display: grid;
      gap: 8px;
    }}
    .grid2 {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }}
    .check-card, .summary-card, .raw-box, .delivery-card {{
      display: flex;
      gap: 12px;
      align-items: flex-start;
      padding: 14px 16px;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.68);
    }}
    .check-card input {{
      width: auto;
      margin-top: 2px;
    }}
    .status {{
      min-height: 20px;
      color: var(--teal);
      font-size: 14px;
    }}
    .filter-stack {{ display: grid; gap: 12px; margin-bottom: 14px; }}
    .filter-row {{ display: flex; flex-wrap: wrap; gap: 8px; margin-top: 8px; }}
    .filter-chip {{
      display: inline-flex;
      padding: 8px 12px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.72);
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }}
    .filter-chip.is-active {{
      background: rgba(17, 104, 102, 0.12);
      color: var(--teal);
      border-color: rgba(17, 104, 102, 0.28);
    }}
    pre {{
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-family: Consolas, "Courier New", monospace;
      font-size: 12px;
      color: var(--muted);
    }}
    @media (max-width: 960px) {{
      .hero, .layout, .grid2 {{
        grid-template-columns: 1fr;
      }}
      .shell {{ width: min(100% - 16px, 1240px); }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <div>
        <span class="eyebrow">Preferences Center | User Workflow</span>
        <h1>Control what reaches you and when</h1>
        <p class="muted">
          This page controls the single local user profile: default root, subscribed roots and horizons,
          event subscriptions, minimum priority and quiet hours for Telegram delivery.
        </p>
        <div class="actions">
          <a class="button primary" href="/api/v1/workspace/preferences">Open preferences JSON</a>
          <a class="button" href="/workspace">Back to workspace</a>
          <a class="button" href="/workspace/journal">Open journal</a>
          <a class="button" href="/workspace/delivery-history">Delivery history</a>
        </div>
      </div>
      <aside class="hero-side">
        <p>Telegram enabled: <strong>{str(snapshot.telegram_enabled).lower()}</strong></p>
        <p>Telegram configured: <strong>{str(snapshot.telegram_configured).lower()}</strong></p>
        <p>Default root: <strong>{escape(preferences.default_root or "auto")}</strong></p>
        <p>Quiet hours: <strong>{escape(preferences.quiet_hours_start or "--:--")} - {escape(preferences.quiet_hours_end or "--:--")}</strong></p>
        <p>Quiet-hours delivery: <strong>{'suppressed' if preferences.suppress_during_quiet_hours else 'allowed'}</strong></p>
      </aside>
    </section>
    <section class="layout">
      <section class="panel">
        <h2>Subscription settings</h2>
        <form id="preferences-form">
          <div class="field">
            <label for="default_root">Default root</label>
            <select id="default_root" name="default_root">
              {''.join(root_options)}
            </select>
          </div>
          <div class="field">
            <label>Subscribed roots</label>
            <div class="checks">{root_checks}</div>
          </div>
          <div class="field">
            <label>Subscribed horizons</label>
            <div class="checks">{horizon_checks}</div>
          </div>
          <div class="field">
            <label>Telegram events</label>
            <div class="checks">{event_checks}</div>
          </div>
          <div class="grid2">
            <div class="field">
              <label for="min_priority_score">Minimum priority score</label>
              <input id="min_priority_score" name="min_priority_score" type="number" min="0" max="10" value="{preferences.min_priority_score}">
            </div>
            <div class="field">
              <label for="digest_limit">Digest limit</label>
              <input id="digest_limit" name="digest_limit" type="number" min="1" max="10" value="{preferences.digest_limit}">
            </div>
            <div class="field">
              <label for="quiet_hours_start">Quiet hours start</label>
              <input id="quiet_hours_start" name="quiet_hours_start" type="time" value="{escape(preferences.quiet_hours_start or '')}">
            </div>
            <div class="field">
              <label for="quiet_hours_end">Quiet hours end</label>
              <input id="quiet_hours_end" name="quiet_hours_end" type="time" value="{escape(preferences.quiet_hours_end or '')}">
            </div>
          </div>
          <label class="check-card">
            <input type="checkbox" name="suppress_during_quiet_hours" value="true"{" checked" if preferences.suppress_during_quiet_hours else ""}>
            <span><strong>Suppress delivery during quiet hours</strong><small>Preview still works, sends are paused unless overridden.</small></span>
          </label>
          <button class="button primary" type="submit">Save preferences</button>
          <div class="status" id="preferences-status"></div>
        </form>
      </section>
      <section class="panel">
        <h2>Current summary</h2>
        <div class="stack">
          <article class="summary-card"><strong>Subscribed roots</strong><span>{escape(', '.join(preferences.subscribed_roots) or 'none')}</span></article>
          <article class="summary-card"><strong>Subscribed horizons</strong><span>{escape(', '.join(item.value for item in preferences.subscribed_horizons) or 'none')}</span></article>
          <article class="summary-card"><strong>Telegram events</strong><span>{escape(', '.join(item.value for item in preferences.subscribed_event_kinds) or 'none')}</span></article>
          <article class="summary-card"><strong>Min priority</strong><span>{preferences.min_priority_score}</span></article>
          <article class="summary-card"><strong>Digest limit</strong><span>{preferences.digest_limit}</span></article>
          <article class="summary-card"><strong>Quiet-hours policy</strong><span>{'suppress sends' if preferences.suppress_during_quiet_hours else 'allow sends'}</span></article>
        </div>
      </section>
    </section>
    <section class="panel">
      <h2>Delivery calendar</h2>
      <p class="muted">These are the next scheduler-driven Telegram windows using your saved preferences.</p>
      <div class="stack">{delivery_windows}</div>
      <div class="status" id="preferences-delivery-status"></div>
    </section>
    <section class="panel">
      <h2>Delivery activity</h2>
      <p class="muted">Recent sends, quiet-hours suppressions and manual calendar actions.</p>
      {delivery_activity_controls}
      <div class="stack">{delivery_activity}</div>
      {delivery_activity_footer}
    </section>
    <section class="panel">
      <h2>Raw snapshot</h2>
      <div class="raw-box">
        <pre id="preferences-data">{payload}</pre>
      </div>
    </section>
  </main>
  <script>
    const form = document.getElementById("preferences-form");
    const status = document.getElementById("preferences-status");
    const deliveryStatus = document.getElementById("preferences-delivery-status");
    if (form) {{
      form.addEventListener("submit", async (event) => {{
        event.preventDefault();
        const formData = new FormData(form);
        const payload = {{
          default_root: formData.get("default_root") || null,
          subscribed_roots: formData.getAll("subscribed_roots"),
          subscribed_horizons: formData.getAll("subscribed_horizons"),
          subscribed_event_kinds: formData.getAll("subscribed_event_kinds"),
          min_priority_score: Number(formData.get("min_priority_score") || 0),
          quiet_hours_start: formData.get("quiet_hours_start") || null,
          quiet_hours_end: formData.get("quiet_hours_end") || null,
          suppress_during_quiet_hours: formData.get("suppress_during_quiet_hours") === "true",
          digest_limit: Number(formData.get("digest_limit") || 3),
        }};
        if (status) {{
          status.textContent = "Saving...";
        }}
        const response = await fetch("/api/v1/workspace/preferences", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify(payload),
        }});
        if (!response.ok) {{
          if (status) {{
            status.textContent = "Preferences save failed.";
          }}
          return;
        }}
        if (status) {{
          status.textContent = "Saved. Reloading...";
        }}
        window.location.reload();
      }});
    }}
    const deliverySendButtons = document.querySelectorAll(".delivery-send-now");
    const deliverySendForceButtons = document.querySelectorAll(".delivery-send-now-force");
    const deliverySkipButtons = document.querySelectorAll(".delivery-skip-next");
    const deliveryUndoButtons = document.querySelectorAll(".delivery-undo-skip");
    const runDeliveryAction = async (eventKind, ignoreQuietHours) => {{
      if (deliveryStatus) {{
        deliveryStatus.textContent = ignoreQuietHours ? "Sending with quiet-hours override..." : "Sending...";
      }}
      const response = await fetch("/api/v1/workspace/delivery/send-now", {{
        method: "POST",
        headers: {{ "Content-Type": "application/json" }},
        body: JSON.stringify({{
          root: null,
          event_kind: eventKind,
          limit: 3,
          ignore_quiet_hours: ignoreQuietHours,
        }}),
      }});
      const payload = await response.json();
      if (!response.ok) {{
        if (deliveryStatus) {{
          deliveryStatus.textContent = "Delivery action failed.";
        }}
        return;
      }}
      if (deliveryStatus) {{
        deliveryStatus.textContent = payload.detail || payload.delivery_status || "Delivery action completed.";
      }}
      window.setTimeout(() => window.location.reload(), 800);
    }};
    for (const button of deliverySendButtons) {{
      button.addEventListener("click", async () => {{
        await runDeliveryAction(button.dataset.eventKind, false);
      }});
    }}
    for (const button of deliverySendForceButtons) {{
      button.addEventListener("click", async () => {{
        await runDeliveryAction(button.dataset.eventKind, true);
      }});
    }}
    for (const button of deliverySkipButtons) {{
      button.addEventListener("click", async () => {{
        const eventKind = button.dataset.eventKind;
        if (deliveryStatus) {{
          deliveryStatus.textContent = "Updating next run...";
        }}
        const response = await fetch("/api/v1/workspace/delivery/skip-next", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ event_kind: eventKind }}),
        }});
        if (!response.ok) {{
          if (deliveryStatus) {{
            deliveryStatus.textContent = "Skip-next action failed.";
          }}
          return;
        }}
        if (deliveryStatus) {{
          deliveryStatus.textContent = "Next run updated. Reloading...";
        }}
        window.setTimeout(() => window.location.reload(), 600);
      }});
    }}
    for (const button of deliveryUndoButtons) {{
      button.addEventListener("click", async () => {{
        const eventKind = button.dataset.eventKind;
        if (deliveryStatus) {{
          deliveryStatus.textContent = "Undoing skip...";
        }}
        const response = await fetch("/api/v1/workspace/delivery/undo-skip", {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify({{ event_kind: eventKind }}),
        }});
        if (!response.ok) {{
          if (deliveryStatus) {{
            deliveryStatus.textContent = "Undo-skip action failed.";
          }}
          return;
        }}
        if (deliveryStatus) {{
          deliveryStatus.textContent = "Skip removed. Reloading...";
        }}
        window.setTimeout(() => window.location.reload(), 600);
      }});
    }}
  </script>
</body>
</html>"""


def _render_signal_workspace(snapshot: WorkspaceSignalSnapshot) -> str:
    signal = snapshot.signal
    root_details = snapshot.root_details
    visual = snapshot.visual
    journal_rows = "".join(_render_journal_entry(item) for item in signal.journal_entries) or '<p class="empty">No journal entries yet.</p>'
    related = "".join(_render_related_signal(item) for item in snapshot.related_signals) or '<p class="empty">No related signals available right now.</p>'
    metric_bars = _render_metric_bars(visual.metric_bars, compact=False)
    timeline = _render_timeline(visual.timeline, compact=False)
    horizon_pulse = _render_horizon_pulse(visual.horizon_pulse)
    drivers = "".join(f"<li>{escape(item)}</li>" for item in signal.drivers) or "<li>No drivers recorded yet.</li>"
    objections = "".join(f"<li>{escape(item)}</li>" for item in signal.objections) or "<li>No objections recorded yet.</li>"
    invalidations = "".join(f"<li>{escape(item)}</li>" for item in signal.invalidation_conditions) or "<li>No invalidation conditions recorded yet.</li>"
    data_sources = "".join(f"<li>{escape(item)}</li>" for item in signal.data_sources) or "<li>No explicit data sources recorded yet.</li>"
    resolution_block = '<p class="empty">Signal is still active; no resolution record yet.</p>'
    if signal.resolution is not None:
        resolution_block = (
            '<article class="resolution-card">'
            f'<strong>{escape(signal.resolution.outcome.value)} | {escape(signal.resolution.status.value)}</strong>'
            f'<p class="muted">Resolved at {escape(signal.resolution.resolved_at.isoformat())} | return {signal.resolution.realized_return_bps:.1f} bps</p>'
            f'<p class="muted">{escape(signal.resolution.resolution_note)}</p>'
            f'<p class="muted">{escape(signal.resolution.post_mortem_summary)}</p>'
            "</article>"
        )

    context_band = ""
    if root_details is not None:
        context_band = (
            '<section class="band-grid">'
            f'<article><span>Session</span><strong>{escape(root_details.session.session_type.value)}</strong><p class="muted">Trading day {escape(root_details.session.trading_day.isoformat())}</p></article>'
            f'<article><span>Contract state</span><strong>{escape(root_details.continuous_series.active_contract)}</strong><p class="muted">Next {escape(root_details.continuous_series.next_contract)} | roll {root_details.continuous_series.next_contract_share:.0%}</p></article>'
            f'<article><span>Universe</span><strong>{escape(root_details.root.universe_status.value)}</strong><p class="muted">Liquidity rank {root_details.root.liquidity_rank}</p></article>'
            f'<article><span>Evaluation</span><strong>{snapshot.evaluation.resolved_signals}</strong><p class="muted">Resolved signals | Brier {_format_optional(snapshot.evaluation.brier_score)}</p></article>'
            "</section>"
        )

    payload = escape(json.dumps(snapshot.model_dump(mode="json"), ensure_ascii=False))
    telegram_preview = escape(snapshot.telegram_preview_message or "Telegram preview is not available.")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Signal {escape(signal.signal_id)}</title>
  <style>
    :root {{
      --bg: #f5efe6;
      --paper: rgba(255, 250, 242, 0.9);
      --ink: #15202a;
      --muted: #5c6970;
      --line: rgba(21, 32, 42, 0.1);
      --navy: #17364d;
      --teal: #116966;
      --amber: #bb7122;
      --red: #b44a3d;
      --green: #2f7e57;
      --shadow: 0 18px 46px rgba(21, 32, 42, 0.11);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      font-family: "Segoe UI", "Trebuchet MS", sans-serif;
      background:
        radial-gradient(circle at left top, rgba(187, 113, 34, 0.16), transparent 24%),
        radial-gradient(circle at right, rgba(17, 105, 102, 0.18), transparent 22%),
        linear-gradient(180deg, #fbf7f1, var(--bg));
    }}
    a {{ color: inherit; text-decoration: none; }}
    .shell {{ width: min(1280px, calc(100% - 28px)); margin: 20px auto 36px; display: grid; gap: 16px; }}
    .hero, .panel {{
      background: var(--paper);
      border: 1px solid var(--line);
      border-radius: 30px;
      box-shadow: var(--shadow);
      padding: 24px;
    }}
    .hero {{
      display: grid;
      grid-template-columns: minmax(0, 1.45fr) minmax(280px, 0.9fr);
      gap: 18px;
    }}
    .eyebrow {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 999px;
      background: rgba(23, 54, 77, 0.08);
      color: var(--navy);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 12px;
    }}
    h1 {{
      margin: 14px 0 10px;
      font-family: Georgia, "Palatino Linotype", serif;
      font-size: clamp(34px, 5vw, 54px);
      line-height: 0.98;
      max-width: 11ch;
    }}
    h2 {{
      margin: 0;
      font-family: Georgia, "Palatino Linotype", serif;
      font-size: 22px;
    }}
    h3 {{ margin: 0 0 10px; font-size: 16px; }}
    .muted, .empty {{ color: var(--muted); line-height: 1.55; }}
    .hero-actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 18px;
    }}
    .button {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 12px 16px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.64);
      font-weight: 600;
      cursor: pointer;
    }}
    .button.primary {{
      background: var(--navy);
      border-color: transparent;
      color: #fff8ef;
    }}
    .hero-side {{
      display: grid;
      gap: 12px;
      padding: 18px;
      border-radius: 24px;
      background: linear-gradient(160deg, rgba(23, 54, 77, 0.96), rgba(17, 105, 102, 0.88));
      color: #f6efe5;
    }}
    .hero-side p, .hero-side small {{ color: rgba(246, 239, 229, 0.84); line-height: 1.5; }}
    .metric-grid, .band-grid, .split, .layout, .stack, .list, .timeline-list, .visual-grid, .horizon-grid {{
      display: grid;
      gap: 12px;
    }}
    .layout {{
      grid-template-columns: minmax(0, 1.45fr) minmax(320px, 0.95fr);
      gap: 16px;
    }}
    .metric-grid {{
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    }}
    .metric-grid article, .band-grid article, .resolution-card, .journal-entry, .related-card, .telegram-box, .raw-box, .thesis-card {{
      padding: 14px 16px;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.68);
    }}
    .metric-grid span, .band-grid span {{
      display: block;
      margin-bottom: 8px;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 11px;
    }}
    .metric-grid strong, .band-grid strong {{ font-size: 20px; }}
    .band-grid {{
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    }}
    .split {{
      grid-template-columns: repeat(2, minmax(0, 1fr));
    }}
    .thesis-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
    }}
    .thesis-card ul {{
      margin: 0;
      padding-left: 18px;
      color: var(--muted);
      line-height: 1.55;
    }}
    .journal-entry strong, .related-card strong {{ display: block; margin-bottom: 6px; }}
    .journal-entry small {{ color: var(--muted); display: block; margin-bottom: 8px; }}
    form {{ display: grid; gap: 10px; }}
    select, input, textarea {{
      width: 100%;
      padding: 12px 14px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.85);
      color: var(--ink);
      font: inherit;
    }}
    textarea {{ min-height: 120px; resize: vertical; }}
    .status {{ min-height: 20px; color: var(--teal); font-size: 14px; }}
    .metric-bar {{
      padding: 12px 14px;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.68);
    }}
    .metric-bar-head {{
      display: flex;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 8px;
      font-size: 13px;
    }}
    .metric-bar-track {{
      width: 100%;
      height: 10px;
      border-radius: 999px;
      background: rgba(21, 32, 42, 0.08);
      overflow: hidden;
    }}
    .metric-bar-fill {{
      height: 100%;
      border-radius: 999px;
      background: linear-gradient(90deg, var(--navy), var(--teal));
    }}
    .metric-bar-fill.tone-positive {{ background: linear-gradient(90deg, #2f7e57, #59a570); }}
    .metric-bar-fill.tone-warning {{ background: linear-gradient(90deg, #bb7122, #db9a45); }}
    .metric-bar-fill.tone-negative {{ background: linear-gradient(90deg, #b44a3d, #df6f5f); }}
    .timeline-item {{
      position: relative;
      padding: 12px 14px 12px 30px;
      border-radius: 16px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.68);
    }}
    .timeline-item::before {{
      content: "";
      position: absolute;
      left: 13px;
      top: 18px;
      width: 8px;
      height: 8px;
      border-radius: 999px;
      background: var(--navy);
    }}
    .timeline-item.tone-positive::before {{ background: #2f7e57; }}
    .timeline-item.tone-warning::before {{ background: #bb7122; }}
    .timeline-item.tone-negative::before {{ background: #b44a3d; }}
    .horizon-grid {{
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
    }}
    .horizon-card {{
      padding: 14px 16px;
      border-radius: 18px;
      border: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.68);
    }}
    .horizon-card strong {{
      display: block;
      margin-bottom: 6px;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 7px 10px;
      border-radius: 999px;
      background: rgba(17, 105, 102, 0.08);
      color: var(--teal);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      font-size: 12px;
    }}
    pre {{
      margin: 0;
      white-space: pre-wrap;
      word-break: break-word;
      font-family: Consolas, "Courier New", monospace;
      font-size: 12px;
      color: var(--muted);
    }}
    @media (max-width: 1040px) {{
      .hero, .layout, .split, .thesis-grid {{
        grid-template-columns: 1fr;
      }}
      .shell {{ width: min(100% - 16px, 1280px); }}
    }}
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <div>
        <span class="eyebrow">Signal Detail | User Workflow</span>
        <h1>{escape(signal.root)} {escape(signal.contract)}</h1>
        <p class="muted">{escape(signal.summary)}</p>
        <div class="hero-actions">
          <a class="button primary" href="/workspace?root={escape(signal.root)}&signal_id={escape(signal.signal_id)}">Back to workspace</a>
          <a class="button" href="/workspace/preferences">Preferences</a>
          <a class="button" href="/api/v1/workspace/signals/{escape(signal.signal_id)}">Open page JSON</a>
          <a class="button" href="/api/v1/signals/{escape(signal.signal_id)}">Open signal API</a>
          <a class="button" href="/api/v1/roots/{escape(signal.root)}/deep-dive">Open deep-dive</a>
        </div>
      </div>
      <aside class="hero-side">
        <div>
          <h2>{escape(signal.direction_final.value)} | {escape(signal.horizon.value)}</h2>
          <p><strong>{escape(signal.skeptic_verdict.value)}</strong></p>
          <small>Signal id: {escape(signal.signal_id)}</small>
        </div>
        <div class="metric-grid">
          <article><span>Confidence</span><strong>{signal.confidence_final:.2f}</strong></article>
          <article><span>Skeptic</span><strong>{signal.skeptic_score:.2f}</strong></article>
          <article><span>Priority</span><strong>{signal.priority_score}</strong></article>
          <article><span>Status</span><strong>{escape(signal.status.value)}</strong></article>
        </div>
      </aside>
    </section>
    {context_band}
    <section class="layout">
      <div class="stack">
        <section class="panel">
          <h2>Probability map</h2>
          <div class="metric-grid">
            <article><span>Up</span><strong>{signal.probability_up:.2f}</strong></article>
            <article><span>Down</span><strong>{signal.probability_down:.2f}</strong></article>
            <article><span>No edge</span><strong>{signal.probability_no_edge:.2f}</strong></article>
            <article><span>Freshness</span><strong>{signal.freshness_score:.2f}</strong></article>
            <article><span>Roll risk</span><strong>{signal.roll_risk:.2f}</strong></article>
            <article><span>Expiry risk</span><strong>{signal.expiry_risk:.2f}</strong></article>
          </div>
        </section>
        <section class="panel">
          <h2>Signal chart</h2>
          <div class="visual-grid">{metric_bars}</div>
        </section>
        <section class="panel">
          <h2>Horizon pulse</h2>
          <p class="muted">Same root across horizons, using point-in-time features and active signal probabilities.</p>
          <div class="horizon-grid">{horizon_pulse}</div>
        </section>
        <section class="panel">
          <h2>Decision anatomy</h2>
          <div class="thesis-grid">
            <article class="thesis-card">
              <h3>Drivers</h3>
              <ul>{drivers}</ul>
            </article>
            <article class="thesis-card">
              <h3>Objections</h3>
              <ul>{objections}</ul>
            </article>
            <article class="thesis-card">
              <h3>Invalidation</h3>
              <ul>{invalidations}</ul>
            </article>
            <article class="thesis-card">
              <h3>Data sources</h3>
              <ul>{data_sources}</ul>
            </article>
          </div>
        </section>
        <section class="panel">
          <h2>Resolution</h2>
          {resolution_block}
        </section>
        <section class="panel">
          <h2>Lifecycle timeline</h2>
          <div class="timeline-list">{timeline}</div>
        </section>
        <section class="panel">
          <div style="display:flex;justify-content:space-between;gap:12px;align-items:baseline;margin-bottom:16px;">
            <h2>Journal</h2>
            <p class="muted">Capture what changed around this exact signal.</p>
          </div>
          <div class="list">{journal_rows}</div>
          <div style="display:flex;justify-content:space-between;gap:12px;align-items:baseline;margin:18px 0 12px;">
            <h2>Quick capture</h2>
            <p class="muted">Writes directly to the signal journal.</p>
          </div>
          <form id="signal-journal-form" data-signal-id="{escape(signal.signal_id)}">
            <select name="kind">
              <option value="thesis">Thesis</option>
              <option value="risk_note">Risk note</option>
              <option value="execution_note">Execution note</option>
              <option value="post_mortem">Post-mortem</option>
            </select>
            <input type="text" name="title" placeholder="Short title">
            <textarea name="note" placeholder="What changed, what risk you see, and what should be watched next."></textarea>
            <button class="button primary" type="submit">Save journal note</button>
            <div class="status" id="signal-journal-status"></div>
          </form>
        </section>
      </div>
      <div class="stack">
        <section class="panel">
          <h2>Telegram brief</h2>
          <p class="muted">{'Ready to send.' if snapshot.telegram_delivery_ready else 'Preview available even if delivery is not configured yet.'}</p>
          <div class="telegram-box">
            <pre>{telegram_preview}</pre>
          </div>
        </section>
        <section class="panel">
          <h2>Related signals</h2>
          <div class="list">{related}</div>
        </section>
        <section class="panel">
          <h2>Raw snapshot</h2>
          <div class="raw-box">
            <pre id="signal-page-data">{payload}</pre>
          </div>
        </section>
      </div>
    </section>
  </main>
  <script>
    const journalForm = document.getElementById("signal-journal-form");
    const journalStatus = document.getElementById("signal-journal-status");
    if (journalForm) {{
      journalForm.addEventListener("submit", async (event) => {{
        event.preventDefault();
        const signalId = journalForm.dataset.signalId;
        const formData = new FormData(journalForm);
        const payload = {{
          kind: formData.get("kind"),
          title: formData.get("title"),
          note: formData.get("note"),
          author: "signal-page",
        }};
        if (!payload.title || !payload.note) {{
          if (journalStatus) {{
            journalStatus.textContent = "Title and note are required.";
          }}
          return;
        }}
        if (journalStatus) {{
          journalStatus.textContent = "Saving...";
        }}
        const response = await fetch(`/api/v1/journal/${{signalId}}`, {{
          method: "POST",
          headers: {{ "Content-Type": "application/json" }},
          body: JSON.stringify(payload),
        }});
        if (!response.ok) {{
          if (journalStatus) {{
            journalStatus.textContent = "Journal save failed.";
          }}
          return;
        }}
        if (journalStatus) {{
          journalStatus.textContent = "Saved. Reloading...";
        }}
        window.location.reload();
      }});
    }}
  </script>
</body>
</html>"""


def _render_workspace_signal_tile(signal, selected_signal_id: str | None) -> str:
    is_focus = signal.signal_id == selected_signal_id or (selected_signal_id is None and signal.status.value == "active")
    return (
        f'<a class="signal-tile{" is-focus" if is_focus else ""}" href="/workspace?root={escape(signal.root)}&signal_id={escape(signal.signal_id)}">'
        '<div class="signal-top">'
        f'<div><strong>{escape(signal.root)} | {escape(signal.contract)}</strong><p class="muted">{escape(signal.summary)}</p></div>'
        f'<span class="badge">{escape(signal.direction_final.value)} | {escape(signal.horizon.value)}</span>'
        "</div>"
        '<div class="metric-row">'
        f"<small>confidence {signal.confidence_final:.2f}</small>"
        f"<small>skeptic {signal.skeptic_score:.2f}</small>"
        f"<small>priority {signal.priority_score}</small>"
        "</div>"
        "</a>"
    )


def _render_action_item(item: WorkspaceActionItem) -> str:
    return (
        f'<article class="action-card tone-{escape(item.tone)}">'
        f"<strong>{escape(item.title)}</strong>"
        f'<p class="muted">{escape(item.detail)}</p>'
        "</article>"
    )


def _render_journal_entry(entry) -> str:
    return (
        '<article class="journal-entry">'
        f"<strong>{escape(entry.title)}</strong>"
        f"<small>{escape(entry.kind.value)} | {escape(entry.author)} | {escape(entry.created_at.isoformat())}</small>"
        f'<p class="muted">{escape(entry.note)}</p>'
        "</article>"
    )


def _render_related_signal(signal) -> str:
    return (
        f'<a class="related-card" href="/workspace/signals/{escape(signal.signal_id)}">'
        f"<strong>{escape(signal.root)} | {escape(signal.contract)} | {escape(signal.horizon.value)}</strong>"
        f'<p class="muted">{escape(signal.summary)}</p>'
        f'<p class="muted">confidence {signal.confidence_final:.2f} | skeptic {signal.skeptic_score:.2f} | {escape(signal.direction_final.value)}</p>'
        "</a>"
    )


def _render_journal_workspace_entry(item) -> str:
    signal = item.signal
    entry = item.entry
    return (
        '<article class="entry-card">'
        '<div class="entry-meta">'
        f'<div><strong>{escape(entry.title)}</strong><p class="muted">{escape(signal.root)} | {escape(signal.contract)} | {escape(signal.horizon.value)}</p></div>'
        f'<span class="badge">{escape(entry.kind.value)} | {escape(signal.status.value)}</span>'
        "</div>"
        f'<p class="muted">{escape(entry.note)}</p>'
        f'<p class="muted">author {escape(entry.author)} | created {escape(entry.created_at.isoformat())}</p>'
        '<div style="display:flex;flex-wrap:wrap;gap:10px;margin-top:12px;">'
        f'<a class="button" href="/workspace/signals/{escape(signal.signal_id)}">Open signal page</a>'
        f'<a class="button" href="/workspace?root={escape(signal.root)}&signal_id={escape(signal.signal_id)}">Open in workspace</a>'
        "</div>"
        "</article>"
    )


def _render_metric_bars(items, *, compact: bool) -> str:
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


def _render_timeline(items, *, compact: bool) -> str:
    if not items:
        return '<p class="empty">No lifecycle events recorded yet.</p>'
    limit = 4 if compact else len(items)
    rendered = []
    for item in items[-limit:]:
        rendered.append(
            f'<article class="timeline-item tone-{escape(item.tone)}">'
            f"<strong>{escape(item.title)}</strong>"
            f'<p class="muted">{escape(item.at.isoformat())} | {escape(item.kind)}</p>'
            f'<p class="muted">{escape(item.detail)}</p>'
            "</article>"
        )
    return "".join(rendered)


def _render_horizon_pulse(items) -> str:
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


def _render_delivery_windows(items) -> str:
    if not items:
        return '<p class="empty">No delivery windows configured yet.</p>'
    rendered = []
    for item in items:
        next_run = escape(item.next_run_at.isoformat()) if item.next_run_at is not None else "not scheduled"
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


def _render_delivery_activity(items) -> str:
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
        rendered.append(
            f'<article class="delivery-card tone-{"positive" if item.status == "sent" else "warning"}">'
            f"<strong>{escape(title)}</strong>"
            f'<p class="muted">{escape(item.event_kind.value)} | {escape(item.created_at.isoformat())}</p>'
            f'<p class="muted">root {root_scope} | source {source} | status {escape(item.status)}</p>'
            f'<p class="muted">{escape(item.detail)}</p>'
            f'<p class="muted">{escape(signal_info)}'
            f'{" | provider message " + escape(item.provider_message_id) if item.provider_message_id else ""}</p>'
            "</article>"
        )
    return "".join(rendered)


def _delivery_activity_filter_href(
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


def _render_delivery_activity_controls(
    *,
    base_path: str,
    filters: NotificationDeliveryActivityFilters,
    by_event_kind: list[NotificationDeliveryActivityGroup],
    by_root_scope: list[NotificationDeliveryActivityGroup],
    by_status: list[NotificationDeliveryActivityGroup],
    root: str | None = None,
    signal_id: str | None = None,
) -> str:
    clear_href = _delivery_activity_filter_href(base_path, root=root, signal_id=signal_id)
    event_links = [
        (
            '<a class="filter-chip'
            f'{" is-active" if filters.event_kind is None else ""}" '
            f'href="{escape(clear_href)}">All events</a>'
        )
    ]
    for item in by_event_kind:
        href = _delivery_activity_filter_href(
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
            f'href="{escape(_delivery_activity_filter_href(base_path, root=root, signal_id=signal_id, activity_event_kind=filters.event_kind, activity_status=filters.status))}">All roots</a>'
        )
        for item in by_root_scope:
            href = _delivery_activity_filter_href(
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
            f'href="{escape(_delivery_activity_filter_href(base_path, root=root, signal_id=signal_id, activity_root_scope=filters.root_scope, activity_event_kind=filters.event_kind))}">All statuses</a>'
        )
    ]
    for item in by_status:
        href = _delivery_activity_filter_href(
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


def _render_delivery_activity_footer(
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
        prev_href = _delivery_activity_filter_href(
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
        next_href = _delivery_activity_filter_href(
            base_path,
            root=root,
            signal_id=signal_id,
            activity_root_scope=filters.root_scope,
            activity_event_kind=filters.event_kind,
            activity_status=filters.status,
        )
        sep = "&" if "?" in next_href else "?"
        links.append(f'<a class="filter-chip" href="{escape(next_href)}{sep}activity_page={pagination.page + 1}&activity_page_size={pagination.page_size}">Next</a>')
    export_base = _delivery_activity_filter_href(
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


def _journal_filter_href(
    *,
    root: str | None = None,
    status: SignalStatus | None = None,
    kind: JournalEntryKind | None = None,
) -> str:
    params: dict[str, str] = {}
    if root is not None:
        params["root"] = root
    if status is not None:
        params["status"] = status.value
    if kind is not None:
        params["kind"] = kind.value
    if not params:
        return "/workspace/journal"
    return f"/workspace/journal?{urlencode(params)}"


def _render_signal_card(signal) -> str:
    return (
        '<article class="signal-card">'
        '<div class="signal-top">'
        f'<div><strong>{escape(signal.root)} · {escape(signal.contract)}</strong><div class="signal-summary">{escape(signal.summary)}</div></div>'
        f'<span class="badge">{escape(signal.direction_final.value)} · {escape(signal.horizon.value)}</span>'
        "</div>"
        '<div class="signal-meta">'
        f"<small>confidence {signal.confidence_final:.2f}</small>"
        f"<small>skeptic {signal.skeptic_score:.2f}</small>"
        f"<small>priority {signal.priority_score}</small>"
        "</div>"
        "</article>"
    )


def _render_signal_row(signal) -> str:
    return (
        '<article class="signal-row">'
        f"<strong>{escape(signal.root)} · {escape(signal.horizon.value)} · {escape(signal.direction_final.value)}</strong>"
        f"<small>{escape(signal.summary)}</small>"
        "</article>"
    )


def _render_quality_pair(pair: DashboardQualityPair) -> str:
    latest_contract = pair.latest_contract or "n/a"
    mismatch = _format_optional(pair.mismatch_rate_overlap)
    return (
        "<article>"
        f"<strong>{escape(pair.provider_a)} vs {escape(pair.provider_b)}</strong>"
        f"<p>contracts {pair.contracts_count} · latest {escape(latest_contract)} · mismatch {escape(mismatch)}</p>"
        "</article>"
    )


def _format_optional(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.4f}"
