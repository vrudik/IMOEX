from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from libs.domain.contracts import HorizonCode, RootSeriesSummary


class NotificationEventKind(StrEnum):
    DIGEST = "digest"
    SIGNAL_OPEN = "signal_open"
    RESOLUTION = "resolution"
    POST_MORTEM = "post_mortem"


class NotificationDeliveryActivityAction(StrEnum):
    SEND_NOW = "send_now"
    SEND_NOW_FORCE = "send_now_force"
    SCHEDULE_DELIVERY = "schedule_delivery"
    SKIP_NEXT = "skip_next"
    UNDO_SKIP = "undo_skip"


class NotificationPreferenceSnapshot(BaseModel):
    profile_id: str = "default"
    default_root: str | None = None
    subscribed_roots: list[str] = Field(default_factory=list)
    subscribed_horizons: list[HorizonCode] = Field(default_factory=list)
    subscribed_event_kinds: list[NotificationEventKind] = Field(default_factory=list)
    skip_next_event_kinds: list[NotificationEventKind] = Field(default_factory=list)
    min_priority_score: int = 0
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    suppress_during_quiet_hours: bool = True
    digest_limit: int = 3
    updated_at: datetime | None = None


class NotificationPreferenceUpdate(BaseModel):
    default_root: str | None = None
    subscribed_roots: list[str] = Field(default_factory=list)
    subscribed_horizons: list[HorizonCode] = Field(default_factory=list)
    subscribed_event_kinds: list[NotificationEventKind] = Field(default_factory=list)
    min_priority_score: int = Field(default=0, ge=0, le=10)
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    suppress_during_quiet_hours: bool = True
    digest_limit: int = Field(default=3, ge=1, le=10)


class NotificationDeliverySkipRequest(BaseModel):
    event_kind: NotificationEventKind


class NotificationDeliveryWindow(BaseModel):
    job_id: str
    label: str
    event_kind: NotificationEventKind
    root_scope: str
    next_run_at: datetime | None = None
    due_now: bool = False
    subscription_enabled: bool = True
    skip_next_pending: bool = False
    quiet_hours_policy: str
    last_run_status: str | None = None
    last_run_detail: str | None = None


class NotificationDeliveryActivityItem(BaseModel):
    activity_id: str
    action: NotificationDeliveryActivityAction
    event_kind: NotificationEventKind
    delivery_source: str | None = None
    root_scope: str | None = None
    status: str
    detail: str
    signal_ids: list[str] = Field(default_factory=list)
    provider_message_id: str | None = None
    created_at: datetime


class NotificationDeliveryActivityFilters(BaseModel):
    root_scope: str | None = None
    event_kind: NotificationEventKind | None = None
    status: str | None = None


class NotificationDeliveryActivityGroup(BaseModel):
    value: str
    label: str
    count: int


class NotificationDeliveryActivityPagination(BaseModel):
    page: int = 1
    page_size: int = 8
    total_items: int = 0
    total_pages: int = 1
    has_previous: bool = False
    has_next: bool = False


class NotificationDeliveryActivityExportFormat(StrEnum):
    CSV = "csv"
    JSONL = "jsonl"


class NotificationPreferenceWorkspaceSnapshot(BaseModel):
    generated_at: datetime
    roots: list[RootSeriesSummary] = Field(default_factory=list)
    available_horizons: list[HorizonCode] = Field(default_factory=list)
    preferences: NotificationPreferenceSnapshot
    delivery_windows: list[NotificationDeliveryWindow] = Field(default_factory=list)
    delivery_activity: list[NotificationDeliveryActivityItem] = Field(default_factory=list)
    delivery_activity_filters: NotificationDeliveryActivityFilters = Field(
        default_factory=NotificationDeliveryActivityFilters
    )
    delivery_activity_by_event_kind: list[NotificationDeliveryActivityGroup] = Field(default_factory=list)
    delivery_activity_by_root_scope: list[NotificationDeliveryActivityGroup] = Field(default_factory=list)
    delivery_activity_by_status: list[NotificationDeliveryActivityGroup] = Field(default_factory=list)
    delivery_activity_pagination: NotificationDeliveryActivityPagination = Field(
        default_factory=NotificationDeliveryActivityPagination
    )
    telegram_configured: bool = False
    telegram_enabled: bool = False
