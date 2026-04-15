from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from libs.domain.contracts import (
    AdminHealthSnapshot,
    EvaluationSummary,
    FinalSignalCard,
    FinalSignalDetail,
    JournalEntry,
    JournalEntryKind,
    RootDeepDive,
    RootSeriesSummary,
    SessionType,
    SignalDirection,
    SignalStatus,
)
from libs.preferences.contracts import (
    NotificationDeliveryActivityFilters,
    NotificationDeliveryActivityGroup,
    NotificationDeliveryActivityItem,
    NotificationDeliveryActivityPagination,
    NotificationDeliveryWindow,
)


class DashboardKpi(BaseModel):
    label: str
    value: str
    tone: str = "neutral"
    detail: str | None = None


class DashboardQualityPair(BaseModel):
    provider_a: str
    provider_b: str
    latest_contract: str | None = None
    latest_at: datetime | None = None
    contracts_count: int = 0
    mismatch_rate_overlap: float | None = None


class DashboardSnapshot(BaseModel):
    generated_at: datetime
    selected_root: str
    roots: list[RootSeriesSummary] = Field(default_factory=list)
    root_details: RootDeepDive | None = None
    spotlight_signals: list[FinalSignalCard] = Field(default_factory=list)
    recent_signals: list[FinalSignalCard] = Field(default_factory=list)
    evaluation: EvaluationSummary
    admin_health: AdminHealthSnapshot
    quality_pairs: list[DashboardQualityPair] = Field(default_factory=list)
    kpis: list[DashboardKpi] = Field(default_factory=list)


class WorkspaceRootPulse(BaseModel):
    root_code: str
    base_asset: str
    session_type: SessionType | None = None
    active_contract: str
    active_signals: int = 0
    next_contract_share: float = 0.0
    liquidity_rank: int = 0
    best_direction: SignalDirection | None = None
    headline: str
    tone: str = "neutral"


class WorkspaceActionItem(BaseModel):
    title: str
    detail: str
    tone: str = "neutral"


class SignalMetricBar(BaseModel):
    label: str
    value: float
    max_value: float = 1.0
    tone: str = "neutral"
    detail: str | None = None


class SignalTimelineEvent(BaseModel):
    at: datetime
    title: str
    kind: str
    detail: str
    tone: str = "neutral"


class HorizonPulsePoint(BaseModel):
    horizon: str
    signal_probability: float
    return_score: float
    realized_volatility: float
    trend_slope: float
    tone: str = "neutral"


class SignalVisualSnapshot(BaseModel):
    metric_bars: list[SignalMetricBar] = Field(default_factory=list)
    timeline: list[SignalTimelineEvent] = Field(default_factory=list)
    horizon_pulse: list[HorizonPulsePoint] = Field(default_factory=list)


class WorkspaceSnapshot(BaseModel):
    generated_at: datetime
    selected_root: str
    selected_signal_id: str | None = None
    roots: list[RootSeriesSummary] = Field(default_factory=list)
    pulses: list[WorkspaceRootPulse] = Field(default_factory=list)
    signal_lane: list[FinalSignalCard] = Field(default_factory=list)
    focus_signal: FinalSignalDetail | None = None
    root_details: RootDeepDive | None = None
    evaluation: EvaluationSummary
    admin_health: AdminHealthSnapshot
    quality_pairs: list[DashboardQualityPair] = Field(default_factory=list)
    action_items: list[WorkspaceActionItem] = Field(default_factory=list)
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
    focus_visual: SignalVisualSnapshot | None = None
    telegram_preview_message: str | None = None
    telegram_delivery_ready: bool = False


class WorkspaceSignalSnapshot(BaseModel):
    generated_at: datetime
    signal: FinalSignalDetail
    root_details: RootDeepDive | None = None
    related_signals: list[FinalSignalCard] = Field(default_factory=list)
    evaluation: EvaluationSummary
    visual: SignalVisualSnapshot
    telegram_preview_message: str | None = None
    telegram_delivery_ready: bool = False


class JournalWorkspaceEntry(BaseModel):
    entry: JournalEntry
    signal: FinalSignalCard


class JournalWorkspaceSnapshot(BaseModel):
    generated_at: datetime
    roots: list[RootSeriesSummary] = Field(default_factory=list)
    selected_root: str | None = None
    selected_status: SignalStatus | None = None
    selected_kind: JournalEntryKind | None = None
    selected_signal_id: str | None = None
    entries: list[JournalWorkspaceEntry] = Field(default_factory=list)
    related_signals: list[FinalSignalCard] = Field(default_factory=list)
    total_entries: int = 0
    thesis_entries: int = 0
    risk_entries: int = 0
    post_mortems: int = 0


class DeliveryHistoryWorkspaceSnapshot(BaseModel):
    generated_at: datetime
    roots: list[RootSeriesSummary] = Field(default_factory=list)
    selected_root: str | None = None
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
