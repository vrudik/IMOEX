from __future__ import annotations

from datetime import UTC, datetime

import httpx

from libs.marketdata.service import MarketDataService
from libs.utils.config import Settings


def test_market_data_service_returns_none_when_live_disabled() -> None:
    app_settings = Settings(market_data_live_enabled=False)
    service = MarketDataService(app_settings=app_settings)

    snapshot = service.get_market_snapshot(
        root_code="Si",
        contract="SiM6",
        providers=["moex"],
        unit_hint="RUB",
        now=datetime(2026, 4, 19, 9, 40, tzinfo=UTC),
    )

    assert snapshot is None


def test_market_data_service_parses_moex_quote_and_candles() -> None:
    quote_payload = {
        "marketdata": {
            "columns": [
                "SECID",
                "LAST",
                "PREVSETTLEPRICE",
                "SYSTIME",
                "TRADEDATE",
                "TIME",
            ],
            "data": [
                ["SiM6", 96325.0, 95810.0, "2026-04-19 12:34:56", "2026-04-19", "12:34:56"],
            ],
        },
        "securities": {
            "columns": ["SECID", "FACEUNIT"],
            "data": [["SiM6", "RUB"]],
        },
    }
    daily_payload = {
        "candles": {
            "columns": ["open", "close", "high", "low", "volume", "begin", "end"],
            "data": [
                [95840.0, 95980.0, 96020.0, 95790.0, 1245.0, "2026-04-19 10:00:00", "2026-04-19 10:10:00"],
                [95980.0, 96325.0, 96380.0, 95940.0, 1750.0, "2026-04-19 10:10:00", "2026-04-19 10:20:00"],
            ],
        }
    }
    weekly_payload = {
        "candles": {
            "columns": ["open", "close", "high", "low", "volume", "begin", "end"],
            "data": [
                [94900.0, 95200.0, 95320.0, 94780.0, 8420.0, "2026-04-14 10:00:00", "2026-04-14 23:50:00"],
                [95200.0, 96325.0, 96410.0, 95150.0, 9130.0, "2026-04-18 10:00:00", "2026-04-18 23:50:00"],
            ],
        }
    }
    monthly_payload = {
        "candles": {
            "columns": ["open", "close", "high", "low", "volume", "begin", "end"],
            "data": [
                [93600.0, 94450.0, 94610.0, 93420.0, 15420.0, "2026-03-21 10:00:00", "2026-03-21 23:50:00"],
                [94450.0, 96325.0, 96410.0, 94390.0, 16780.0, "2026-04-18 10:00:00", "2026-04-18 23:50:00"],
            ],
        }
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/engines/futures/markets/forts/securities/SiM6.json"):
            return httpx.Response(200, json=quote_payload)
        if request.url.path.endswith("/engines/futures/markets/forts/securities/SiM6/candles.json"):
            from_value = request.url.params.get("from", "")
            if from_value.startswith("2026-04-19"):
                return httpx.Response(200, json=daily_payload)
            if from_value.startswith("2026-04-11"):
                return httpx.Response(200, json=weekly_payload)
            return httpx.Response(200, json=monthly_payload)
        return httpx.Response(404, json={"detail": "not found"})

    transport = httpx.MockTransport(handler)
    moex_client = httpx.Client(transport=transport, base_url="https://iss.moex.com/iss")
    app_settings = Settings(
        market_data_live_enabled=True,
        market_data_http_timeout_seconds=1.0,
        market_data_cache_ttl_seconds=60,
    )
    service = MarketDataService(app_settings=app_settings, moex_client=moex_client)

    snapshot = service.get_market_snapshot(
        root_code="Si",
        contract="SiM6",
        providers=["moex"],
        unit_hint="RUB",
        now=datetime(2026, 4, 19, 9, 40, tzinfo=UTC),
    )

    assert snapshot is not None
    assert snapshot.provider == "moex"
    assert snapshot.quote.current_price == 96325.0
    assert snapshot.quote.price_change_abs == 515.0
    assert round(snapshot.quote.price_change_pct, 4) == round(515.0 / 95810.0, 4)
    assert snapshot.unit == "RUB"
    assert len(snapshot.daily_bars) == 2
    assert snapshot.daily_bars[-1].close == 96325.0
    assert len(snapshot.weekly_bars) == 2
    assert len(snapshot.monthly_bars) == 2
    assert snapshot.as_of.isoformat() == "2026-04-19T09:34:56+00:00"


def test_market_data_service_circuit_breaks_repeated_provider_failures() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        raise httpx.ConnectTimeout("MOEX is temporarily unavailable.", request=request)

    transport = httpx.MockTransport(handler)
    moex_client = httpx.Client(transport=transport, base_url="https://iss.moex.com/iss")
    app_settings = Settings(
        market_data_live_enabled=True,
        market_data_http_timeout_seconds=1.0,
        market_data_cache_ttl_seconds=60,
    )
    service = MarketDataService(app_settings=app_settings, moex_client=moex_client)
    now = datetime(2026, 4, 19, 9, 40, tzinfo=UTC)

    first = service.get_quote_snapshot(
        root_code="Si",
        contract="SiM6",
        providers=["moex"],
        unit_hint="RUB",
        now=now,
    )
    second = service.get_quote_snapshot(
        root_code="BR",
        contract="BRK6",
        providers=["moex"],
        unit_hint="USD",
        now=now,
    )
    third = service.get_market_snapshot(
        root_code="MXI",
        contract="MXM6",
        providers=["moex"],
        unit_hint="RUB",
        now=now,
    )

    assert first is None
    assert second is None
    assert third is None
    assert calls == 1
