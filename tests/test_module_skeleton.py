from __future__ import annotations

from libs.bootstrap.container import get_app_container
from libs.bootstrap.modules import list_module_specs


def test_module_catalog_covers_core_application_and_entrypoint_layers() -> None:
    modules = list_module_specs()
    names = {item.name for item in modules}

    assert "bootstrap" in names
    assert "domain" in names
    assert "reference" in names
    assert "journal" in names
    assert "signals" in names
    assert "scheduler" in names
    assert "dashboard" in names
    assert "notifications" in names
    assert "api" in names
    assert "worker" in names
    assert any(item.layer == "entrypoint" and item.name == "api" for item in modules)


def test_app_container_builds_shared_runtime_services() -> None:
    container = get_app_container()

    assert container.repository is not None
    assert container.contract_master_service is not None
    assert container.journal_service is not None
    assert container.pipeline_service is not None
    assert container.dashboard_service is not None
    assert container.telegram_notification_service is not None
    assert container.scheduler_service is not None
