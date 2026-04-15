from __future__ import annotations

from libs.adapters.base import ProviderAdapter
from libs.adapters.contracts import AdapterImplementationStatus
from libs.adapters.reconnect import ReconnectManager, ReconnectPolicy
from libs.domain.contracts import CapabilityRegistry, HealthStatus, SourceHealth
from libs.utils.config import Settings


class FinamAdapter(ProviderAdapter):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        reconnect_manager = ReconnectManager(
            ReconnectPolicy(
                max_retries=12,
                base_delay_seconds=1.0,
                max_delay_seconds=120.0,
                multiplier=2.0,
            )
        )
        configured = self.is_configured()
        mode = self.mode
        health_status = HealthStatus.OK if configured else HealthStatus.DEGRADED
        health_detail = (
            f"Finam adapter configured for {mode} mode; secret/JWT credentials detected."
            if configured
            else "Finam adapter is available but `FINAM_SECRET_TOKEN` or `FINAM_JWT_TOKEN` is not configured."
        )
        usage_notes = [
            f"Current mode: {mode}.",
            "Finam streams require reconnect management because asynchronous sessions have a bounded lifetime.",
            "Maintenance windows should be expected around the broker morning restart window before MOEX main activity.",
        ]
        if settings.finam_account_id:
            usage_notes.append("Client/account id is configured for future account-aware flows.")
        if settings.finam_symbol_map:
            usage_notes.append("Custom Finam symbol map is configured via `FINAM_SYMBOL_MAP_JSON`.")

        super().__init__(
            provider="finam",
            adapter_kind="broker",
            implementation_status=AdapterImplementationStatus.BASELINE,
            capabilities=CapabilityRegistry(
                historical_bars=True,
                stream_bars=True,
                trades=True,
                order_book=True,
                status=True,
                futures_limits=False,
                sandbox=bool(settings.finam_use_demo),
                auth_type="api_key_or_jwt",
                known_constraints=[
                    "Async API sessions are bounded in time and need reconnect handling.",
                    "Exact symbol routing should be pinned via symbol map before promotion to primary provider.",
                ],
            ),
            health=SourceHealth(
                provider="finam",
                role="shadow_market_data",
                status=health_status,
                detail=health_detail,
                freshness_seconds=38 if configured else None,
                primary=False,
            ),
            transports=["rest", "grpc", "websocket"],
            primary_use_cases=["shadow comparison", "secondary bars", "secondary stream data"],
            usage_notes=usage_notes,
            graceful_degradation="If Finam streams flap, the platform keeps MOEX reference truth and other configured providers online.",
            reconnect_manager=reconnect_manager,
        )

    @property
    def mode(self) -> str:
        return "demo" if self.settings.finam_use_demo else "live"

    @property
    def rest_base_url(self) -> str:
        return "https://trade-api.finam.ru"

    @property
    def grpc_target(self) -> str:
        return "trade-api.finam.ru:443"

    @property
    def websocket_url(self) -> str:
        return "wss://trade-api.finam.ru"

    @property
    def auth_endpoint(self) -> str:
        return f"{self.rest_base_url}/api/v1/access-tokens/check"

    def is_configured(self) -> bool:
        return bool(self.settings.finam_secret_token or self.settings.finam_jwt_token)

    def auth_headers(self) -> dict[str, str]:
        if self.settings.finam_jwt_token:
            return {"X-Api-Key": self.settings.finam_jwt_token}
        if self.settings.finam_secret_token:
            return {"X-Api-Key": self.settings.finam_secret_token}
        return {}

    def jwt_bootstrap_payload(self) -> dict[str, str] | None:
        if not self.settings.finam_secret_token:
            return None
        return {"secretKey": self.settings.finam_secret_token}

    def maintenance_window_msk(self) -> tuple[str, str]:
        return ("05:00", "06:15")

    def expected_stream_lifetime_seconds(self) -> int:
        return 86400

    def resolve_symbol(self, root_or_contract: str) -> str | None:
        normalized = root_or_contract.strip()
        mapping = self.settings.finam_symbol_map
        if normalized in mapping:
            return mapping[normalized]
        upper = normalized.upper()
        if upper in mapping:
            return mapping[upper]
        return None
