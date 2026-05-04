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
    SignalWorkflowState,
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


class ModelRoleAssignment(BaseModel):
    role_key: str
    role_label: str
    owner: str
    product: str
    model: str
    control_mode: str = "fixed"
    detail: str | None = None


class MarketDataFeedStatus(BaseModel):
    provider: str
    owner: str
    role: str
    status: str
    primary: bool = False
    detail: str | None = None
    freshness_seconds: int | None = None
    last_update_at: datetime | None = None


class ReferenceSyncStatus(BaseModel):
    source: str
    owner: str
    status: str
    detail: str | None = None
    last_sync_at: datetime | None = None


class RuntimeControlPanel(BaseModel):
    generated_at: datetime
    llm_owner: str
    llm_product: str
    llm_model: str
    data_mode: str = "degraded_feed"
    data_mode_detail: str | None = None
    model_roles: list[ModelRoleAssignment] = Field(default_factory=list)
    market_data_feeds: list[MarketDataFeedStatus] = Field(default_factory=list)
    latest_market_data_at: datetime | None = None
    reference_sync: ReferenceSyncStatus


class TrustRibbonItem(BaseModel):
    label: str
    value: str
    tone: str = "neutral"
    detail: str | None = None


class TrustRibbon(BaseModel):
    headline: str
    tone: str = "neutral"
    items: list[TrustRibbonItem] = Field(default_factory=list)


class SystemConfidencePanel(BaseModel):
    score: int
    label: str
    tone: str = "neutral"
    detail: str
    drivers: list[str] = Field(default_factory=list)


class WatchlistEntry(BaseModel):
    watch_key: str
    root_code: str
    signal_id: str | None = None
    note: str | None = None
    priority_rank: int = 0
    focus_reason: str | None = None
    last_reviewed_at: datetime | None = None
    review_state: str = "review_due"
    added_at: datetime
    updated_at: datetime
    signal: FinalSignalCard | None = None


class WatchlistEntryCreate(BaseModel):
    root_code: str
    signal_id: str | None = None
    note: str | None = None


class ConfidenceFactor(BaseModel):
    label: str
    value: float
    tone: str = "neutral"
    detail: str | None = None


class ConfidenceDecomposition(BaseModel):
    headline: str
    factors: list[ConfidenceFactor] = Field(default_factory=list)


class SignalChangeSummary(BaseModel):
    signal_id: str
    previous_signal_id: str | None = None
    changed: bool = False
    summary: str
    probability_up_delta: float = 0.0
    probability_down_delta: float = 0.0
    confidence_delta: float = 0.0
    skeptic_delta: float = 0.0
    freshness_delta: float = 0.0
    drivers_added: list[str] = Field(default_factory=list)
    drivers_removed: list[str] = Field(default_factory=list)
    invalidations_added: list[str] = Field(default_factory=list)
    invalidations_removed: list[str] = Field(default_factory=list)
    data_sources_added: list[str] = Field(default_factory=list)
    data_sources_removed: list[str] = Field(default_factory=list)


class HistoricalSetup(BaseModel):
    signal_id: str
    outcome: str
    realized_return_bps: float
    resolved_at: datetime
    note: str
    similarity_score: float


class DecisionTimelineItem(BaseModel):
    at: datetime
    kind: str
    title: str
    detail: str
    tone: str = "neutral"
    tags: list[str] = Field(default_factory=list)


class HorizonComparisonItem(BaseModel):
    horizon: str
    direction: str
    confidence: float
    skeptic_score: float
    freshness_score: float
    attention_score: float
    summary: str
    workflow_state: SignalWorkflowState


class HorizonComparisonSnapshot(BaseModel):
    root: str
    items: list[HorizonComparisonItem] = Field(default_factory=list)


class ReviewBundle(BaseModel):
    watchlist_items: int = 0
    watched_roots: int = 0
    watched_root_codes: list[str] = Field(default_factory=list)
    review_due_items: int = 0
    reviewed_today_items: int = 0
    decisions_logged: int = 0
    ignored_signals: int = 0
    resolved_signals: int = 0
    outcome_summary: list[str] = Field(default_factory=list)
    tag_suggestions: list[str] = Field(default_factory=list)
    next_review_actions: list[str] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)


class AttentionInboxItem(BaseModel):
    item_key: str
    item_type: str = "signal"
    root_code: str
    signal_id: str | None = None
    title: str
    reason: str
    what_changed: str
    next_step: str
    tone: str = "neutral"
    priority_score: int = 0
    attention_score: float = 0.0
    workflow_state: SignalWorkflowState | None = None
    current_price: float | None = None
    price_unit: str | None = None
    market_status: str = "unknown"
    market_status_detail: str | None = None
    href: str


class MorningBriefItem(BaseModel):
    title: str
    detail: str
    href: str | None = None
    tone: str = "neutral"


class MorningBriefSnapshot(BaseModel):
    market_status: str = "hidden"
    market_detail: str | None = None
    last_price: float | None = None
    price_unit: str | None = None
    top_attention: list[MorningBriefItem] = Field(default_factory=list)
    review_highlights: list[str] = Field(default_factory=list)
    dont_chase: list[MorningBriefItem] = Field(default_factory=list)
    review_due_items: int = 0
    watched_roots: list[str] = Field(default_factory=list)
    telegram_status: str = "preview"
    data_mode: str = "unknown"
    signals_only: bool = True


class WatchlistWorkbenchSnapshot(BaseModel):
    total_items: int = Field(default=0, ge=0)
    review_due_items: int = Field(default=0, ge=0)
    reviewed_today_items: int = Field(default=0, ge=0)
    watched_roots: list[str] = Field(default_factory=list)
    signal_linked_items: int = Field(default=0, ge=0)
    root_level_items: int = Field(default=0, ge=0)
    first_due_watch_key: str | None = None
    first_due_root_code: str | None = None
    first_due_signal_id: str | None = None
    first_due_focus_reason: str | None = None
    next_step: str = "No watchlist items are queued yet."
    signals_only: bool = True


class RuntimeFreshnessPolicySnapshot(BaseModel):
    fresh_max_seconds: int = 30
    aging_max_seconds: int = 180
    stale_max_seconds: int = 900
    degraded_max_seconds: int = 3600


class RuntimeModelRouteUpdate(BaseModel):
    role_key: str
    owner: str
    product: str
    model: str
    control_mode: str = "editable"
    detail: str | None = None


class RuntimeRolePromptProfile(BaseModel):
    role_key: str
    role_label: str
    prompt_template: str
    control_mode: str = "editable"
    detail: str | None = None
    variables: list[str] = Field(default_factory=list)
    rendered_prompt: str | None = None
    default_prompt_template: str | None = None
    current_version_id: str | None = None
    approved_version_id: str | None = None
    pending_version_id: str | None = None
    approval_required: bool = False
    approval_state: str = "live"
    approval_note: str | None = None
    approval_reasons: list[str] = Field(default_factory=list)
    effective_prompt_template: str | None = None
    effective_control_mode: str | None = None
    effective_rendered_prompt: str | None = None
    version_history: list["RuntimeRolePromptVersion"] = Field(default_factory=list)


class RuntimeRolePromptUpdate(BaseModel):
    role_key: str
    prompt_template: str = Field(min_length=1, max_length=6000)
    control_mode: str = "editable"
    detail: str | None = None


class RuntimeRolePromptRestoreRequest(BaseModel):
    role_key: str
    version_id: str = Field(min_length=1, max_length=128)


class RuntimeRolePromptApproveRequest(BaseModel):
    role_key: str
    version_id: str | None = Field(default=None, max_length=128)


class RuntimeRolePromptDismissRequest(BaseModel):
    role_key: str
    version_id: str | None = Field(default=None, max_length=128)


class RuntimePromptDiffLine(BaseModel):
    kind: str
    text: str


class RuntimePromptValidationIssue(BaseModel):
    code: str
    severity: str
    message: str


class RuntimeRolePromptDiff(BaseModel):
    role_key: str
    role_label: str
    has_changes: bool
    can_save: bool = True
    approval_required: bool = False
    summary: str
    baseline_version_id: str | None = None
    baseline_label: str | None = None
    release_note_preview: str | None = None
    metadata_changes: list[str] = Field(default_factory=list)
    approval_reasons: list[str] = Field(default_factory=list)
    unresolved_variables: list[str] = Field(default_factory=list)
    validation_issues: list[RuntimePromptValidationIssue] = Field(default_factory=list)
    lines: list[RuntimePromptDiffLine] = Field(default_factory=list)
    before_rendered_prompt: str | None = None
    after_rendered_prompt: str | None = None


class RuntimeRolePromptVersion(BaseModel):
    version_id: str
    action: str
    summary: str
    prompt_template: str
    control_mode: str = "editable"
    detail: str | None = None
    created_at: datetime
    lifecycle_state: str = "history"
    release_note: str | None = None
    dismissed_version_id: str | None = None
    restored_from_version_id: str | None = None
    restorable: bool = True


class RuntimeFreshnessPolicyUpdate(BaseModel):
    fresh_max_seconds: int = Field(default=30, ge=1)
    aging_max_seconds: int = Field(default=180, ge=1)
    stale_max_seconds: int = Field(default=900, ge=1)
    degraded_max_seconds: int = Field(default=3600, ge=1)


class RuntimeAuditEvent(BaseModel):
    event_id: str
    category: str
    action: str
    target_key: str | None = None
    detail: str
    payload: dict[str, object] = Field(default_factory=dict)
    created_at: datetime


class RuntimeControlSnapshot(BaseModel):
    generated_at: datetime
    model_routes: list[ModelRoleAssignment] = Field(default_factory=list)
    role_prompts: list[RuntimeRolePromptProfile] = Field(default_factory=list)
    freshness_policy: RuntimeFreshnessPolicySnapshot
    audit_trail: list[RuntimeAuditEvent] = Field(default_factory=list)


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
    control_panel: RuntimeControlPanel
    trust_ribbon: TrustRibbon
    system_confidence: SystemConfidencePanel


class WorkspaceRootPulse(BaseModel):
    root_code: str
    base_asset: str
    session_type: SessionType | None = None
    active_contract: str
    active_signals: int = 0
    next_contract_share: float = 0.0
    liquidity_rank: int = 0
    best_direction: SignalDirection | None = None
    current_price: float | None = None
    price_change_abs: float | None = None
    price_change_pct: float | None = None
    price_unit: str | None = None
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


class InstrumentChartPoint(BaseModel):
    label: str
    value: float
    open: float
    high: float
    low: float
    close: float


class InstrumentChartOverlay(BaseModel):
    key: str
    value: float
    tone: str = "neutral"


class InstrumentChartSeries(BaseModel):
    label: str
    points: list[InstrumentChartPoint] = Field(default_factory=list)
    open_price: float
    current_price: float
    high_price: float
    low_price: float
    change_abs: float
    change_pct: float
    overlays: list[InstrumentChartOverlay] = Field(default_factory=list)


class InstrumentMarketSnapshot(BaseModel):
    root_code: str
    contract: str
    base_asset: str
    unit: str
    current_price: float
    price_change_abs: float
    price_change_pct: float
    price_source: str
    status: str = "fresh"
    status_detail: str | None = None
    as_of: datetime
    daily: InstrumentChartSeries
    weekly: InstrumentChartSeries
    monthly: InstrumentChartSeries


class WorkspaceSnapshot(BaseModel):
    generated_at: datetime
    selected_root: str
    selected_signal_id: str | None = None
    roots: list[RootSeriesSummary] = Field(default_factory=list)
    pulses: list[WorkspaceRootPulse] = Field(default_factory=list)
    market_snapshot: InstrumentMarketSnapshot | None = None
    signal_lane: list[FinalSignalCard] = Field(default_factory=list)
    focus_signal: FinalSignalDetail | None = None
    root_details: RootDeepDive | None = None
    evaluation: EvaluationSummary
    admin_health: AdminHealthSnapshot
    quality_pairs: list[DashboardQualityPair] = Field(default_factory=list)
    control_panel: RuntimeControlPanel
    trust_ribbon: TrustRibbon
    system_confidence: SystemConfidencePanel
    workspace_mode: str = "scan"
    watchlist: list[WatchlistEntry] = Field(default_factory=list)
    attention_inbox: list[AttentionInboxItem] = Field(default_factory=list)
    morning_brief: MorningBriefSnapshot = Field(default_factory=MorningBriefSnapshot)
    watchlist_workbench: WatchlistWorkbenchSnapshot = Field(default_factory=WatchlistWorkbenchSnapshot)
    comparison: HorizonComparisonSnapshot | None = None
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
    focus_signal_diff: SignalChangeSummary | None = None
    focus_confidence: ConfidenceDecomposition | None = None
    decision_log_preview: list[DecisionTimelineItem] = Field(default_factory=list)
    telegram_preview_message: str | None = None
    telegram_delivery_ready: bool = False
    review_bundle: ReviewBundle = Field(default_factory=ReviewBundle)


class WorkspaceSignalSnapshot(BaseModel):
    generated_at: datetime
    signal: FinalSignalDetail
    roots: list[RootSeriesSummary] = Field(default_factory=list)
    root_details: RootDeepDive | None = None
    market_snapshot: InstrumentMarketSnapshot | None = None
    related_signals: list[FinalSignalCard] = Field(default_factory=list)
    evaluation: EvaluationSummary
    control_panel: RuntimeControlPanel
    trust_ribbon: TrustRibbon
    system_confidence: SystemConfidencePanel
    visual: SignalVisualSnapshot
    signal_diff: SignalChangeSummary | None = None
    confidence_decomposition: ConfidenceDecomposition | None = None
    decision_log: list[DecisionTimelineItem] = Field(default_factory=list)
    similar_setups: list[HistoricalSetup] = Field(default_factory=list)
    telegram_preview_message: str | None = None
    telegram_delivery_ready: bool = False


class JournalWorkspaceEntry(BaseModel):
    entry: JournalEntry
    signal: FinalSignalCard


class JournalDecisionLogItem(BaseModel):
    signal: FinalSignalCard
    updated_at: datetime
    latest_entry: JournalEntry | None = None
    decision_summary: str
    why_now: list[str] = Field(default_factory=list)
    next_watch: list[str] = Field(default_factory=list)


class JournalTagSummary(BaseModel):
    tag: str
    count: int
    roots: list[str] = Field(default_factory=list)
    kinds: list[str] = Field(default_factory=list)


class JournalWorkspaceSnapshot(BaseModel):
    generated_at: datetime
    roots: list[RootSeriesSummary] = Field(default_factory=list)
    selected_root: str | None = None
    selected_status: SignalStatus | None = None
    selected_kind: JournalEntryKind | None = None
    selected_signal_id: str | None = None
    selected_tag: str | None = None
    decision_log: list[JournalDecisionLogItem] = Field(default_factory=list)
    entries: list[JournalWorkspaceEntry] = Field(default_factory=list)
    related_signals: list[FinalSignalCard] = Field(default_factory=list)
    total_entries: int = 0
    thesis_entries: int = 0
    risk_entries: int = 0
    post_mortems: int = 0
    note_templates: list[dict[str, str]] = Field(default_factory=list)
    tag_suggestions: list[str] = Field(default_factory=list)
    tag_counts: list[JournalTagSummary] = Field(default_factory=list)


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
