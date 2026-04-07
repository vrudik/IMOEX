from __future__ import annotations

from datetime import UTC, date, datetime

from libs.continuous.engine import ContinuousSeriesEngine
from libs.domain.models import ContractMetaRecord


def _contract(
    *,
    code: str,
    root: str,
    expiry_date: date,
    last_trade_date: date,
) -> ContractMetaRecord:
    return ContractMetaRecord(
        contract_code=code,
        root_code=root,
        expiry_date=expiry_date,
        last_trade_date=last_trade_date,
        tick_size=1.0,
        lot_size=1,
        currency="RUB",
        active_flag=True,
        created_at=datetime(2026, 4, 6, 9, 0, tzinfo=UTC),
    )


def test_continuous_engine_prefers_front_and_next_contracts() -> None:
    engine = ContinuousSeriesEngine()
    contracts = [
        _contract(code="SiM6", root="Si", expiry_date=date(2026, 6, 20), last_trade_date=date(2026, 6, 18)),
        _contract(code="SiU6", root="Si", expiry_date=date(2026, 9, 20), last_trade_date=date(2026, 9, 18)),
    ]

    snapshot = engine.resolve(
        root_code="Si",
        trading_day=date(2026, 4, 6),
        contracts=contracts,
        preferred_active_contract="SiM6",
        preferred_next_contract="SiU6",
    )

    assert snapshot is not None
    assert snapshot.snapshot.active_contract == "SiM6"
    assert snapshot.snapshot.next_contract == "SiU6"
    assert snapshot.snapshot.days_to_expiry == 75
    assert snapshot.snapshot.days_to_last_trade == 73
    assert snapshot.snapshot.roll_risk_flag is False
    assert snapshot.roll_event is None


def test_continuous_engine_flags_roll_risk_near_last_trade() -> None:
    engine = ContinuousSeriesEngine()
    contracts = [
        _contract(code="BRK6", root="BR", expiry_date=date(2026, 4, 12), last_trade_date=date(2026, 4, 10)),
        _contract(code="BRN6", root="BR", expiry_date=date(2026, 5, 15), last_trade_date=date(2026, 5, 13)),
    ]

    snapshot = engine.resolve(
        root_code="BR",
        trading_day=date(2026, 4, 6),
        contracts=contracts,
        preferred_active_contract="BRK6",
        preferred_next_contract="BRN6",
    )

    assert snapshot is not None
    assert snapshot.snapshot.roll_risk_flag is True
    assert snapshot.snapshot.next_contract_share > 0.05
    assert snapshot.roll_event is not None
    assert snapshot.roll_event.status == "pending"


def test_continuous_engine_falls_back_to_next_eligible_front_when_preferred_expired() -> None:
    engine = ContinuousSeriesEngine()
    contracts = [
        _contract(code="MXH6", root="MXI", expiry_date=date(2026, 3, 20), last_trade_date=date(2026, 3, 18)),
        _contract(code="MXM6", root="MXI", expiry_date=date(2026, 6, 20), last_trade_date=date(2026, 6, 18)),
        _contract(code="MXU6", root="MXI", expiry_date=date(2026, 9, 20), last_trade_date=date(2026, 9, 18)),
    ]

    snapshot = engine.resolve(
        root_code="MXI",
        trading_day=date(2026, 4, 6),
        contracts=contracts,
        preferred_active_contract="MXH6",
        preferred_next_contract="MXU6",
    )

    assert snapshot is not None
    assert snapshot.snapshot.active_contract == "MXM6"
    assert snapshot.snapshot.next_contract == "MXU6"
    assert snapshot.roll_event is not None
    assert snapshot.roll_event.status == "applied"
