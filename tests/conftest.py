from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from libs.adapters.contracts import Bar
from libs.bootstrap.container import get_app_container
from libs.domain.service import get_contract_master_service
from libs.marketdata.service import (
    LiveInstrumentMarketSnapshot,
    LiveQuoteSnapshot,
    get_market_data_service,
)
from libs.reference.service import get_moex_reference_service
from libs.runtime.metrics import get_runtime_metrics_registry
from libs.utils.config import settings
from libs.utils.db import get_engine


@pytest.fixture(autouse=True)
def reset_cached_services() -> None:
    get_app_container.cache_clear()
    get_moex_reference_service.cache_clear()
    get_contract_master_service.cache_clear()
    get_market_data_service.cache_clear()
    get_engine.cache_clear()
    get_runtime_metrics_registry.cache_clear()
    yield
    get_app_container.cache_clear()
    get_moex_reference_service.cache_clear()
    get_contract_master_service.cache_clear()
    get_market_data_service.cache_clear()
    get_engine.cache_clear()
    get_runtime_metrics_registry.cache_clear()


class FakeMarketDataService:
    def __init__(self, *, available: bool = True) -> None:
        self.available = available

    def get_quote_snapshot(
        self,
        *,
        root_code: str,
        contract: str,
        providers: list[str],
        unit_hint: str | None = None,
        now: datetime | None = None,
    ) -> LiveQuoteSnapshot | None:
        if not self.available:
            return None
        current_time = now or datetime(2026, 4, 19, 9, 40, tzinfo=UTC)
        current_price = self._base_price(root_code)
        previous_price = round(current_price * 0.9945, 2)
        change_abs = round(current_price - previous_price, 2)
        change_pct = round(change_abs / previous_price, 4) if previous_price else None
        return LiveQuoteSnapshot(
            provider="moex",
            root_code=root_code,
            contract=contract,
            unit=unit_hint or self._unit(root_code),
            current_price=current_price,
            price_change_abs=change_abs,
            price_change_pct=change_pct,
            as_of=current_time,
            status="fresh",
            detail="Deterministic test quote.",
        )

    def get_market_snapshot(
        self,
        *,
        root_code: str,
        contract: str,
        providers: list[str],
        unit_hint: str | None = None,
        now: datetime | None = None,
    ) -> LiveInstrumentMarketSnapshot | None:
        quote = self.get_quote_snapshot(
            root_code=root_code,
            contract=contract,
            providers=providers,
            unit_hint=unit_hint,
            now=now,
        )
        if quote is None:
            return None
        current_time = quote.as_of
        return LiveInstrumentMarketSnapshot(
            provider="moex",
            root_code=root_code,
            contract=contract,
            unit=quote.unit,
            as_of=current_time,
            status="fresh",
            detail="Deterministic test snapshot.",
            quote=quote,
            daily_bars=self._build_bars(
                root_code=root_code,
                contract=contract,
                timeframe="1D",
                current_price=quote.current_price,
                count=12,
                step_ratio=0.0007,
                interval=timedelta(minutes=30),
                end_at=current_time,
            ),
            weekly_bars=self._build_bars(
                root_code=root_code,
                contract=contract,
                timeframe="1W",
                current_price=quote.current_price,
                count=7,
                step_ratio=0.0014,
                interval=timedelta(days=1),
                end_at=current_time,
            ),
            monthly_bars=self._build_bars(
                root_code=root_code,
                contract=contract,
                timeframe="1M",
                current_price=quote.current_price,
                count=6,
                step_ratio=0.0022,
                interval=timedelta(days=5),
                end_at=current_time,
            ),
        )

    def _build_bars(
        self,
        *,
        root_code: str,
        contract: str,
        timeframe: str,
        current_price: float,
        count: int,
        step_ratio: float,
        interval: timedelta,
        end_at: datetime,
    ) -> list[Bar]:
        step = max(current_price * step_ratio, 0.5)
        bars: list[Bar] = []
        for index in range(count):
            close = round(current_price - step * (count - index - 1), 2)
            open_price = round(close - step * 0.35, 2)
            high_price = round(max(open_price, close) + step * 0.4, 2)
            low_price = round(min(open_price, close) - step * 0.32, 2)
            bar_end = end_at - interval * (count - index - 1)
            bar_start = bar_end - interval
            bars.append(
                Bar(
                    provider="moex",
                    root=root_code,
                    contract=contract,
                    timeframe=timeframe,
                    open=open_price,
                    high=high_price,
                    low=low_price,
                    close=close,
                    volume=float(1000 + index * 125),
                    start_at=bar_start,
                    end_at=bar_end,
                )
            )
        return bars

    @staticmethod
    def _base_price(root_code: str) -> float:
        return {
            "SI": 96325.0,
            "BR": 6845.0,
            "MXI": 328950.0,
        }.get(root_code.upper(), 1000.0)

    @staticmethod
    def _unit(root_code: str) -> str:
        return "USD" if root_code.upper() == "BR" else "RUB"


def _install_fake_market_data(
    monkeypatch: pytest.MonkeyPatch,
    *,
    available: bool,
) -> FakeMarketDataService:
    import libs.bootstrap.container as container_module
    import libs.dashboard.service as dashboard_service_module

    service = FakeMarketDataService(available=available)
    monkeypatch.setattr(container_module, "get_market_data_service", lambda: service)
    monkeypatch.setattr(dashboard_service_module, "get_market_data_service", lambda: service)
    return service


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    database_path = tmp_path / "api_test.db"
    backup_path = tmp_path / "backups"
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{database_path.as_posix()}")
    monkeypatch.setattr(settings, "backups_dir", backup_path.as_posix())
    monkeypatch.setattr(settings, "market_data_live_enabled", False)
    monkeypatch.setattr(settings, "moex_reference_auto_sync_enabled", False)
    _install_fake_market_data(monkeypatch, available=True)
    get_app_container.cache_clear()
    get_engine.cache_clear()
    get_contract_master_service.cache_clear()
    get_market_data_service.cache_clear()
    with TestClient(app) as test_client:
        yield test_client
    try:
        get_engine().dispose()
    except Exception:
        pass
    get_app_container.cache_clear()
    get_contract_master_service.cache_clear()
    get_market_data_service.cache_clear()
    get_engine.cache_clear()


@pytest.fixture
def client_without_market_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    database_path = tmp_path / "api_test_no_market.db"
    backup_path = tmp_path / "backups_no_market"
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{database_path.as_posix()}")
    monkeypatch.setattr(settings, "backups_dir", backup_path.as_posix())
    monkeypatch.setattr(settings, "market_data_live_enabled", False)
    monkeypatch.setattr(settings, "moex_reference_auto_sync_enabled", False)
    _install_fake_market_data(monkeypatch, available=False)
    get_app_container.cache_clear()
    get_engine.cache_clear()
    get_contract_master_service.cache_clear()
    get_market_data_service.cache_clear()
    with TestClient(app) as test_client:
        yield test_client
    try:
        get_engine().dispose()
    except Exception:
        pass
    get_app_container.cache_clear()
    get_contract_master_service.cache_clear()
    get_market_data_service.cache_clear()
    get_engine.cache_clear()
