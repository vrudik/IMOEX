from __future__ import annotations

from datetime import UTC, date, datetime

from libs.domain.models import ContractMetaRecord, RootSeriesRecord
from libs.universe.service import UniverseService


def _root(
    *,
    root_code: str,
    asset_class: str,
    liquidity_rank: int,
    active_contract: str,
    next_contract: str,
    manual_allow: bool = False,
    manual_deny: bool = False,
    lock_selected: bool = False,
) -> RootSeriesRecord:
    return RootSeriesRecord(
        root_code=root_code,
        asset_class=asset_class,
        base_asset=root_code,
        active_contract=active_contract,
        next_contract=next_contract,
        active_flag=True,
        liquidity_rank=liquidity_rank,
        liquidity_score=0,
        manual_allow=manual_allow,
        manual_deny=manual_deny,
        lock_selected=lock_selected,
        primary_provider="moex",
        secondary_provider=None,
        session_rule_set="moex-unified-2026-03-23",
        created_at=datetime(2026, 4, 6, 9, 0, tzinfo=UTC),
    )


def _contract(root: str, code: str, last_trade_date: date, expiry_date: date) -> ContractMetaRecord:
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


def test_universe_service_keeps_one_root_per_asset_class_and_sorts_by_score() -> None:
    service = UniverseService(top_n=3)
    roots = [
        _root(root_code="Si", asset_class="currency", liquidity_rank=1, active_contract="SiM6", next_contract="SiU6"),
        _root(root_code="BR", asset_class="commodity", liquidity_rank=2, active_contract="BRK6", next_contract="BRN6"),
        _root(root_code="MXI", asset_class="index", liquidity_rank=3, active_contract="MXM6", next_contract="MXU6"),
    ]
    contracts_by_root = {
        "Si": [_contract("Si", "SiM6", date(2026, 6, 18), date(2026, 6, 20)), _contract("Si", "SiU6", date(2026, 9, 18), date(2026, 9, 20))],
        "BR": [_contract("BR", "BRK6", date(2026, 5, 10), date(2026, 5, 12)), _contract("BR", "BRN6", date(2026, 8, 13), date(2026, 8, 15))],
        "MXI": [_contract("MXI", "MXM6", date(2026, 6, 18), date(2026, 6, 20)), _contract("MXI", "MXU6", date(2026, 9, 18), date(2026, 9, 20))],
    }

    ranked = service.rank(roots=roots, contracts_by_root=contracts_by_root)

    assert len(ranked) == 3
    assert ranked[0].root.root_code == "Si"
    assert all(item.universe_status.value == "selected" for item in ranked)


def test_universe_service_respects_manual_deny_and_allow() -> None:
    service = UniverseService(top_n=2)
    roots = [
        _root(root_code="Si", asset_class="currency", liquidity_rank=1, active_contract="SiM6", next_contract="SiU6", manual_deny=True),
        _root(root_code="BR", asset_class="commodity", liquidity_rank=3, active_contract="BRK6", next_contract="BRN6", manual_allow=True),
        _root(root_code="MXI", asset_class="index", liquidity_rank=2, active_contract="MXM6", next_contract="MXU6"),
    ]
    contracts_by_root = {
        "Si": [_contract("Si", "SiM6", date(2026, 6, 18), date(2026, 6, 20))],
        "BR": [_contract("BR", "BRK6", date(2026, 5, 10), date(2026, 5, 12)), _contract("BR", "BRN6", date(2026, 8, 13), date(2026, 8, 15))],
        "MXI": [_contract("MXI", "MXM6", date(2026, 6, 18), date(2026, 6, 20)), _contract("MXI", "MXU6", date(2026, 9, 18), date(2026, 9, 20))],
    }

    ranked = {item.root.root_code: item for item in service.rank(roots=roots, contracts_by_root=contracts_by_root)}

    assert ranked["Si"].universe_status.value == "excluded"
    assert ranked["BR"].universe_status.value == "selected"
    assert ranked["BR"].manual_override.value == "allow"
