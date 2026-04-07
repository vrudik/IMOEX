from __future__ import annotations

from datetime import date

from libs.continuous.builder import BackAdjustedSeriesBuilder, ContractClosePoint, RollTransition


def test_back_adjusted_builder_applies_single_roll_gap_to_history() -> None:
    builder = BackAdjustedSeriesBuilder()

    points = [
        ContractClosePoint(trading_day=date(2026, 4, 1), contract_code="SiM6", close=100.0),
        ContractClosePoint(trading_day=date(2026, 4, 2), contract_code="SiM6", close=101.0),
        ContractClosePoint(trading_day=date(2026, 4, 3), contract_code="SiU6", close=110.0),
        ContractClosePoint(trading_day=date(2026, 4, 4), contract_code="SiU6", close=112.0),
    ]
    transitions = [
        RollTransition(from_contract="SiM6", to_contract="SiU6", effective_trading_day=date(2026, 4, 3)),
    ]

    series = builder.build(points=points, transitions=transitions, start_contract="SiM6")

    assert [item.contract_code for item in series] == ["SiM6", "SiM6", "SiU6", "SiU6"]
    assert [item.raw_close for item in series] == [100.0, 101.0, 110.0, 112.0]
    assert [item.adjusted_close for item in series] == [109.0, 110.0, 110.0, 112.0]


def test_back_adjusted_builder_accumulates_multiple_roll_gaps() -> None:
    builder = BackAdjustedSeriesBuilder()

    points = [
        ContractClosePoint(trading_day=date(2026, 3, 30), contract_code="MXH6", close=3000.0),
        ContractClosePoint(trading_day=date(2026, 3, 31), contract_code="MXH6", close=3010.0),
        ContractClosePoint(trading_day=date(2026, 4, 1), contract_code="MXM6", close=3050.0),
        ContractClosePoint(trading_day=date(2026, 4, 2), contract_code="MXM6", close=3065.0),
        ContractClosePoint(trading_day=date(2026, 4, 3), contract_code="MXU6", close=3120.0),
        ContractClosePoint(trading_day=date(2026, 4, 4), contract_code="MXU6", close=3130.0),
    ]
    transitions = [
        RollTransition(from_contract="MXH6", to_contract="MXM6", effective_trading_day=date(2026, 4, 1)),
        RollTransition(from_contract="MXM6", to_contract="MXU6", effective_trading_day=date(2026, 4, 3)),
    ]

    series = builder.build(points=points, transitions=transitions, start_contract="MXH6")

    assert [item.contract_code for item in series] == ["MXH6", "MXH6", "MXM6", "MXM6", "MXU6", "MXU6"]
    assert [item.adjusted_close for item in series] == [3095.0, 3105.0, 3105.0, 3120.0, 3120.0, 3130.0]
    assert [item.cumulative_adjustment for item in series] == [95.0, 95.0, 55.0, 55.0, 0.0, 0.0]


def test_back_adjusted_builder_uses_nearest_available_reference_prices() -> None:
    builder = BackAdjustedSeriesBuilder()

    points = [
        ContractClosePoint(trading_day=date(2026, 4, 1), contract_code="BRK6", close=70.0),
        ContractClosePoint(trading_day=date(2026, 4, 2), contract_code="BRK6", close=72.0),
        ContractClosePoint(trading_day=date(2026, 4, 4), contract_code="BRN6", close=79.0),
    ]
    transitions = [
        RollTransition(from_contract="BRK6", to_contract="BRN6", effective_trading_day=date(2026, 4, 3)),
    ]

    series = builder.build(points=points, transitions=transitions, start_contract="BRK6")

    assert len(series) == 3
    assert [item.adjusted_close for item in series] == [77.0, 79.0, 79.0]
