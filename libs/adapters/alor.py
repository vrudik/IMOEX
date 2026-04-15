from __future__ import annotations

from libs.adapters.base import ProviderAdapter
from libs.adapters.contracts import AdapterImplementationStatus
from libs.domain.contracts import CapabilityRegistry, HealthStatus, SourceHealth
from libs.utils.config import Settings


class AlorAdapter(ProviderAdapter):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        configured = self.is_configured()
        mode = self.mode
        health_status = HealthStatus.OK if configured else HealthStatus.DEGRADED
        health_detail = (
            f"ALOR adapter configured for {mode} mode; refresh/access credentials detected."
            if configured
            else f"ALOR adapter is available in {mode} mode but `ALOR_REFRESH_TOKEN` or `ALOR_ACCESS_TOKEN` is not configured."
        )
        usage_notes = [
            f"Current mode: {mode}.",
            "Use the test environment first for market-data normalization and symbol-map validation.",
            "Refresh token flow remains the preferred path for API bootstrap before streaming sessions are promoted.",
        ]
        if settings.alor_portfolio:
            usage_notes.append("Portfolio is configured and can be reused for future trading-status and position-aware flows.")
        if settings.alor_symbol_map:
            usage_notes.append("Custom ALOR symbol map is configured via `ALOR_SYMBOL_MAP_JSON`.")

        super().__init__(
            provider="alor",
            adapter_kind="broker",
            implementation_status=AdapterImplementationStatus.BASELINE,
            capabilities=CapabilityRegistry(
                historical_bars=True,
                stream_bars=True,
                trades=True,
                order_book=True,
                status=True,
                futures_limits=False,
                sandbox=bool(settings.alor_use_test_env),
                auth_type="jwt",
                known_constraints=[
                    "Access-token acquisition is config-driven and is not automatically executed during API startup.",
                    "Portfolio binding and exact exchange-board routing still need live integration wiring.",
                ],
            ),
            health=SourceHealth(
                provider="alor",
                role="secondary_market_data",
                status=health_status,
                detail=health_detail,
                freshness_seconds=20 if configured else None,
                primary=False,
            ),
            transports=["http", "websocket", "graphql"],
            primary_use_cases=["secondary market data", "fallback quotes", "eventual order status and portfolio overlays"],
            usage_notes=usage_notes,
            graceful_degradation="If ALOR is unavailable, downstream services continue on MOEX reference truth and other configured providers.",
        )

    @property
    def mode(self) -> str:
        return "test" if self.settings.alor_use_test_env else "prod"

    @property
    def api_base_url(self) -> str:
        if self.settings.alor_use_test_env:
            return "https://apidev.alor.ru"
        return "https://api.alor.ru"

    @property
    def oauth_base_url(self) -> str:
        if self.settings.alor_use_test_env:
            return "https://oauthdev.alor.ru"
        return "https://oauth.alor.ru"

    @property
    def market_data_ws_url(self) -> str:
        return f"{self.api_base_url}/ws"

    @property
    def command_ws_url(self) -> str:
        return f"{self.api_base_url}/cws"

    @property
    def refresh_token_endpoint(self) -> str:
        return f"{self.oauth_base_url}/refresh"

    def is_configured(self) -> bool:
        return bool(self.settings.alor_refresh_token or self.settings.alor_access_token)

    def auth_headers(self) -> dict[str, str]:
        token = self.settings.alor_access_token
        if token:
            return {"Authorization": f"Bearer {token}"}
        return {}

    def refresh_request_payload(self) -> dict[str, str] | None:
        if not self.settings.alor_refresh_token:
            return None
        return {"token": self.settings.alor_refresh_token}

    def resolve_symbol(self, root_or_contract: str) -> str | None:
        normalized = root_or_contract.strip()
        mapping = self.settings.alor_symbol_map
        if normalized in mapping:
            return mapping[normalized]
        upper = normalized.upper()
        if upper in mapping:
            return mapping[upper]
        return None
