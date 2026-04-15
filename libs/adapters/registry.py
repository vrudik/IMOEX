from __future__ import annotations

from functools import lru_cache

from libs.adapters.alor import AlorAdapter
from libs.adapters.base import ProviderAdapter
from libs.adapters.bcs import BcsAdapter
from libs.adapters.contracts import AdapterImplementationStatus, SourceRegistryEntry
from libs.adapters.finam import FinamAdapter
from libs.adapters.tbank import TBankAdapter
from libs.domain.contracts import CapabilityRegistry, HealthStatus, SourceHealth
from libs.utils.config import settings


class AdapterRegistry:
    def __init__(self, adapters: list[ProviderAdapter]) -> None:
        self._adapters = {adapter.provider: adapter for adapter in adapters}

    def list_providers(self) -> list[str]:
        return sorted(self._adapters)

    def get(self, provider: str) -> ProviderAdapter | None:
        return self._adapters.get(provider)

    def list_capabilities(self) -> dict[str, CapabilityRegistry]:
        return {provider: adapter.capability_registry() for provider, adapter in sorted(self._adapters.items())}

    def capability_registry_for(self, providers: list[str]) -> dict[str, CapabilityRegistry]:
        return {
            provider: self._adapters[provider].capability_registry()
            for provider in _dedupe_preserve_order(providers)
            if provider in self._adapters
        }

    def list_source_health(self) -> list[SourceHealth]:
        return [self._adapters[provider].source_health() for provider in self.list_providers()]

    def source_health_for(self, providers: list[str]) -> list[SourceHealth]:
        return [
            self._adapters[provider].source_health()
            for provider in _dedupe_preserve_order(providers)
            if provider in self._adapters
        ]

    def list_source_registry(self) -> list[SourceRegistryEntry]:
        return [self._adapters[provider].source_registry_entry() for provider in self.list_providers()]


@lru_cache(maxsize=1)
def get_adapter_registry() -> AdapterRegistry:
    adapters = [
        AlorAdapter(settings),
        BcsAdapter(settings),
        ProviderAdapter(
            provider="cbr",
            adapter_kind="macro_calendar",
            implementation_status=AdapterImplementationStatus.BASELINE,
            capabilities=CapabilityRegistry(
                historical_bars=False,
                stream_bars=False,
                trades=False,
                order_book=False,
                status=False,
                futures_limits=False,
                sandbox=False,
                auth_type="public",
                known_constraints=["Business-event calendar only; no market-data surface."],
            ),
            health=SourceHealth(
                provider="cbr",
                role="macro_events",
                status=HealthStatus.OK,
                detail="Key-rate calendar is available as exchange-adjacent business-event source.",
                freshness_seconds=900,
                primary=True,
            ),
            transports=["http"],
            primary_use_cases=["macro events", "calendar overlays", "rate-decision proximity features"],
            usage_notes=["Use CBR only for normalized business events, never as market-data source."],
            graceful_degradation="Macro/event analyst drops confidence but the rest of the signal stack keeps running.",
        ),
        FinamAdapter(settings),
        ProviderAdapter(
            provider="moex",
            adapter_kind="exchange_reference",
            implementation_status=AdapterImplementationStatus.BASELINE,
            capabilities=CapabilityRegistry(
                historical_bars=True,
                stream_bars=False,
                trades=True,
                order_book=True,
                status=True,
                futures_limits=False,
                sandbox=False,
                auth_type="public",
                known_constraints=["Streaming is intentionally modeled as unavailable in the current baseline slice."],
            ),
            health=SourceHealth(
                provider="moex",
                role="exchange_reference",
                status=HealthStatus.OK,
                detail="Reference truth for calendar, contract metadata and baseline bars.",
                freshness_seconds=5,
                primary=True,
            ),
            transports=["http"],
            primary_use_cases=["calendar truth", "contract metadata", "reference bars", "exchange notices"],
            usage_notes=["MOEX remains the source of truth for trading-day semantics and expiry metadata."],
            graceful_degradation="If MOEX is stale, the system keeps cached contract/session state and downgrades confidence.",
        ),
        TBankAdapter(settings),
    ]
    return AdapterRegistry(adapters)


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered
