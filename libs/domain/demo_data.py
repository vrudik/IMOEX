from __future__ import annotations

from datetime import UTC, date, datetime

from libs.adapters.registry import get_adapter_registry
from libs.domain.contracts import (
    AssetClass,
    ContinuousSeriesSnapshot,
    FinalSignalCard,
    FinalSignalDetail,
    HorizonCode,
    RootDeepDive,
    RootSeriesSummary,
    SessionSnapshot,
    SessionType,
    SignalDirection,
    SignalStatus,
    SkepticVerdict,
    SourceHealth,
)

_ROOTS: list[RootSeriesSummary] = [
    RootSeriesSummary(
        root_code="Si",
        asset_class=AssetClass.CURRENCY,
        base_asset="USD/RUB",
        active_contract="SiM6",
        next_contract="SiU6",
        liquidity_rank=1,
        liquidity_score=0.92,
        universe_status="selected",
        manual_override="none",
        selection_reasons=["selected by weekly liquidity ranking"],
        primary_provider="moex",
        secondary_provider="finam",
        session_rule_set="moex-unified-2026-03-23",
    ),
    RootSeriesSummary(
        root_code="BR",
        asset_class=AssetClass.COMMODITY,
        base_asset="Brent Crude",
        active_contract="BRK6",
        next_contract="BRN6",
        liquidity_rank=2,
        liquidity_score=0.84,
        universe_status="selected",
        manual_override="none",
        selection_reasons=["selected by weekly liquidity ranking"],
        primary_provider="moex",
        secondary_provider="bcs",
        session_rule_set="moex-unified-2026-03-23",
    ),
    RootSeriesSummary(
        root_code="MXI",
        asset_class=AssetClass.INDEX,
        base_asset="MOEX Index",
        active_contract="MXM6",
        next_contract="MXU6",
        liquidity_rank=3,
        liquidity_score=0.79,
        universe_status="selected",
        manual_override="none",
        selection_reasons=["selected by weekly liquidity ranking"],
        primary_provider="moex",
        secondary_provider="alor",
        session_rule_set="moex-unified-2026-03-23",
    ),
]

_SIGNALS: list[FinalSignalDetail] = [
    FinalSignalDetail(
        signal_id="SIG-2026-04-06-Si-H3S-000001",
        version=1,
        root="Si",
        contract="SiM6",
        horizon=HorizonCode.H3S,
        status=SignalStatus.ACTIVE,
        direction_final=SignalDirection.BULLISH,
        probability_up=0.64,
        probability_down=0.18,
        probability_no_edge=0.18,
        confidence_final=0.72,
        priority_score=81,
        roll_risk=0.11,
        expiry_risk=0.07,
        skeptic_score=0.88,
        skeptic_verdict=SkepticVerdict.PASS,
        generated_at=datetime(2026, 4, 6, 9, 20, tzinfo=UTC),
        freshness_score=0.94,
        summary="Rule-based momentum remains positive while roll risk is still moderate.",
        drivers=[
            "Price trades above 5-session breakout level.",
            "Open-interest proxy and relative volume remain supportive.",
            "No exchange-status degradation on the active contract.",
        ],
        objections=[
            "Signal enters the near-clearing zone later today.",
            "Strength partly depends on USD/RUB macro flow staying intact.",
        ],
        invalidation_conditions=[
            "Breakout closes back inside prior 3-session range.",
            "Freshness score drops below 0.70 due to source lag.",
        ],
        data_sources=["moex", "finam", "cbr"],
    ),
    FinalSignalDetail(
        signal_id="SIG-2026-04-06-BR-H1S-000001",
        version=1,
        root="BR",
        contract="BRK6",
        horizon=HorizonCode.H1S,
        status=SignalStatus.ACTIVE,
        direction_final=SignalDirection.BEARISH,
        probability_up=0.21,
        probability_down=0.57,
        probability_no_edge=0.22,
        confidence_final=0.61,
        priority_score=68,
        roll_risk=0.16,
        expiry_risk=0.09,
        skeptic_score=0.57,
        skeptic_verdict=SkepticVerdict.SOFT_FAIL,
        generated_at=datetime(2026, 4, 6, 9, 35, tzinfo=UTC),
        freshness_score=0.88,
        summary="Order-flow pressure dominates, but liquidity quality is below champion threshold.",
        drivers=[
            "Sell-side imbalance persists across tape and top-of-book.",
            "Spread regime widened versus rolling median.",
        ],
        objections=[
            "Liquidity is weaker than usual for the morning window.",
            "Signal is penalized by skeptic for degraded shadow coverage.",
        ],
        invalidation_conditions=[
            "Depth normalizes and bearish imbalance mean-reverts.",
        ],
        data_sources=["moex", "bcs"],
    ),
    FinalSignalDetail(
        signal_id="SIG-2026-04-04-MXI-H2W-000001",
        version=2,
        root="MXI",
        contract="MXM6",
        horizon=HorizonCode.H2W,
        status=SignalStatus.RESOLVED,
        direction_final=SignalDirection.NO_EDGE,
        probability_up=0.39,
        probability_down=0.26,
        probability_no_edge=0.35,
        confidence_final=0.58,
        priority_score=51,
        roll_risk=0.08,
        expiry_risk=0.05,
        skeptic_score=0.81,
        skeptic_verdict=SkepticVerdict.PASS,
        generated_at=datetime(2026, 4, 4, 15, 10, tzinfo=UTC),
        freshness_score=0.91,
        summary="Medium-horizon setup remains mixed; the system keeps it as no-edge.",
        drivers=[
            "Trend slope is positive but realized volatility accelerated.",
            "Macro-event proximity keeps conviction capped.",
        ],
        objections=[
            "No strong follow-through from order-flow analyst.",
        ],
        invalidation_conditions=[
            "Not applicable after resolution.",
        ],
        data_sources=["moex", "alor", "cbr"],
    ),
]

_DEEP_DIVES: dict[str, RootDeepDive] = {
    "SI": RootDeepDive(
        root=_ROOTS[0],
        session=SessionSnapshot(
            calendar_day=date(2026, 4, 6),
            trading_day=date(2026, 4, 6),
            session_type=SessionType.MAIN,
            session_start_at=datetime(2026, 4, 6, 6, 50, tzinfo=UTC),
            session_end_at=datetime(2026, 4, 6, 15, 0, tzinfo=UTC),
            is_weekend_linked=False,
            is_clearing_window=False,
            is_near_expiry=False,
            effective_rule_set="moex-unified-2026-03-23",
        ),
        continuous_series=ContinuousSeriesSnapshot(
            active_contract="SiM6",
            next_contract="SiU6",
            days_to_expiry=74,
            days_to_last_trade=72,
            roll_risk_flag=False,
            next_contract_share=0.24,
            roll_state="stable",
            back_adjustment_method="difference_on_roll",
            estimated_roll_date=date(2026, 6, 15),
        ),
        roll_event=None,
        active_signals=[_SIGNALS[0]],
        sources=[],
        capability_registry={},
    ),
    "BR": RootDeepDive(
        root=_ROOTS[1],
        session=SessionSnapshot(
            calendar_day=date(2026, 4, 6),
            trading_day=date(2026, 4, 6),
            session_type=SessionType.MAIN,
            session_start_at=datetime(2026, 4, 6, 6, 50, tzinfo=UTC),
            session_end_at=datetime(2026, 4, 6, 15, 0, tzinfo=UTC),
            is_weekend_linked=False,
            is_clearing_window=False,
            is_near_expiry=False,
            effective_rule_set="moex-unified-2026-03-23",
        ),
        continuous_series=ContinuousSeriesSnapshot(
            active_contract="BRK6",
            next_contract="BRN6",
            days_to_expiry=66,
            days_to_last_trade=64,
            roll_risk_flag=False,
            next_contract_share=0.31,
            roll_state="stable",
            back_adjustment_method="difference_on_roll",
            estimated_roll_date=date(2026, 6, 5),
        ),
        roll_event=None,
        active_signals=[_SIGNALS[1]],
        sources=[],
        capability_registry={},
    ),
    "MXI": RootDeepDive(
        root=_ROOTS[2],
        session=SessionSnapshot(
            calendar_day=date(2026, 4, 6),
            trading_day=date(2026, 4, 6),
            session_type=SessionType.MAIN,
            session_start_at=datetime(2026, 4, 6, 6, 50, tzinfo=UTC),
            session_end_at=datetime(2026, 4, 6, 15, 0, tzinfo=UTC),
            is_weekend_linked=False,
            is_clearing_window=False,
            is_near_expiry=False,
            effective_rule_set="moex-unified-2026-03-23",
        ),
        continuous_series=ContinuousSeriesSnapshot(
            active_contract="MXM6",
            next_contract="MXU6",
            days_to_expiry=74,
            days_to_last_trade=72,
            roll_risk_flag=False,
            next_contract_share=0.18,
            roll_state="stable",
            back_adjustment_method="difference_on_roll",
            estimated_roll_date=date(2026, 6, 15),
        ),
        roll_event=None,
        active_signals=[],
        sources=[],
        capability_registry={},
    ),
}


def list_roots() -> list[RootSeriesSummary]:
    return [item.model_copy(deep=True) for item in _ROOTS]


def get_root_deep_dive(root: str) -> RootDeepDive | None:
    deep_dive = _clone(_DEEP_DIVES.get(root.upper()))
    if deep_dive is None:
        return None
    registry = get_adapter_registry()
    providers = _providers_for_root(deep_dive.root)
    return deep_dive.model_copy(
        update={
            "sources": registry.source_health_for(providers),
            "capability_registry": registry.capability_registry_for(providers),
        },
        deep=True,
    )


def list_signals(
    *,
    root: str | None = None,
    horizon: HorizonCode | None = None,
    status: SignalStatus | None = None,
    limit: int = 50,
) -> list[FinalSignalCard]:
    rows: list[FinalSignalCard] = []
    for signal in _SIGNALS:
        if root and signal.root.upper() != root.upper():
            continue
        if horizon and signal.horizon != horizon:
            continue
        if status and signal.status != status:
            continue
        rows.append(
            FinalSignalCard.model_validate(signal.model_dump())
        )
    return [item.model_copy(deep=True) for item in rows[:limit]]


def get_signal(signal_id: str) -> FinalSignalDetail | None:
    for signal in _SIGNALS:
        if signal.signal_id == signal_id:
            return signal.model_copy(deep=True)
    return None


def list_sources() -> list[SourceHealth]:
    return [item.model_copy(deep=True) for item in get_adapter_registry().list_source_health()]


def _clone(value: RootDeepDive | None) -> RootDeepDive | None:
    if value is None:
        return None
    return value.model_copy(deep=True)


def _providers_for_root(root: RootSeriesSummary) -> list[str]:
    providers = [root.primary_provider]
    if root.secondary_provider:
        providers.append(root.secondary_provider)
    providers.append("cbr")
    return providers
