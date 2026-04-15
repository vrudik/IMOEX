from __future__ import annotations

from datetime import date, datetime

from libs.adapters.contracts import (
    AdapterImplementationStatus,
    Bar,
    BusinessEvent,
    ContractMeta,
    OrderBook,
    OrderBookLevel,
    SourceRegistryEntry,
    Trade,
    TradingStatus,
)
from libs.adapters.reconnect import ReconnectManager
from libs.domain.contracts import CapabilityRegistry, HealthStatus, SourceHealth


class ProviderAdapter:
    def __init__(
        self,
        *,
        provider: str,
        adapter_kind: str,
        implementation_status: AdapterImplementationStatus,
        capabilities: CapabilityRegistry,
        health: SourceHealth,
        transports: list[str],
        primary_use_cases: list[str],
        usage_notes: list[str],
        graceful_degradation: str,
        reconnect_manager: ReconnectManager | None = None,
    ) -> None:
        self.provider = provider
        self.adapter_kind = adapter_kind
        self.implementation_status = implementation_status
        self._capabilities = capabilities
        self._health = health
        self._transports = transports
        self._primary_use_cases = primary_use_cases
        self._usage_notes = usage_notes
        self._graceful_degradation = graceful_degradation
        self._reconnect_manager = reconnect_manager

    def capability_registry(self) -> CapabilityRegistry:
        return self._capabilities.model_copy(deep=True)

    def source_health(self) -> SourceHealth:
        health = self._health.model_copy(deep=True)
        if self._reconnect_manager is None:
            return health

        state = self._reconnect_manager.snapshot()
        if state.status != "ok":
            detail_suffix = state.detail
            if state.next_retry_seconds is not None:
                detail_suffix = f"{detail_suffix}; next_retry_seconds={state.next_retry_seconds:.1f}"
            return health.model_copy(
                update={
                    "status": HealthStatus.DEGRADED,
                    "detail": f"{health.detail} {detail_suffix}".strip(),
                },
                deep=True,
            )
        return health

    def source_registry_entry(self) -> SourceRegistryEntry:
        return SourceRegistryEntry(
            provider=self.provider,
            adapter_kind=self.adapter_kind,
            implementation_status=self.implementation_status,
            auth_type=self._capabilities.auth_type,
            transports=list(self._transports),
            primary_use_cases=list(self._primary_use_cases),
            usage_notes=list(self._usage_notes),
            graceful_degradation=self._graceful_degradation,
            capabilities=self.capability_registry(),
            health=self.source_health(),
        )

    def normalize_bar(
        self,
        *,
        root: str,
        contract: str,
        timeframe: str,
        open: float,
        high: float,
        low: float,
        close: float,
        volume: float,
        start_at: datetime,
        end_at: datetime,
    ) -> Bar:
        return Bar(
            provider=self.provider,
            root=root,
            contract=contract,
            timeframe=timeframe,
            open=open,
            high=high,
            low=low,
            close=close,
            volume=volume,
            start_at=start_at,
            end_at=end_at,
        )

    def normalize_trade(
        self,
        *,
        contract: str,
        trade_id: str,
        price: float,
        quantity: float,
        side: str,
        traded_at: datetime,
    ) -> Trade:
        return Trade(
            provider=self.provider,
            contract=contract,
            trade_id=trade_id,
            price=price,
            quantity=quantity,
            side=side,
            traded_at=traded_at,
        )

    def normalize_order_book(
        self,
        *,
        contract: str,
        as_of: datetime,
        bids: list[tuple[float, float]],
        asks: list[tuple[float, float]],
    ) -> OrderBook:
        return OrderBook(
            provider=self.provider,
            contract=contract,
            as_of=as_of,
            bids=[OrderBookLevel(price=price, quantity=quantity) for price, quantity in bids],
            asks=[OrderBookLevel(price=price, quantity=quantity) for price, quantity in asks],
        )

    def normalize_trading_status(
        self,
        *,
        contract: str,
        status: str,
        detail: str,
        as_of: datetime,
    ) -> TradingStatus:
        return TradingStatus(
            provider=self.provider,
            contract=contract,
            status=status,
            detail=detail,
            as_of=as_of,
        )

    def normalize_contract_meta(
        self,
        *,
        contract_code: str,
        root_code: str,
        expiry_date: date,
        last_trade_date: date,
        tick_size: float,
        lot_size: int,
        currency: str,
    ) -> ContractMeta:
        return ContractMeta(
            provider=self.provider,
            contract_code=contract_code,
            root_code=root_code,
            expiry_date=expiry_date,
            last_trade_date=last_trade_date,
            tick_size=tick_size,
            lot_size=lot_size,
            currency=currency,
        )

    def normalize_business_event(
        self,
        *,
        event_id: str,
        category: str,
        title: str,
        effective_at: datetime,
        importance: float,
        uncertainty: float,
        detail: str,
    ) -> BusinessEvent:
        return BusinessEvent(
            provider=self.provider,
            event_id=event_id,
            category=category,
            title=title,
            effective_at=effective_at,
            importance=importance,
            uncertainty=uncertainty,
            detail=detail,
        )
