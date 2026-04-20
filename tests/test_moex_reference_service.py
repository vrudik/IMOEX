from __future__ import annotations

from datetime import UTC, date, datetime

import httpx

from libs.reference.iss import MoexIssClient
from libs.reference.service import MoexReferenceService


def test_reference_service_maps_weekend_session_to_next_trading_day() -> None:
    service = MoexReferenceService()

    snapshot = service.resolve_calendar_day(date(2026, 4, 4))

    assert snapshot.calendar_day == date(2026, 4, 4)
    assert snapshot.trading_day == date(2026, 4, 6)
    assert snapshot.is_weekend_session is True
    assert snapshot.rule_set.code == "moex-unified-2026-03-23"


def test_reference_service_returns_contract_specs_for_root() -> None:
    service = MoexReferenceService()

    contracts = service.list_contracts_for_root("Si")
    active = service.get_contract("SiM6")
    next_contract = service.get_contract("SiU6")

    assert len(contracts) == 2
    assert active is not None
    assert next_contract is not None
    assert active.root_code == "Si"
    assert active.last_trade_date == date(2026, 6, 18)
    assert active.expiry_date == date(2026, 6, 18)
    assert next_contract.last_trade_date == date(2026, 9, 17)
    assert next_contract.expiry_date == date(2026, 9, 17)


def test_reference_service_returns_correct_brent_contract_dates() -> None:
    service = MoexReferenceService()

    active = service.get_contract("BRK6")
    next_contract = service.get_contract("BRM6")

    assert active is not None
    assert next_contract is not None
    assert active.root_code == "BR"
    assert active.last_trade_date == date(2026, 5, 4)
    assert active.expiry_date == date(2026, 5, 4)
    assert next_contract.last_trade_date == date(2026, 6, 1)
    assert next_contract.expiry_date == date(2026, 6, 1)


def test_reference_service_returns_current_mxi_contract_dates() -> None:
    service = MoexReferenceService()

    active = service.get_contract("MXM6")
    next_contract = service.get_contract("MXU6")

    assert active is not None
    assert next_contract is not None
    assert active.root_code == "MXI"
    assert active.last_trade_date == date(2026, 6, 18)
    assert active.expiry_date == date(2026, 6, 18)
    assert next_contract.last_trade_date == date(2026, 9, 17)
    assert next_contract.expiry_date == date(2026, 9, 17)


def test_moex_iss_client_parses_contracts_and_calendar_payloads() -> None:
    client = MoexIssClient(client=httpx.Client(base_url="https://example.test"))

    contracts = client.parse_contracts(
        {
            "securities": {
                "columns": ["SECID", "ASSETCODE", "LASTTRADEDATE", "MATDATE", "MINSTEP", "LOTSIZE", "FACEUNIT"],
                "data": [
                    ["SiZ6", "Si", "2026-12-16", "2026-12-18", 1.0, 1, "RUB"],
                ],
            }
        }
    )
    calendar = client.parse_calendar(
        {
            "dates": {
                "columns": ["TRADEDATE", "TRADINGDAY", "ISWEEKENDSESSION"],
                "data": [
                    ["2026-04-04", "2026-04-06", 1],
                ],
            }
        }
    )

    assert len(contracts) == 1
    assert contracts[0].contract_code == "SiZ6"
    assert contracts[0].last_trade_date == date(2026, 12, 16)
    assert calendar[date(2026, 4, 4)] == (date(2026, 4, 6), True)


def test_reference_service_sync_from_iss_updates_contracts_and_calendar() -> None:
    class StubIssClient:
        def fetch_contracts_payload(self) -> dict:
            return {
                "securities": {
                    "columns": ["SECID", "ASSETCODE", "LASTTRADEDATE", "MATDATE", "MINSTEP", "LOTSIZE", "FACEUNIT"],
                    "data": [
                        ["SiZ6", "Si", "2026-12-16", "2026-12-18", 1.0, 1, "RUB"],
                    ],
                }
            }

        def fetch_calendar_payload(self, *, from_date=None, to_date=None) -> dict:
            return {
                "dates": {
                    "columns": ["TRADEDATE", "TRADINGDAY", "ISWEEKENDSESSION"],
                    "data": [
                        ["2026-04-04", "2026-04-06", 1],
                    ],
                }
            }

        def parse_contracts(self, payload: dict):
            return MoexIssClient(client=httpx.Client(base_url="https://example.test")).parse_contracts(payload)

        def parse_calendar(self, payload: dict):
            return MoexIssClient(client=httpx.Client(base_url="https://example.test")).parse_calendar(payload)

    service = MoexReferenceService()
    result = service.sync_from_iss(
        client=StubIssClient(),
        from_date=date(2026, 4, 1),
        to_date=date(2026, 4, 7),
    )

    assert result.source == "moex_iss"
    assert result.contracts_synced == 1
    assert result.calendar_days_synced == 1
    assert service.get_contract("SiZ6") is not None
    assert service.resolve_calendar_day(date(2026, 4, 4)).trading_day == date(2026, 4, 6)


def test_reference_service_auto_sync_from_iss_if_due_uses_iss_payloads(monkeypatch) -> None:
    service = MoexReferenceService()
    monkeypatch.setattr("libs.reference.service.settings.moex_reference_auto_sync_enabled", True)
    monkeypatch.setattr("libs.reference.service.settings.moex_reference_auto_sync_interval_hours", 12)
    monkeypatch.setattr("libs.reference.service.settings.moex_reference_retry_cooldown_minutes", 0)
    monkeypatch.setattr("libs.reference.service.settings.moex_reference_calendar_lookback_days", 3)
    monkeypatch.setattr("libs.reference.service.settings.moex_reference_calendar_lookahead_days", 5)

    class StubIssClient:
        def fetch_contracts_payload(self) -> dict:
            return {
                "securities": {
                    "columns": ["SECID", "ASSETCODE", "LASTTRADEDATE", "MATDATE", "MINSTEP", "LOTSIZE", "FACEUNIT"],
                    "data": [
                        ["SiZ6", "Si", "2026-12-17", "2026-12-17", 1.0, 1, "RUB"],
                    ],
                }
            }

        def fetch_calendar_payload(self, *, from_date=None, to_date=None) -> dict:
            assert from_date == date(2026, 4, 13)
            assert to_date == date(2026, 4, 21)
            return {
                "dates": {
                    "columns": ["TRADEDATE", "TRADINGDAY", "ISWEEKENDSESSION"],
                    "data": [
                        ["2026-04-18", "2026-04-20", 1],
                    ],
                }
            }

        def parse_contracts(self, payload: dict):
            return MoexIssClient(client=httpx.Client(base_url="https://example.test")).parse_contracts(payload)

        def parse_calendar(self, payload: dict):
            return MoexIssClient(client=httpx.Client(base_url="https://example.test")).parse_calendar(payload)

    monkeypatch.setattr("libs.reference.service.MoexIssClient", StubIssClient)

    result = service.sync_from_iss_if_due(now=datetime(2026, 4, 16, 7, 0, tzinfo=UTC))

    assert result is not None
    assert result.contracts_synced == 1
    assert any(detail == "auto_sync=true" for detail in result.details)
    assert service.get_contract("SiZ6") is not None
    assert service.resolve_calendar_day(date(2026, 4, 18)).trading_day == date(2026, 4, 20)
