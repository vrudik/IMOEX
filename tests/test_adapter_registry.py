from __future__ import annotations

from datetime import UTC, date, datetime

from libs.adapters.alor import AlorAdapter
from libs.adapters.bcs import BcsAdapter
from libs.adapters.finam import FinamAdapter
from libs.adapters.registry import get_adapter_registry
from libs.adapters.tbank import TBankAdapter
from libs.utils.config import Settings


def test_adapter_registry_exposes_capabilities_and_source_registry() -> None:
    registry = get_adapter_registry()

    providers = registry.list_providers()
    capabilities = registry.list_capabilities()
    entries = registry.list_source_registry()

    assert "moex" in providers
    assert "tbank" in providers
    assert "finam" in capabilities
    assert capabilities["moex"].historical_bars is True
    assert capabilities["tbank"].sandbox is True
    assert any(item.provider == "cbr" for item in entries)


def test_finam_reconnect_manager_surfaces_degraded_health() -> None:
    registry = get_adapter_registry()

    finam = registry.get("finam")
    assert finam is not None
    health = finam.source_health()

    assert health.status.value == "degraded"
    assert "FINAM_SECRET_TOKEN" in health.detail


def test_adapter_normalization_helpers_build_internal_contracts() -> None:
    registry = get_adapter_registry()
    moex = registry.get("moex")
    assert moex is not None

    bar = moex.normalize_bar(
        root="Si",
        contract="SiM6",
        timeframe="1m",
        open=100.0,
        high=101.0,
        low=99.5,
        close=100.5,
        volume=2500,
        start_at=datetime(2026, 4, 7, 7, 0, tzinfo=UTC),
        end_at=datetime(2026, 4, 7, 7, 1, tzinfo=UTC),
    )
    contract_meta = moex.normalize_contract_meta(
        contract_code="SiM6",
        root_code="Si",
        expiry_date=date(2026, 6, 18),
        last_trade_date=date(2026, 6, 16),
        tick_size=1.0,
        lot_size=1,
        currency="RUB",
    )

    assert bar.provider == "moex"
    assert bar.contract == "SiM6"
    assert contract_meta.provider == "moex"
    assert contract_meta.root_code == "Si"


def test_tbank_adapter_uses_settings_for_mode_headers_and_symbol_resolution() -> None:
    adapter = TBankAdapter(
        Settings(
            tbank_token="secret-token",
            tbank_account_id="account-1",
            tbank_use_sandbox=True,
            tbank_app_name="imoex-test",
            tbank_symbol_map_json='{"Si":"UID-SI","SiM6":"UID-SIM6"}',
        )
    )

    assert adapter.is_configured() is True
    assert adapter.mode == "sandbox"
    assert adapter.grpc_target == "sandbox-invest-public-api.tinkoff.ru:443"
    assert adapter.auth_headers()["Authorization"] == "Bearer secret-token"
    assert adapter.auth_headers()["x-app-name"] == "imoex-test"
    assert adapter.resolve_symbol("Si") == "UID-SI"
    assert adapter.resolve_symbol("SiM6") == "UID-SIM6"
    assert adapter.source_health().status.value == "ok"


def test_tbank_adapter_reports_degraded_when_token_is_missing() -> None:
    adapter = TBankAdapter(Settings(tbank_use_sandbox=False))

    assert adapter.is_configured() is False
    assert adapter.mode == "live"
    assert adapter.grpc_target == "invest-public-api.tinkoff.ru:443"
    assert adapter.auth_headers() == {}
    assert adapter.source_health().status.value == "degraded"
    assert "TBANK_TOKEN" in adapter.source_health().detail


def test_alor_adapter_uses_test_env_refresh_flow_and_symbol_resolution() -> None:
    adapter = AlorAdapter(
        Settings(
            alor_refresh_token="refresh-token",
            alor_portfolio="D39004",
            alor_use_test_env=True,
            alor_symbol_map_json='{"Si":"Si-6.26","BR":"BR-6.26"}',
        )
    )

    assert adapter.is_configured() is True
    assert adapter.mode == "test"
    assert adapter.api_base_url == "https://apidev.alor.ru"
    assert adapter.oauth_base_url == "https://oauthdev.alor.ru"
    assert adapter.market_data_ws_url == "https://apidev.alor.ru/ws"
    assert adapter.command_ws_url == "https://apidev.alor.ru/cws"
    assert adapter.refresh_token_endpoint == "https://oauthdev.alor.ru/refresh"
    assert adapter.refresh_request_payload() == {"token": "refresh-token"}
    assert adapter.resolve_symbol("BR") == "BR-6.26"
    assert adapter.source_health().status.value == "ok"


def test_alor_adapter_prefers_access_token_in_prod_mode() -> None:
    adapter = AlorAdapter(
        Settings(
            alor_access_token="access-token",
            alor_use_test_env=False,
        )
    )

    assert adapter.is_configured() is True
    assert adapter.mode == "prod"
    assert adapter.api_base_url == "https://api.alor.ru"
    assert adapter.oauth_base_url == "https://oauth.alor.ru"
    assert adapter.auth_headers() == {"Authorization": "Bearer access-token"}
    assert adapter.refresh_request_payload() is None


def test_alor_adapter_reports_degraded_when_credentials_are_missing() -> None:
    adapter = AlorAdapter(Settings(alor_use_test_env=False))

    assert adapter.is_configured() is False
    assert adapter.source_health().status.value == "degraded"
    assert "ALOR_REFRESH_TOKEN" in adapter.source_health().detail


def test_finam_adapter_uses_secret_or_jwt_and_exposes_stream_constraints() -> None:
    adapter = FinamAdapter(
        Settings(
            finam_secret_token="secret-token",
            finam_account_id="client-1",
            finam_use_demo=True,
            finam_symbol_map_json='{"Si":"SiM6@FUT","BR":"BRK6@FUT"}',
        )
    )

    assert adapter.is_configured() is True
    assert adapter.mode == "demo"
    assert adapter.rest_base_url == "https://trade-api.finam.ru"
    assert adapter.grpc_target == "trade-api.finam.ru:443"
    assert adapter.websocket_url == "wss://trade-api.finam.ru"
    assert adapter.auth_headers() == {"X-Api-Key": "secret-token"}
    assert adapter.jwt_bootstrap_payload() == {"secretKey": "secret-token"}
    assert adapter.maintenance_window_msk() == ("05:00", "06:15")
    assert adapter.expected_stream_lifetime_seconds() == 86400
    assert adapter.resolve_symbol("Si") == "SiM6@FUT"
    assert adapter.source_health().status.value == "ok"


def test_finam_adapter_prefers_jwt_when_present() -> None:
    adapter = FinamAdapter(
        Settings(
            finam_secret_token="secret-token",
            finam_jwt_token="jwt-token",
        )
    )

    assert adapter.auth_headers() == {"X-Api-Key": "jwt-token"}


def test_finam_adapter_reports_degraded_when_credentials_are_missing() -> None:
    adapter = FinamAdapter(Settings())

    assert adapter.is_configured() is False
    assert adapter.source_health().status.value == "degraded"
    assert "FINAM_SECRET_TOKEN" in adapter.source_health().detail


def test_bcs_adapter_uses_configured_urls_and_token_auth() -> None:
    adapter = BcsAdapter(
        Settings(
            bcs_api_token="bcs-token",
            bcs_client_id="client-42",
            bcs_market_data_ws_url="wss://example.test/market-data",
            bcs_order_book_ws_url="wss://example.test/order-book",
            bcs_limits_ws_url="wss://example.test/limits",
            bcs_symbol_map_json='{"Si":"SiM6","BR":"BRK6"}',
        )
    )

    assert adapter.is_configured() is True
    assert adapter.market_data_ws_url == "wss://example.test/market-data"
    assert adapter.order_book_ws_url == "wss://example.test/order-book"
    assert adapter.limits_ws_url == "wss://example.test/limits"
    assert adapter.auth_headers() == {"Authorization": "Bearer bcs-token"}
    assert adapter.resolve_symbol("BR") == "BRK6"
    assert adapter.source_health().status.value == "ok"


def test_bcs_adapter_reports_degraded_when_token_is_missing() -> None:
    adapter = BcsAdapter(Settings())

    assert adapter.is_configured() is False
    assert adapter.auth_headers() == {}
    assert adapter.source_health().status.value == "degraded"
    assert "BCS_API_TOKEN" in adapter.source_health().detail
