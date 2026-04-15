from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class TelegramDeliveryEventKind(StrEnum):
    DIGEST = "digest"
    SIGNAL_OPEN = "signal_open"
    RESOLUTION = "resolution"
    POST_MORTEM = "post_mortem"


class TelegramDeliverySourceKind(StrEnum):
    MANUAL = "manual"
    SCHEDULE = "schedule"


class TelegramNotificationPreview(BaseModel):
    root: str
    enabled: bool
    configured: bool
    event_kind: TelegramDeliveryEventKind = TelegramDeliveryEventKind.DIGEST
    quiet_hours_active: bool = False
    suppressed_reason: str | None = None
    delivery_allowed: bool = True
    chat_id: str | None = None
    parse_mode: str
    signal_ids: list[str] = Field(default_factory=list)
    message: str
    generated_at: datetime


class TelegramNotificationSendRequest(BaseModel):
    root: str | None = None
    limit: int = 3
    event_kind: TelegramDeliveryEventKind = TelegramDeliveryEventKind.DIGEST
    delivery_source: TelegramDeliverySourceKind = TelegramDeliverySourceKind.MANUAL
    ignore_quiet_hours: bool = False
    dry_run: bool = False


class TelegramNotificationSendResult(BaseModel):
    delivered: bool
    delivery_status: str
    root: str
    chat_id: str | None = None
    signal_ids: list[str] = Field(default_factory=list)
    generated_at: datetime
    preview: TelegramNotificationPreview
    provider_message_id: str | None = None
    detail: str | None = None


class TelegramOpsAlertItem(BaseModel):
    kind: str
    severity: str
    title: str
    detail: str


class TelegramOpsAlertPreview(BaseModel):
    enabled: bool
    configured: bool
    chat_id: str | None = None
    parse_mode: str
    alert_items: list[TelegramOpsAlertItem] = Field(default_factory=list)
    message: str
    generated_at: datetime


class TelegramOpsAlertSendRequest(BaseModel):
    dry_run: bool = False
    stale_after_minutes: int | None = None
    failed_runs_limit: int | None = None


class TelegramOpsAlertSendResult(BaseModel):
    delivered: bool
    delivery_status: str
    chat_id: str | None = None
    generated_at: datetime
    preview: TelegramOpsAlertPreview
    provider_message_id: str | None = None
    detail: str | None = None
