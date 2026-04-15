from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from libs.domain.contracts import CapabilityRegistry, SourceHealth


class AdapterImplementationStatus(StrEnum):
    LIVE = "live"
    BASELINE = "baseline"
    PLANNED = "planned"


class Bar(BaseModel):
    provider: str
    root: str
    contract: str
    timeframe: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    start_at: datetime
    end_at: datetime


class Trade(BaseModel):
    provider: str
    contract: str
    trade_id: str
    price: float
    quantity: float
    side: str
    traded_at: datetime


class OrderBookLevel(BaseModel):
    price: float
    quantity: float


class OrderBook(BaseModel):
    provider: str
    contract: str
    as_of: datetime
    bids: list[OrderBookLevel] = Field(default_factory=list)
    asks: list[OrderBookLevel] = Field(default_factory=list)


class TradingStatus(BaseModel):
    provider: str
    contract: str
    status: str
    detail: str
    as_of: datetime


class ContractMeta(BaseModel):
    provider: str
    contract_code: str
    root_code: str
    expiry_date: date
    last_trade_date: date
    tick_size: float
    lot_size: int
    currency: str


class BusinessEvent(BaseModel):
    provider: str
    event_id: str
    category: str
    title: str
    effective_at: datetime
    importance: float
    uncertainty: float
    detail: str


class SourceRegistryEntry(BaseModel):
    provider: str
    adapter_kind: str
    implementation_status: AdapterImplementationStatus
    auth_type: str
    transports: list[str] = Field(default_factory=list)
    primary_use_cases: list[str] = Field(default_factory=list)
    usage_notes: list[str] = Field(default_factory=list)
    graceful_degradation: str
    capabilities: CapabilityRegistry
    health: SourceHealth
