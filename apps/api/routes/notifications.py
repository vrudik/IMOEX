from __future__ import annotations

from fastapi import APIRouter, HTTPException

from libs.bootstrap.container import get_app_container
from libs.notifications.contracts import (
    TelegramDeliveryEventKind,
    TelegramOpsAlertPreview,
    TelegramOpsAlertSendRequest,
    TelegramOpsAlertSendResult,
    TelegramNotificationPreview,
    TelegramNotificationSendRequest,
    TelegramNotificationSendResult,
)
from libs.runtime.feature_flags import is_feature_enabled

router = APIRouter(tags=["notifications"])


def _ensure_telegram_delivery_enabled() -> None:
    if not is_feature_enabled("telegram_delivery"):
        raise HTTPException(status_code=404, detail="Telegram delivery feature is disabled.")


@router.get("/notifications/telegram/preview", response_model=TelegramNotificationPreview)
async def preview_telegram_notification(
    root: str | None = None,
    limit: int = 3,
    event_kind: TelegramDeliveryEventKind = TelegramDeliveryEventKind.DIGEST,
    ignore_quiet_hours: bool = False,
) -> TelegramNotificationPreview:
    _ensure_telegram_delivery_enabled()
    return get_app_container().telegram_notification_service.preview(
        root=root,
        limit=min(max(int(limit), 1), 10),
        event_kind=event_kind,
        ignore_quiet_hours=ignore_quiet_hours,
    )


@router.post("/notifications/telegram/send", response_model=TelegramNotificationSendResult)
async def send_telegram_notification(payload: TelegramNotificationSendRequest) -> TelegramNotificationSendResult:
    _ensure_telegram_delivery_enabled()
    return get_app_container().telegram_notification_service.send(payload)


@router.get("/notifications/telegram/ops-preview", response_model=TelegramOpsAlertPreview)
async def preview_telegram_ops_alerts(
    stale_after_minutes: int | None = None,
    failed_runs_limit: int | None = None,
) -> TelegramOpsAlertPreview:
    _ensure_telegram_delivery_enabled()
    return get_app_container().telegram_ops_alert_service.preview(
        stale_after_minutes=stale_after_minutes,
        failed_runs_limit=failed_runs_limit,
    )


@router.post("/notifications/telegram/ops-send", response_model=TelegramOpsAlertSendResult)
async def send_telegram_ops_alerts(payload: TelegramOpsAlertSendRequest) -> TelegramOpsAlertSendResult:
    _ensure_telegram_delivery_enabled()
    return get_app_container().telegram_ops_alert_service.send(payload)
