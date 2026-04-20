from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from libs.bootstrap.container import get_app_container
from libs.domain.service import get_contract_master_service
from libs.marketdata.service import get_market_data_service
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


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    database_path = tmp_path / "api_test.db"
    backup_path = tmp_path / "backups"
    monkeypatch.setattr(settings, "database_url", f"sqlite:///{database_path.as_posix()}")
    monkeypatch.setattr(settings, "backups_dir", backup_path.as_posix())
    monkeypatch.setattr(settings, "market_data_live_enabled", False)
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
