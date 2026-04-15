from __future__ import annotations

from libs.adapters.base import ProviderAdapter
from libs.adapters.contracts import AdapterImplementationStatus
from libs.adapters.reconnect import ReconnectManager, ReconnectPolicy
from libs.domain.contracts import CapabilityRegistry, HealthStatus, SourceHealth
from libs.utils.config import Settings


class BcsAdapter(ProviderAdapter):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        reconnect_manager = ReconnectManager(
            ReconnectPolicy(
                max_retries=10,
                base_delay_seconds=1.0,
                max_delay_seconds=90.0,
                multiplier=2.0,
            )
        )
        configured = self.is_configured()
        health_status = HealthStatus.OK if configured else HealthStatus.DEGRADED
        health_detail = (
            "BCS adapter configured; market-data and limits streams can be initialized from configured URLs."
            if configured
            else "BCS adapter is available but `BCS_API_TOKEN` is not configured."
        )
        usage_notes = [
            "BCS is modeled as stream-first market data plus limits provider.",
            "WebSocket URLs stay config-driven because official docs were temporarily inaccessible during implementation.",
        ]
        if settings.bcs_client_id:
            usage_notes.append("Client id is configured for future account-aware flows.")
        if settings.bcs_symbol_map:
            usage_notes.append("Custom BCS symbol map is configured via `BCS_SYMBOL_MAP_JSON`.")

        super().__init__(
            provider="bcs",
            adapter_kind="broker",
            implementation_status=AdapterImplementationStatus.BASELINE,
            capabilities=CapabilityRegistry(
                historical_bars=False,
                stream_bars=True,
                trades=True,
                order_book=True,
                status=True,
                futures_limits=True,
                sandbox=False,
                auth_type="token",
                known_constraints=[
                    "Historical bars remain delegated to exchange/reference providers in the current slice.",
                    "Exact transport paths are configurable because official BCS docs were not fetchable from this environment.",
                ],
            ),
            health=SourceHealth(
                provider="bcs",
                role="secondary_market_data",
                status=health_status,
                detail=health_detail,
                freshness_seconds=12 if configured else None,
                primary=False,
            ),
            transports=["websocket"],
            primary_use_cases=["secondary market data", "order book", "futures limits", "shadow comparison"],
            usage_notes=usage_notes,
            graceful_degradation="If BCS streams are unavailable, the platform continues on MOEX truth and the remaining configured providers.",
            reconnect_manager=reconnect_manager,
        )

    @property
    def market_data_ws_url(self) -> str:
        return self.settings.bcs_market_data_ws_url

    @property
    def order_book_ws_url(self) -> str:
        return self.settings.bcs_order_book_ws_url

    @property
    def limits_ws_url(self) -> str:
        return self.settings.bcs_limits_ws_url

    def is_configured(self) -> bool:
        return bool(self.settings.bcs_api_token)

    def auth_headers(self) -> dict[str, str]:
        if not self.settings.bcs_api_token:
            return {}
        return {"Authorization": f"Bearer {self.settings.bcs_api_token}"}

    def resolve_symbol(self, root_or_contract: str) -> str | None:
        normalized = root_or_contract.strip()
        mapping = self.settings.bcs_symbol_map
        if normalized in mapping:
            return mapping[normalized]
        upper = normalized.upper()
        if upper in mapping:
            return mapping[upper]
        return None
