from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class AssetClass(StrEnum):
    CURRENCY = "currency"
    INDEX = "index"
    COMMODITY = "commodity"


class SessionType(StrEnum):
    MORNING = "morning"
    MAIN = "main"
    EVENING = "evening"
    WEEKEND = "weekend"
    CLEARING = "clearing"
    HALTED = "halted"


class HorizonCode(StrEnum):
    H1S = "H1S"
    H3S = "H3S"
    H2W = "H2W"
    H4W = "H4W"


class SignalDirection(StrEnum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NO_EDGE = "no_edge"


class SkepticVerdict(StrEnum):
    PASS = "pass"
    SOFT_FAIL = "soft_fail"
    REJECT = "reject"
    HUMAN_REVIEW = "human_review"


class SignalStatus(StrEnum):
    ACTIVE = "active"
    RESOLVED = "resolved"
    INVALIDATED = "invalidated"


class SignalWorkflowState(StrEnum):
    WATCHING = "watching"
    VALIDATING = "validating"
    READY = "ready"
    IGNORED = "ignored"
    ESCALATE = "escalate"
    RESOLVED = "resolved"


class ResolutionOutcome(StrEnum):
    WIN = "win"
    LOSS = "loss"
    NEUTRAL = "neutral"
    EXPIRED = "expired"


class JournalEntryKind(StrEnum):
    THESIS = "thesis"
    RISK_NOTE = "risk_note"
    EXECUTION_NOTE = "execution_note"
    POST_MORTEM = "post_mortem"
    INVALIDATION_BREACH = "invalidation_breach"
    DATA_ANOMALY = "data_anomaly"


class HealthStatus(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"
    NOT_OK = "not_ok"


class UniverseStatus(StrEnum):
    SELECTED = "selected"
    WATCHLIST = "watchlist"
    EXCLUDED = "excluded"


class ManualOverrideState(StrEnum):
    NONE = "none"
    ALLOW = "allow"
    DENY = "deny"
    LOCK = "lock"


class AnalystKind(StrEnum):
    TREND_VOL = "trend_vol"
    FLOW_LIQUIDITY = "flow_liquidity"
    OI_ROLL = "oi_roll"
    MACRO_EVENT = "macro_event"


class CapabilityRegistry(BaseModel):
    historical_bars: bool
    stream_bars: bool
    trades: bool
    order_book: bool
    status: bool
    futures_limits: bool
    sandbox: bool
    auth_type: str
    known_constraints: list[str] = Field(default_factory=list)


class SourceHealth(BaseModel):
    provider: str
    role: str
    status: HealthStatus
    detail: str
    freshness_seconds: int | None = None
    primary: bool = False


class RootSeriesSummary(BaseModel):
    root_code: str
    asset_class: AssetClass
    base_asset: str
    active_contract: str
    next_contract: str
    liquidity_rank: int
    liquidity_score: float = 0.0
    universe_status: UniverseStatus = UniverseStatus.WATCHLIST
    manual_override: ManualOverrideState = ManualOverrideState.NONE
    selection_reasons: list[str] = Field(default_factory=list)
    primary_provider: str
    secondary_provider: str | None = None
    session_rule_set: str


class SessionSnapshot(BaseModel):
    calendar_day: date
    trading_day: date
    session_type: SessionType
    session_start_at: datetime
    session_end_at: datetime
    is_weekend_linked: bool
    is_clearing_window: bool
    is_near_expiry: bool = False
    effective_rule_set: str


class ContinuousSeriesSnapshot(BaseModel):
    active_contract: str
    next_contract: str
    days_to_expiry: int
    expiry_date: date | None = None
    days_to_last_trade: int
    roll_risk_flag: bool
    next_contract_share: float
    roll_state: str = "stable"
    back_adjustment_method: str = "difference_on_roll"
    estimated_roll_date: date | None = None


class RollEventPreview(BaseModel):
    root_code: str
    from_contract: str
    to_contract: str
    event_type: str
    effective_trading_day: date
    reason: str
    status: str


class FeatureSnapshot(BaseModel):
    snapshot_id: str
    root: str
    contract: str
    horizon: HorizonCode
    as_of: datetime
    feature_version: str
    point_in_time_correct: bool = True
    session_of_day: SessionType
    proximity_to_clearing_minutes: int | None = None
    weekend_linked: bool
    days_to_expiry: int
    days_to_last_trade: int
    roll_state: str
    roll_risk_flag: bool
    next_contract_share: float
    return_score: float
    realized_volatility: float
    atr_ratio: float
    trend_slope: float
    vwap_distance_bps: float
    breakout_state: str
    overnight_gap_regime: str


class AnalystOutput(BaseModel):
    output_id: str
    root: str
    contract: str
    horizon: HorizonCode
    analyst: AnalystKind
    generated_at: datetime
    direction: SignalDirection
    probability: float
    confidence: float
    drivers: list[str] = Field(default_factory=list)
    objections: list[str] = Field(default_factory=list)
    invalidation_conditions: list[str] = Field(default_factory=list)
    freshness_score: float


class SkepticReview(BaseModel):
    review_id: str
    root: str
    contract: str
    horizon: HorizonCode
    generated_at: datetime
    skeptic_score: float
    verdict: SkepticVerdict
    main_objections: list[str] = Field(default_factory=list)
    data_quality_flags: list[str] = Field(default_factory=list)


class SignalResolution(BaseModel):
    resolution_id: str
    signal_id: str
    root: str
    contract: str
    horizon: HorizonCode
    resolved_at: datetime
    status: SignalStatus
    outcome: ResolutionOutcome
    realized_return_bps: float
    realized_hit: bool
    resolution_note: str
    post_mortem_summary: str


class JournalEntryCreate(BaseModel):
    kind: JournalEntryKind
    title: str
    note: str
    author: str = "system"
    tags: list[str] = Field(default_factory=list)


class SignalWorkflowStateUpdate(BaseModel):
    workflow_state: SignalWorkflowState


class JournalEntry(BaseModel):
    entry_id: str
    signal_id: str
    kind: JournalEntryKind
    title: str
    note: str
    author: str
    created_at: datetime
    tags: list[str] = Field(default_factory=list)


class AdminRecalculateRequest(BaseModel):
    root: str | None = None
    as_of: datetime | None = None
    resolve_due: bool = True


class AdminRecalculateResult(BaseModel):
    roots_processed: int
    signals_built: int
    signals_resolved: int
    as_of: datetime | None = None
    details: list[str] = Field(default_factory=list)


class CalibrationBin(BaseModel):
    lower_bound: float
    upper_bound: float
    count: int
    avg_confidence: float
    empirical_win_rate: float


class EvaluationSummary(BaseModel):
    resolved_signals: int
    actionable_signals: int
    brier_score: float | None = None
    brier_skill_score: float | None = None
    log_loss: float | None = None
    precision: float | None = None
    recall: float | None = None
    calibration_error: float | None = None
    top_k_precision: float | None = None
    top_k: int
    calibration_bins: list[CalibrationBin] = Field(default_factory=list)


class EvaluationSlice(BaseModel):
    slice_key: str
    slice_value: str
    summary: EvaluationSummary


class EvaluationReport(BaseModel):
    overall: EvaluationSummary
    slices: list[EvaluationSlice] = Field(default_factory=list)


class AdminReplayRequest(BaseModel):
    root: str | None = None
    as_of: datetime
    top_k: int = 5
    limit: int = 500


class AdminReplayResult(BaseModel):
    recalculation: AdminRecalculateResult
    evaluation_report: EvaluationReport


class AdminMoexReferenceSyncRequest(BaseModel):
    as_of: datetime | None = None
    from_date: date | None = None
    to_date: date | None = None
    sync_calendar: bool = True
    sync_contracts: bool = True


class AdminMoexReferenceSyncResult(BaseModel):
    source: str
    calendar_days_synced: int
    contracts_synced: int
    effective_rule_set: str | None = None
    details: list[str] = Field(default_factory=list)


class AdminBackupRequest(BaseModel):
    label: str | None = None


class AdminBackupResult(BaseModel):
    backup_path: str
    created_at: datetime
    size_bytes: int


class AdminCleanupRequest(BaseModel):
    retention_days: int = Field(default=30, ge=0, le=3650)


class AdminCleanupResult(BaseModel):
    retention_days: int
    total_deleted: int
    details: list[str] = Field(default_factory=list)


class RuntimeMetric(BaseModel):
    name: str
    value: float
    unit: str
    status: str
    detail: str | None = None


class AdminHealthSnapshot(BaseModel):
    status: str
    database_status: str
    roots_count: int
    active_signals: int
    resolved_signals: int
    invalidated_signals: int
    journal_entries: int
    latest_signal_at: datetime | None = None
    latest_resolution_at: datetime | None = None
    latest_journal_at: datetime | None = None
    backup_artifacts: int = 0
    latest_backup_at: datetime | None = None
    source_health: list[SourceHealth] = Field(default_factory=list)
    metrics: list[RuntimeMetric] = Field(default_factory=list)


class FinalSignalCard(BaseModel):
    signal_id: str
    version: int
    root: str
    contract: str
    horizon: HorizonCode
    status: SignalStatus
    direction_final: SignalDirection
    probability_up: float
    probability_down: float
    probability_no_edge: float
    confidence_final: float
    priority_score: int
    roll_risk: float
    expiry_risk: float
    skeptic_score: float
    skeptic_verdict: SkepticVerdict
    generated_at: datetime
    freshness_score: float
    summary: str
    workflow_state: SignalWorkflowState = SignalWorkflowState.WATCHING


class FinalSignalDetail(FinalSignalCard):
    drivers: list[str] = Field(default_factory=list)
    objections: list[str] = Field(default_factory=list)
    invalidation_conditions: list[str] = Field(default_factory=list)
    data_sources: list[str] = Field(default_factory=list)
    resolution: SignalResolution | None = None
    journal_entries: list[JournalEntry] = Field(default_factory=list)


class RootDeepDive(BaseModel):
    root: RootSeriesSummary
    session: SessionSnapshot
    continuous_series: ContinuousSeriesSnapshot
    roll_event: RollEventPreview | None = None
    feature_snapshots: list[FeatureSnapshot] = Field(default_factory=list)
    analyst_outputs: list[AnalystOutput] = Field(default_factory=list)
    skeptic_reviews: list[SkepticReview] = Field(default_factory=list)
    active_signals: list[FinalSignalCard]
    sources: list[SourceHealth]
    capability_registry: dict[str, CapabilityRegistry]
