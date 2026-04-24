from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Integer, Numeric, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class SourceQualityCheckRecord(Base):
    __tablename__ = "source_quality_check"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    provider_a: Mapped[str] = mapped_column(String(32), index=True)
    provider_b: Mapped[str] = mapped_column(String(32), index=True)
    contract: Mapped[str] = mapped_column(String(64), index=True)

    from_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    till_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    count_a: Mapped[int] = mapped_column(Integer)
    count_b: Mapped[int] = mapped_column(Integer)
    overlap_count: Mapped[int] = mapped_column(Integer)
    missing_in_a: Mapped[int] = mapped_column(Integer)
    missing_in_b: Mapped[int] = mapped_column(Integer)
    mismatch_ohlc: Mapped[int] = mapped_column(Integer)
    mismatch_volume: Mapped[int] = mapped_column(Integer)
    mismatch_rate_overlap: Mapped[float] = mapped_column(Numeric(18, 10))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

    def to_dict(self) -> dict:
        return {
            "provider_a": self.provider_a,
            "provider_b": self.provider_b,
            "contract": self.contract,
            "from_ts": self.from_ts.isoformat(),
            "till_ts": self.till_ts.isoformat(),
            "count_a": int(self.count_a),
            "count_b": int(self.count_b),
            "overlap_count": int(self.overlap_count),
            "missing_in_a": int(self.missing_in_a),
            "missing_in_b": int(self.missing_in_b),
            "mismatch_ohlc": int(self.mismatch_ohlc),
            "mismatch_volume": int(self.mismatch_volume),
            "mismatch_rate_overlap": float(self.mismatch_rate_overlap),
            "created_at": self.created_at.isoformat(),
        }


class RootSeriesRecord(Base):
    __tablename__ = "root_series"

    root_code: Mapped[str] = mapped_column(String(32), primary_key=True)
    asset_class: Mapped[str] = mapped_column(String(32), index=True)
    base_asset: Mapped[str] = mapped_column(String(128))
    active_contract: Mapped[str] = mapped_column(String(64))
    next_contract: Mapped[str] = mapped_column(String(64))
    active_flag: Mapped[bool] = mapped_column(Boolean, default=True)
    liquidity_rank: Mapped[int] = mapped_column(Integer, index=True)
    liquidity_score: Mapped[float] = mapped_column(Numeric(18, 10), default=0)
    manual_allow: Mapped[bool] = mapped_column(Boolean, default=False)
    manual_deny: Mapped[bool] = mapped_column(Boolean, default=False)
    lock_selected: Mapped[bool] = mapped_column(Boolean, default=False)
    primary_provider: Mapped[str] = mapped_column(String(32))
    secondary_provider: Mapped[str | None] = mapped_column(String(32), nullable=True)
    session_rule_set: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ContractMetaRecord(Base):
    __tablename__ = "contract_meta"

    contract_code: Mapped[str] = mapped_column(String(64), primary_key=True)
    root_code: Mapped[str] = mapped_column(String(32), index=True)
    expiry_date: Mapped[date] = mapped_column(Date)
    last_trade_date: Mapped[date] = mapped_column(Date)
    tick_size: Mapped[float] = mapped_column(Numeric(18, 6))
    lot_size: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(16))
    active_flag: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ReferenceSyncStateRecord(Base):
    __tablename__ = "reference_sync_state"

    sync_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    source: Mapped[str] = mapped_column(String(64), index=True)
    detail: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class TradingSessionRecord(Base):
    __tablename__ = "trading_session"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    root_code: Mapped[str] = mapped_column(String(32), index=True)
    trading_day: Mapped[date] = mapped_column(Date, index=True)
    session_type: Mapped[str] = mapped_column(String(32))
    session_start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    session_end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    is_weekend_linked: Mapped[bool] = mapped_column(Boolean, default=False)
    is_clearing_window: Mapped[bool] = mapped_column(Boolean, default=False)
    effective_rule_set: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class FeatureSnapshotRecord(Base):
    __tablename__ = "feature_snapshot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    root_code: Mapped[str] = mapped_column(String(32), index=True)
    contract_code: Mapped[str] = mapped_column(String(64), index=True)
    horizon: Mapped[str] = mapped_column(String(16), index=True)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    feature_version: Mapped[str] = mapped_column(String(32))
    point_in_time_correct: Mapped[bool] = mapped_column(Boolean, default=True)
    session_of_day: Mapped[str] = mapped_column(String(32))
    proximity_to_clearing_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weekend_linked: Mapped[bool] = mapped_column(Boolean, default=False)
    days_to_expiry: Mapped[int] = mapped_column(Integer)
    days_to_last_trade: Mapped[int] = mapped_column(Integer)
    roll_state: Mapped[str] = mapped_column(String(32))
    roll_risk_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    next_contract_share: Mapped[float] = mapped_column(Numeric(10, 6))
    return_score: Mapped[float] = mapped_column(Numeric(18, 10))
    realized_volatility: Mapped[float] = mapped_column(Numeric(18, 10))
    atr_ratio: Mapped[float] = mapped_column(Numeric(18, 10))
    trend_slope: Mapped[float] = mapped_column(Numeric(18, 10))
    vwap_distance_bps: Mapped[float] = mapped_column(Numeric(18, 10))
    breakout_state: Mapped[str] = mapped_column(String(32))
    overnight_gap_regime: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class AnalystOutputRecord(Base):
    __tablename__ = "analyst_output"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    output_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    root_code: Mapped[str] = mapped_column(String(32), index=True)
    contract_code: Mapped[str] = mapped_column(String(64), index=True)
    horizon: Mapped[str] = mapped_column(String(16), index=True)
    analyst: Mapped[str] = mapped_column(String(32), index=True)
    direction: Mapped[str] = mapped_column(String(32))
    probability: Mapped[float] = mapped_column(Numeric(18, 10))
    confidence: Mapped[float] = mapped_column(Numeric(18, 10))
    freshness_score: Mapped[float] = mapped_column(Numeric(18, 10))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    drivers_blob: Mapped[str] = mapped_column(String(2048))
    objections_blob: Mapped[str] = mapped_column(String(2048))
    invalidation_conditions_blob: Mapped[str] = mapped_column(String(2048))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class SkepticReviewRecord(Base):
    __tablename__ = "skeptic_review"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    root_code: Mapped[str] = mapped_column(String(32), index=True)
    contract_code: Mapped[str] = mapped_column(String(64), index=True)
    horizon: Mapped[str] = mapped_column(String(16), index=True)
    skeptic_score: Mapped[float] = mapped_column(Numeric(18, 10))
    verdict: Mapped[str] = mapped_column(String(32), index=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    main_objections_blob: Mapped[str] = mapped_column(String(2048))
    data_quality_flags_blob: Mapped[str] = mapped_column(String(2048))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class SignalVersionRecord(Base):
    __tablename__ = "signal_version"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    signal_id: Mapped[str] = mapped_column(String(128), index=True)
    version: Mapped[int] = mapped_column(Integer, index=True)
    root_code: Mapped[str] = mapped_column(String(32), index=True)
    contract_code: Mapped[str] = mapped_column(String(64), index=True)
    horizon: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    direction_final: Mapped[str] = mapped_column(String(32))
    probability_up: Mapped[float] = mapped_column(Numeric(18, 10))
    probability_down: Mapped[float] = mapped_column(Numeric(18, 10))
    probability_no_edge: Mapped[float] = mapped_column(Numeric(18, 10))
    confidence_final: Mapped[float] = mapped_column(Numeric(18, 10))
    priority_score: Mapped[int] = mapped_column(Integer)
    skeptic_score: Mapped[float] = mapped_column(Numeric(18, 10), default=1)
    skeptic_verdict: Mapped[str] = mapped_column(String(32))
    freshness_score: Mapped[float | None] = mapped_column(Numeric(18, 10), nullable=True)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    summary: Mapped[str] = mapped_column(String(512))
    drivers_blob: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    objections_blob: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    invalidation_conditions_blob: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    data_sources_blob: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class FinalSignalRecord(Base):
    __tablename__ = "final_signal"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    signal_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    root_code: Mapped[str] = mapped_column(String(32), index=True)
    contract_code: Mapped[str] = mapped_column(String(64), index=True)
    horizon: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    direction_final: Mapped[str] = mapped_column(String(32))
    probability_up: Mapped[float] = mapped_column(Numeric(18, 10))
    probability_down: Mapped[float] = mapped_column(Numeric(18, 10))
    probability_no_edge: Mapped[float] = mapped_column(Numeric(18, 10))
    confidence_final: Mapped[float] = mapped_column(Numeric(18, 10))
    priority_score: Mapped[int] = mapped_column(Integer)
    roll_risk: Mapped[float] = mapped_column(Numeric(18, 10))
    expiry_risk: Mapped[float] = mapped_column(Numeric(18, 10))
    skeptic_score: Mapped[float] = mapped_column(Numeric(18, 10), default=1)
    skeptic_verdict: Mapped[str] = mapped_column(String(32))
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    freshness_score: Mapped[float] = mapped_column(Numeric(18, 10))
    summary: Mapped[str] = mapped_column(String(512))
    workflow_state: Mapped[str] = mapped_column(String(32), default="watching")
    drivers_blob: Mapped[str] = mapped_column(String(2048))
    objections_blob: Mapped[str] = mapped_column(String(2048))
    invalidation_conditions_blob: Mapped[str] = mapped_column(String(2048))
    data_sources_blob: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class SignalResolutionRecord(Base):
    __tablename__ = "signal_resolution"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    resolution_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    signal_id: Mapped[str] = mapped_column(String(128), index=True)
    root_code: Mapped[str] = mapped_column(String(32), index=True)
    contract_code: Mapped[str] = mapped_column(String(64), index=True)
    horizon: Mapped[str] = mapped_column(String(16), index=True)
    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    outcome: Mapped[str] = mapped_column(String(32), index=True)
    realized_return_bps: Mapped[float] = mapped_column(Numeric(18, 10))
    realized_hit: Mapped[bool] = mapped_column(Boolean, default=False)
    resolution_note: Mapped[str] = mapped_column(String(1024))
    post_mortem_summary: Mapped[str] = mapped_column(String(2048))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class UserJournalEntryRecord(Base):
    __tablename__ = "user_journal_entry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    entry_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    signal_id: Mapped[str] = mapped_column(String(128), index=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(256))
    note: Mapped[str] = mapped_column(String(4096))
    author: Mapped[str] = mapped_column(String(64))
    tags_json: Mapped[str] = mapped_column(String(1024), default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class UserWorkspaceWatchRecord(Base):
    __tablename__ = "user_workspace_watch"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    watch_key: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    profile_id: Mapped[str] = mapped_column(String(64), index=True)
    root_code: Mapped[str] = mapped_column(String(32), index=True)
    signal_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    note: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class UserNotificationPreferenceRecord(Base):
    __tablename__ = "user_notification_preference"

    profile_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    default_root: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    subscribed_roots_json: Mapped[str] = mapped_column(String(2048), default="[]")
    subscribed_horizons_json: Mapped[str] = mapped_column(String(512), default="[]")
    subscribed_event_kinds_json: Mapped[str] = mapped_column(String(512), default='["digest","signal_open","resolution","post_mortem"]')
    skip_next_event_kinds_json: Mapped[str] = mapped_column(String(512), default="[]")
    min_priority_score: Mapped[int] = mapped_column(Integer, default=0)
    quiet_hours_start: Mapped[str | None] = mapped_column(String(5), nullable=True)
    quiet_hours_end: Mapped[str | None] = mapped_column(String(5), nullable=True)
    suppress_during_quiet_hours: Mapped[bool] = mapped_column(Boolean, default=True)
    digest_limit: Mapped[int] = mapped_column(Integer, default=3)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class NotificationDeliveryEventRecord(Base):
    __tablename__ = "notification_delivery_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    activity_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    profile_id: Mapped[str] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(32), index=True)
    event_kind: Mapped[str] = mapped_column(String(32), index=True)
    delivery_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
    root_code: Mapped[str | None] = mapped_column(String(32), index=True, nullable=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    detail: Mapped[str] = mapped_column(String(2048))
    signal_ids_json: Mapped[str] = mapped_column(String(2048), default="[]")
    provider_message_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class RuntimeModelRouteRecord(Base):
    __tablename__ = "runtime_model_route"

    role_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner: Mapped[str] = mapped_column(String(64))
    product: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(128))
    control_mode: Mapped[str] = mapped_column(String(32), default="editable")
    detail: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class RuntimeRolePromptRecord(Base):
    __tablename__ = "runtime_role_prompt"

    role_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    prompt_template: Mapped[str] = mapped_column(String(16384))
    control_mode: Mapped[str] = mapped_column(String(32), default="editable")
    detail: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class RuntimeFreshnessPolicyRecord(Base):
    __tablename__ = "runtime_freshness_policy"

    policy_key: Mapped[str] = mapped_column(String(64), primary_key=True)
    fresh_max_seconds: Mapped[int] = mapped_column(Integer, default=30)
    aging_max_seconds: Mapped[int] = mapped_column(Integer, default=180)
    stale_max_seconds: Mapped[int] = mapped_column(Integer, default=900)
    degraded_max_seconds: Mapped[int] = mapped_column(Integer, default=3600)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class RuntimeAuditEventRecord(Base):
    __tablename__ = "runtime_audit_event"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    category: Mapped[str] = mapped_column(String(64), index=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    target_key: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    detail: Mapped[str] = mapped_column(String(2048))
    payload_json: Mapped[str] = mapped_column(String(8192), default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class SchedulerRunRecord(Base):
    __tablename__ = "scheduler_run"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    job_id: Mapped[str] = mapped_column(String(128), index=True)
    command: Mapped[str] = mapped_column(String(64))
    trigger_mode: Mapped[str] = mapped_column(String(32), index=True)
    idempotency_key: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    detail: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    payload_blob: Mapped[str] = mapped_column(String(8192), default="{}")
    result_blob: Mapped[str | None] = mapped_column(String(16384), nullable=True)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class SchedulerLockRecord(Base):
    __tablename__ = "scheduler_lock"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lock_key: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    job_id: Mapped[str] = mapped_column(String(128), index=True)
    owner_id: Mapped[str] = mapped_column(String(128))
    acquired_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)

