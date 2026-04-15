"""bootstrap current schema

Revision ID: 20260407_01
Revises:
Create Date: 2026-04-07 21:30:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260407_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "source_quality_check",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("provider_a", sa.String(length=32), nullable=False),
        sa.Column("provider_b", sa.String(length=32), nullable=False),
        sa.Column("contract", sa.String(length=64), nullable=False),
        sa.Column("from_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("till_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("count_a", sa.Integer(), nullable=False),
        sa.Column("count_b", sa.Integer(), nullable=False),
        sa.Column("overlap_count", sa.Integer(), nullable=False),
        sa.Column("missing_in_a", sa.Integer(), nullable=False),
        sa.Column("missing_in_b", sa.Integer(), nullable=False),
        sa.Column("mismatch_ohlc", sa.Integer(), nullable=False),
        sa.Column("mismatch_volume", sa.Integer(), nullable=False),
        sa.Column("mismatch_rate_overlap", sa.Numeric(18, 10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_source_quality_check_provider_a", "source_quality_check", ["provider_a"], unique=False)
    op.create_index("ix_source_quality_check_provider_b", "source_quality_check", ["provider_b"], unique=False)
    op.create_index("ix_source_quality_check_contract", "source_quality_check", ["contract"], unique=False)
    op.create_index("ix_source_quality_check_created_at", "source_quality_check", ["created_at"], unique=False)

    op.create_table(
        "root_series",
        sa.Column("root_code", sa.String(length=32), nullable=False),
        sa.Column("asset_class", sa.String(length=32), nullable=False),
        sa.Column("base_asset", sa.String(length=128), nullable=False),
        sa.Column("active_contract", sa.String(length=64), nullable=False),
        sa.Column("next_contract", sa.String(length=64), nullable=False),
        sa.Column("active_flag", sa.Boolean(), nullable=False),
        sa.Column("liquidity_rank", sa.Integer(), nullable=False),
        sa.Column("liquidity_score", sa.Numeric(18, 10), nullable=False),
        sa.Column("manual_allow", sa.Boolean(), nullable=False),
        sa.Column("manual_deny", sa.Boolean(), nullable=False),
        sa.Column("lock_selected", sa.Boolean(), nullable=False),
        sa.Column("primary_provider", sa.String(length=32), nullable=False),
        sa.Column("secondary_provider", sa.String(length=32), nullable=True),
        sa.Column("session_rule_set", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("root_code"),
    )
    op.create_index("ix_root_series_asset_class", "root_series", ["asset_class"], unique=False)
    op.create_index("ix_root_series_liquidity_rank", "root_series", ["liquidity_rank"], unique=False)
    op.create_index("ix_root_series_created_at", "root_series", ["created_at"], unique=False)

    op.create_table(
        "contract_meta",
        sa.Column("contract_code", sa.String(length=64), nullable=False),
        sa.Column("root_code", sa.String(length=32), nullable=False),
        sa.Column("expiry_date", sa.Date(), nullable=False),
        sa.Column("last_trade_date", sa.Date(), nullable=False),
        sa.Column("tick_size", sa.Numeric(18, 6), nullable=False),
        sa.Column("lot_size", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=16), nullable=False),
        sa.Column("active_flag", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("contract_code"),
    )
    op.create_index("ix_contract_meta_root_code", "contract_meta", ["root_code"], unique=False)
    op.create_index("ix_contract_meta_created_at", "contract_meta", ["created_at"], unique=False)

    op.create_table(
        "trading_session",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("root_code", sa.String(length=32), nullable=False),
        sa.Column("trading_day", sa.Date(), nullable=False),
        sa.Column("session_type", sa.String(length=32), nullable=False),
        sa.Column("session_start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("session_end_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_weekend_linked", sa.Boolean(), nullable=False),
        sa.Column("is_clearing_window", sa.Boolean(), nullable=False),
        sa.Column("effective_rule_set", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trading_session_root_code", "trading_session", ["root_code"], unique=False)
    op.create_index("ix_trading_session_trading_day", "trading_session", ["trading_day"], unique=False)
    op.create_index("ix_trading_session_created_at", "trading_session", ["created_at"], unique=False)

    op.create_table(
        "feature_snapshot",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("snapshot_id", sa.String(length=128), nullable=False),
        sa.Column("root_code", sa.String(length=32), nullable=False),
        sa.Column("contract_code", sa.String(length=64), nullable=False),
        sa.Column("horizon", sa.String(length=16), nullable=False),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=False),
        sa.Column("feature_version", sa.String(length=32), nullable=False),
        sa.Column("point_in_time_correct", sa.Boolean(), nullable=False),
        sa.Column("session_of_day", sa.String(length=32), nullable=False),
        sa.Column("proximity_to_clearing_minutes", sa.Integer(), nullable=True),
        sa.Column("weekend_linked", sa.Boolean(), nullable=False),
        sa.Column("days_to_expiry", sa.Integer(), nullable=False),
        sa.Column("days_to_last_trade", sa.Integer(), nullable=False),
        sa.Column("roll_state", sa.String(length=32), nullable=False),
        sa.Column("roll_risk_flag", sa.Boolean(), nullable=False),
        sa.Column("next_contract_share", sa.Numeric(10, 6), nullable=False),
        sa.Column("return_score", sa.Numeric(18, 10), nullable=False),
        sa.Column("realized_volatility", sa.Numeric(18, 10), nullable=False),
        sa.Column("atr_ratio", sa.Numeric(18, 10), nullable=False),
        sa.Column("trend_slope", sa.Numeric(18, 10), nullable=False),
        sa.Column("vwap_distance_bps", sa.Numeric(18, 10), nullable=False),
        sa.Column("breakout_state", sa.String(length=32), nullable=False),
        sa.Column("overnight_gap_regime", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_feature_snapshot_snapshot_id", "feature_snapshot", ["snapshot_id"], unique=True)
    op.create_index("ix_feature_snapshot_root_code", "feature_snapshot", ["root_code"], unique=False)
    op.create_index("ix_feature_snapshot_contract_code", "feature_snapshot", ["contract_code"], unique=False)
    op.create_index("ix_feature_snapshot_horizon", "feature_snapshot", ["horizon"], unique=False)
    op.create_index("ix_feature_snapshot_as_of", "feature_snapshot", ["as_of"], unique=False)
    op.create_index("ix_feature_snapshot_created_at", "feature_snapshot", ["created_at"], unique=False)

    op.create_table(
        "analyst_output",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("output_id", sa.String(length=128), nullable=False),
        sa.Column("root_code", sa.String(length=32), nullable=False),
        sa.Column("contract_code", sa.String(length=64), nullable=False),
        sa.Column("horizon", sa.String(length=16), nullable=False),
        sa.Column("analyst", sa.String(length=32), nullable=False),
        sa.Column("direction", sa.String(length=32), nullable=False),
        sa.Column("probability", sa.Numeric(18, 10), nullable=False),
        sa.Column("confidence", sa.Numeric(18, 10), nullable=False),
        sa.Column("freshness_score", sa.Numeric(18, 10), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("drivers_blob", sa.String(length=2048), nullable=False),
        sa.Column("objections_blob", sa.String(length=2048), nullable=False),
        sa.Column("invalidation_conditions_blob", sa.String(length=2048), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_analyst_output_output_id", "analyst_output", ["output_id"], unique=True)
    op.create_index("ix_analyst_output_root_code", "analyst_output", ["root_code"], unique=False)
    op.create_index("ix_analyst_output_contract_code", "analyst_output", ["contract_code"], unique=False)
    op.create_index("ix_analyst_output_horizon", "analyst_output", ["horizon"], unique=False)
    op.create_index("ix_analyst_output_analyst", "analyst_output", ["analyst"], unique=False)
    op.create_index("ix_analyst_output_generated_at", "analyst_output", ["generated_at"], unique=False)
    op.create_index("ix_analyst_output_created_at", "analyst_output", ["created_at"], unique=False)

    op.create_table(
        "skeptic_review",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("review_id", sa.String(length=128), nullable=False),
        sa.Column("root_code", sa.String(length=32), nullable=False),
        sa.Column("contract_code", sa.String(length=64), nullable=False),
        sa.Column("horizon", sa.String(length=16), nullable=False),
        sa.Column("skeptic_score", sa.Numeric(18, 10), nullable=False),
        sa.Column("verdict", sa.String(length=32), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("main_objections_blob", sa.String(length=2048), nullable=False),
        sa.Column("data_quality_flags_blob", sa.String(length=2048), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_skeptic_review_review_id", "skeptic_review", ["review_id"], unique=True)
    op.create_index("ix_skeptic_review_root_code", "skeptic_review", ["root_code"], unique=False)
    op.create_index("ix_skeptic_review_contract_code", "skeptic_review", ["contract_code"], unique=False)
    op.create_index("ix_skeptic_review_horizon", "skeptic_review", ["horizon"], unique=False)
    op.create_index("ix_skeptic_review_verdict", "skeptic_review", ["verdict"], unique=False)
    op.create_index("ix_skeptic_review_generated_at", "skeptic_review", ["generated_at"], unique=False)
    op.create_index("ix_skeptic_review_created_at", "skeptic_review", ["created_at"], unique=False)

    op.create_table(
        "signal_version",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("signal_id", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("root_code", sa.String(length=32), nullable=False),
        sa.Column("contract_code", sa.String(length=64), nullable=False),
        sa.Column("horizon", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("direction_final", sa.String(length=32), nullable=False),
        sa.Column("probability_up", sa.Numeric(18, 10), nullable=False),
        sa.Column("probability_down", sa.Numeric(18, 10), nullable=False),
        sa.Column("probability_no_edge", sa.Numeric(18, 10), nullable=False),
        sa.Column("confidence_final", sa.Numeric(18, 10), nullable=False),
        sa.Column("priority_score", sa.Integer(), nullable=False),
        sa.Column("skeptic_score", sa.Numeric(18, 10), nullable=False),
        sa.Column("skeptic_verdict", sa.String(length=32), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("summary", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_signal_version_signal_id", "signal_version", ["signal_id"], unique=False)
    op.create_index("ix_signal_version_version", "signal_version", ["version"], unique=False)
    op.create_index("ix_signal_version_root_code", "signal_version", ["root_code"], unique=False)
    op.create_index("ix_signal_version_contract_code", "signal_version", ["contract_code"], unique=False)
    op.create_index("ix_signal_version_horizon", "signal_version", ["horizon"], unique=False)
    op.create_index("ix_signal_version_status", "signal_version", ["status"], unique=False)
    op.create_index("ix_signal_version_generated_at", "signal_version", ["generated_at"], unique=False)
    op.create_index("ix_signal_version_created_at", "signal_version", ["created_at"], unique=False)

    op.create_table(
        "final_signal",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("signal_id", sa.String(length=128), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("root_code", sa.String(length=32), nullable=False),
        sa.Column("contract_code", sa.String(length=64), nullable=False),
        sa.Column("horizon", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("direction_final", sa.String(length=32), nullable=False),
        sa.Column("probability_up", sa.Numeric(18, 10), nullable=False),
        sa.Column("probability_down", sa.Numeric(18, 10), nullable=False),
        sa.Column("probability_no_edge", sa.Numeric(18, 10), nullable=False),
        sa.Column("confidence_final", sa.Numeric(18, 10), nullable=False),
        sa.Column("priority_score", sa.Integer(), nullable=False),
        sa.Column("roll_risk", sa.Numeric(18, 10), nullable=False),
        sa.Column("expiry_risk", sa.Numeric(18, 10), nullable=False),
        sa.Column("skeptic_score", sa.Numeric(18, 10), nullable=False),
        sa.Column("skeptic_verdict", sa.String(length=32), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("freshness_score", sa.Numeric(18, 10), nullable=False),
        sa.Column("summary", sa.String(length=512), nullable=False),
        sa.Column("drivers_blob", sa.String(length=2048), nullable=False),
        sa.Column("objections_blob", sa.String(length=2048), nullable=False),
        sa.Column("invalidation_conditions_blob", sa.String(length=2048), nullable=False),
        sa.Column("data_sources_blob", sa.String(length=512), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_final_signal_signal_id", "final_signal", ["signal_id"], unique=True)
    op.create_index("ix_final_signal_root_code", "final_signal", ["root_code"], unique=False)
    op.create_index("ix_final_signal_contract_code", "final_signal", ["contract_code"], unique=False)
    op.create_index("ix_final_signal_horizon", "final_signal", ["horizon"], unique=False)
    op.create_index("ix_final_signal_status", "final_signal", ["status"], unique=False)
    op.create_index("ix_final_signal_generated_at", "final_signal", ["generated_at"], unique=False)
    op.create_index("ix_final_signal_created_at", "final_signal", ["created_at"], unique=False)

    op.create_table(
        "signal_resolution",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("resolution_id", sa.String(length=128), nullable=False),
        sa.Column("signal_id", sa.String(length=128), nullable=False),
        sa.Column("root_code", sa.String(length=32), nullable=False),
        sa.Column("contract_code", sa.String(length=64), nullable=False),
        sa.Column("horizon", sa.String(length=16), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("outcome", sa.String(length=32), nullable=False),
        sa.Column("realized_return_bps", sa.Numeric(18, 10), nullable=False),
        sa.Column("realized_hit", sa.Boolean(), nullable=False),
        sa.Column("resolution_note", sa.String(length=1024), nullable=False),
        sa.Column("post_mortem_summary", sa.String(length=2048), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_signal_resolution_resolution_id", "signal_resolution", ["resolution_id"], unique=True)
    op.create_index("ix_signal_resolution_signal_id", "signal_resolution", ["signal_id"], unique=False)
    op.create_index("ix_signal_resolution_root_code", "signal_resolution", ["root_code"], unique=False)
    op.create_index("ix_signal_resolution_contract_code", "signal_resolution", ["contract_code"], unique=False)
    op.create_index("ix_signal_resolution_horizon", "signal_resolution", ["horizon"], unique=False)
    op.create_index("ix_signal_resolution_resolved_at", "signal_resolution", ["resolved_at"], unique=False)
    op.create_index("ix_signal_resolution_status", "signal_resolution", ["status"], unique=False)
    op.create_index("ix_signal_resolution_outcome", "signal_resolution", ["outcome"], unique=False)
    op.create_index("ix_signal_resolution_created_at", "signal_resolution", ["created_at"], unique=False)

    op.create_table(
        "user_journal_entry",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("entry_id", sa.String(length=128), nullable=False),
        sa.Column("signal_id", sa.String(length=128), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("note", sa.String(length=4096), nullable=False),
        sa.Column("author", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_journal_entry_entry_id", "user_journal_entry", ["entry_id"], unique=True)
    op.create_index("ix_user_journal_entry_signal_id", "user_journal_entry", ["signal_id"], unique=False)
    op.create_index("ix_user_journal_entry_kind", "user_journal_entry", ["kind"], unique=False)
    op.create_index("ix_user_journal_entry_created_at", "user_journal_entry", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_user_journal_entry_created_at", table_name="user_journal_entry")
    op.drop_index("ix_user_journal_entry_kind", table_name="user_journal_entry")
    op.drop_index("ix_user_journal_entry_signal_id", table_name="user_journal_entry")
    op.drop_index("ix_user_journal_entry_entry_id", table_name="user_journal_entry")
    op.drop_table("user_journal_entry")

    op.drop_index("ix_signal_resolution_created_at", table_name="signal_resolution")
    op.drop_index("ix_signal_resolution_outcome", table_name="signal_resolution")
    op.drop_index("ix_signal_resolution_status", table_name="signal_resolution")
    op.drop_index("ix_signal_resolution_resolved_at", table_name="signal_resolution")
    op.drop_index("ix_signal_resolution_horizon", table_name="signal_resolution")
    op.drop_index("ix_signal_resolution_contract_code", table_name="signal_resolution")
    op.drop_index("ix_signal_resolution_root_code", table_name="signal_resolution")
    op.drop_index("ix_signal_resolution_signal_id", table_name="signal_resolution")
    op.drop_index("ix_signal_resolution_resolution_id", table_name="signal_resolution")
    op.drop_table("signal_resolution")

    op.drop_index("ix_final_signal_created_at", table_name="final_signal")
    op.drop_index("ix_final_signal_generated_at", table_name="final_signal")
    op.drop_index("ix_final_signal_status", table_name="final_signal")
    op.drop_index("ix_final_signal_horizon", table_name="final_signal")
    op.drop_index("ix_final_signal_contract_code", table_name="final_signal")
    op.drop_index("ix_final_signal_root_code", table_name="final_signal")
    op.drop_index("ix_final_signal_signal_id", table_name="final_signal")
    op.drop_table("final_signal")

    op.drop_index("ix_signal_version_created_at", table_name="signal_version")
    op.drop_index("ix_signal_version_generated_at", table_name="signal_version")
    op.drop_index("ix_signal_version_status", table_name="signal_version")
    op.drop_index("ix_signal_version_horizon", table_name="signal_version")
    op.drop_index("ix_signal_version_contract_code", table_name="signal_version")
    op.drop_index("ix_signal_version_root_code", table_name="signal_version")
    op.drop_index("ix_signal_version_version", table_name="signal_version")
    op.drop_index("ix_signal_version_signal_id", table_name="signal_version")
    op.drop_table("signal_version")

    op.drop_index("ix_skeptic_review_created_at", table_name="skeptic_review")
    op.drop_index("ix_skeptic_review_generated_at", table_name="skeptic_review")
    op.drop_index("ix_skeptic_review_verdict", table_name="skeptic_review")
    op.drop_index("ix_skeptic_review_horizon", table_name="skeptic_review")
    op.drop_index("ix_skeptic_review_contract_code", table_name="skeptic_review")
    op.drop_index("ix_skeptic_review_root_code", table_name="skeptic_review")
    op.drop_index("ix_skeptic_review_review_id", table_name="skeptic_review")
    op.drop_table("skeptic_review")

    op.drop_index("ix_analyst_output_created_at", table_name="analyst_output")
    op.drop_index("ix_analyst_output_generated_at", table_name="analyst_output")
    op.drop_index("ix_analyst_output_analyst", table_name="analyst_output")
    op.drop_index("ix_analyst_output_horizon", table_name="analyst_output")
    op.drop_index("ix_analyst_output_contract_code", table_name="analyst_output")
    op.drop_index("ix_analyst_output_root_code", table_name="analyst_output")
    op.drop_index("ix_analyst_output_output_id", table_name="analyst_output")
    op.drop_table("analyst_output")

    op.drop_index("ix_feature_snapshot_created_at", table_name="feature_snapshot")
    op.drop_index("ix_feature_snapshot_as_of", table_name="feature_snapshot")
    op.drop_index("ix_feature_snapshot_horizon", table_name="feature_snapshot")
    op.drop_index("ix_feature_snapshot_contract_code", table_name="feature_snapshot")
    op.drop_index("ix_feature_snapshot_root_code", table_name="feature_snapshot")
    op.drop_index("ix_feature_snapshot_snapshot_id", table_name="feature_snapshot")
    op.drop_table("feature_snapshot")

    op.drop_index("ix_trading_session_created_at", table_name="trading_session")
    op.drop_index("ix_trading_session_trading_day", table_name="trading_session")
    op.drop_index("ix_trading_session_root_code", table_name="trading_session")
    op.drop_table("trading_session")

    op.drop_index("ix_contract_meta_created_at", table_name="contract_meta")
    op.drop_index("ix_contract_meta_root_code", table_name="contract_meta")
    op.drop_table("contract_meta")

    op.drop_index("ix_root_series_created_at", table_name="root_series")
    op.drop_index("ix_root_series_liquidity_rank", table_name="root_series")
    op.drop_index("ix_root_series_asset_class", table_name="root_series")
    op.drop_table("root_series")

    op.drop_index("ix_source_quality_check_created_at", table_name="source_quality_check")
    op.drop_index("ix_source_quality_check_contract", table_name="source_quality_check")
    op.drop_index("ix_source_quality_check_provider_b", table_name="source_quality_check")
    op.drop_index("ix_source_quality_check_provider_a", table_name="source_quality_check")
    op.drop_table("source_quality_check")
