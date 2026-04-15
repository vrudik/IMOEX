from __future__ import annotations

from libs.adapters.base import ProviderAdapter
from libs.adapters.contracts import AdapterImplementationStatus
from libs.domain.contracts import CapabilityRegistry, HealthStatus, SourceHealth
from libs.utils.config import Settings


class TBankAdapter(ProviderAdapter):
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        sandbox_enabled = bool(settings.tbank_use_sandbox)
        configured = self.is_configured()
        mode = self.mode
        health_status = HealthStatus.OK if configured else HealthStatus.DEGRADED
        health_detail = (
            f"T-Bank adapter configured for {mode} mode; credential presence detected."
            if configured
            else f"T-Bank adapter is available in {mode} mode but `TBANK_TOKEN` is not configured."
        )
        usage_notes = [
            f"Current mode: {mode}.",
            "Use sandbox first for contract/instrument mapping validation before enabling live mode.",
        ]
        if settings.tbank_account_id:
            usage_notes.append("Account id is configured and can be reused for future limits/account-aware flows.")
        if settings.tbank_symbol_map:
            usage_notes.append("Custom root-to-identifier symbol map is configured via `TBANK_SYMBOL_MAP_JSON`.")

        super().__init__(
            provider="tbank",
            adapter_kind="broker",
            implementation_status=AdapterImplementationStatus.BASELINE,
            capabilities=CapabilityRegistry(
                historical_bars=True,
                stream_bars=True,
                trades=True,
                order_book=True,
                status=True,
                futures_limits=True,
                sandbox=sandbox_enabled,
                auth_type="token",
                known_constraints=[
                    "Connectivity is config-driven and not automatically probed during API startup.",
                    "Instrument identifiers should be pinned via symbol map before live ingestion is enabled.",
                ],
            ),
            health=SourceHealth(
                provider="tbank",
                role="broker_market_data",
                status=health_status,
                detail=health_detail,
                freshness_seconds=None,
                primary=False,
            ),
            transports=["grpc", "websocket"],
            primary_use_cases=["primary broker data", "sandbox validation", "limits-aware workflows"],
            usage_notes=usage_notes,
            graceful_degradation="If T-Bank is unavailable, downstream services keep using MOEX reference truth and optional secondary providers.",
        )

    @property
    def mode(self) -> str:
        return "sandbox" if self.settings.tbank_use_sandbox else "live"

    @property
    def grpc_target(self) -> str:
        if self.settings.tbank_use_sandbox:
            return "sandbox-invest-public-api.tinkoff.ru:443"
        return "invest-public-api.tinkoff.ru:443"

    @property
    def market_data_stream_target(self) -> str:
        return self.grpc_target

    def is_configured(self) -> bool:
        return bool(self.settings.tbank_token)

    def auth_headers(self) -> dict[str, str]:
        if not self.settings.tbank_token:
            return {}
        return {
            "Authorization": f"Bearer {self.settings.tbank_token}",
            "x-app-name": self.settings.tbank_app_name,
        }

    def resolve_symbol(self, root_or_contract: str) -> str | None:
        normalized = root_or_contract.strip()
        mapping = self.settings.tbank_symbol_map
        if normalized in mapping:
            return mapping[normalized]
        upper = normalized.upper()
        if upper in mapping:
            return mapping[upper]
        return None
