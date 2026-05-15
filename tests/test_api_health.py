from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from libs.utils.config import settings


def test_health_sources_contains_moex_and_database(client: TestClient) -> None:
    response = client.get("/api/v1/health/sources")

    assert response.status_code == 200
    payload = response.json()
    providers = {item["provider"] for item in payload}

    assert "moex" in providers
    assert "telegram" in providers
    assert "database" in providers


def test_health_capabilities_expose_baseline_adapter_registry(client: TestClient) -> None:
    response = client.get("/api/v1/health/capabilities")

    assert response.status_code == 200
    payload = response.json()
    by_provider = {item["provider"]: item["capabilities"] for item in payload}

    assert "moex" in by_provider
    assert "tbank" in by_provider
    assert "alor" in by_provider
    assert by_provider["finam"]["stream_bars"] is True
    assert by_provider["cbr"]["historical_bars"] is False


def test_health_registry_exposes_source_registry_entries(client: TestClient) -> None:
    response = client.get("/api/v1/health/registry")

    assert response.status_code == 200
    payload = response.json()

    assert any(item["provider"] == "alor" and item["auth_type"] == "jwt" for item in payload)
    assert any(
        item["provider"] == "finam"
        and item["implementation_status"] == "baseline"
        and item["auth_type"] == "api_key_or_jwt"
        for item in payload
    )
    assert any(item["provider"] == "bcs" and item["auth_type"] == "token" for item in payload)
    assert any(item["provider"] == "tbank" and item["auth_type"] == "token" for item in payload)


def test_health_feature_flags_and_runtime_metrics_are_exposed(client: TestClient) -> None:
    warmup = client.get("/api/v1/roots")
    assert warmup.status_code == 200

    flags = client.get("/api/v1/health/feature-flags")
    assert flags.status_code == 200
    flags_payload = flags.json()
    assert any(item["name"] == "dashboard_ui" and item["enabled"] is True for item in flags_payload)
    assert any(item["name"] == "telegram_delivery" and item["enabled"] is True for item in flags_payload)

    metrics = client.get("/api/v1/health/runtime-metrics")
    assert metrics.status_code == 200
    metrics_payload = metrics.json()
    metric_names = {item["name"] for item in metrics_payload["metrics"]}
    assert "http_requests_total" in metric_names
    assert "http_request_duration_avg_ms" in metric_names
    assert any(key.startswith("GET ") for key in metrics_payload["route_hits"])

    schedules = client.get("/api/v1/health/schedules")
    assert schedules.status_code == 200
    schedules_payload = schedules.json()
    assert any(item["job_id"] == "reference-sync-morning" for item in schedules_payload)
    assert all("next_run_at" in item for item in schedules_payload)
    assert all("last_run_status" in item for item in schedules_payload)

    schedule_runs = client.get("/api/v1/health/schedule-runs")
    assert schedule_runs.status_code == 200
    assert isinstance(schedule_runs.json(), list)

    schedule_export = client.get("/api/v1/health/schedule-runs/export")
    assert schedule_export.status_code == 200
    assert schedule_export.text is not None

    leader = client.get("/api/v1/health/scheduler-leader")
    assert leader.status_code == 200
    leader_payload = leader.json()
    assert leader_payload["lock_key"] == "scheduler:leader"
    assert "is_leader" in leader_payload


def test_health_modules_exposes_modular_monolith_catalog(client: TestClient) -> None:
    response = client.get("/api/v1/health/modules")

    assert response.status_code == 200
    payload = response.json()

    names = {item["name"] for item in payload}
    assert "bootstrap" in names
    assert "domain" in names
    assert "journal" in names
    assert "scheduler" in names
    assert "dashboard" in names
    assert "worker" in names


def test_product_readiness_health_gate_covers_operator_surfaces(client: TestClient) -> None:
    response = client.get("/api/v1/health/product-readiness", params={"root": "Si"})

    assert response.status_code == 200
    payload = response.json()

    assert payload["root"] == "Si"
    assert payload["release_gate"] == "pass"
    checks = {item["key"]: item for item in payload["checks"]}

    assert checks["database"]["status"] == "ok"
    assert checks["dashboard_surface"]["status"] == "ok"
    assert checks["workspace_surface"]["status"] == "ok"
    assert checks["review_loop_surface"]["status"] == "ok"
    assert checks["runtime_control_surface"]["status"] == "ok"
    assert checks["runtime_prompt_governance"]["status"] == "ok"
    assert checks["admin_runtime_security"]["status"] == "ok"
    assert checks["admin_runtime_security"]["severity"] == "advisory"
    assert checks["admin_health_surface"]["status"] == "ok"
    assert checks["backup_freshness"]["status"] in {"ok", "warning"}
    assert checks["scheduler_health"]["status"] in {"ok", "warning"}
    assert checks["delivery_readiness"]["status"] in {"ok", "warning"}
    assert checks["migration_status"]["status"] in {"ok", "warning"}
    assert checks["market_data_policy"]["status"] == "ok"
    assert checks["market_data_truth"]["status"] == "ok"
    assert checks["market_data_truth"]["metrics"]["market_visible"] is True
    assert checks["market_data_policy"]["metrics"]["market_visible"] is True
    assert checks["market_data_policy"]["metrics"]["live_required"] is False
    assert checks["runtime_prompt_governance"]["metrics"]["rendered_prompts"] >= 6


def test_product_readiness_health_gate_warns_when_market_data_is_hidden(
    client_without_market_data: TestClient,
) -> None:
    response = client_without_market_data.get("/api/v1/health/product-readiness", params={"root": "Si"})

    assert response.status_code == 200
    payload = response.json()

    assert payload["release_gate"] == "pass"
    assert payload["status"] == "warning"
    checks = {item["key"]: item for item in payload["checks"]}

    assert checks["workspace_surface"]["status"] == "ok"
    assert checks["runtime_prompt_governance"]["status"] == "ok"
    assert checks["market_data_truth"]["status"] == "warning"
    assert checks["market_data_truth"]["metrics"]["market_visible"] is False
    assert checks["market_data_policy"]["status"] == "warning"
    assert checks["market_data_policy"]["metrics"]["market_visible"] is False


def test_product_readiness_health_gate_blocks_when_live_market_data_is_required(
    client_without_market_data: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "product_readiness_require_live_market_data", True)

    response = client_without_market_data.get("/api/v1/health/product-readiness", params={"root": "Si"})

    assert response.status_code == 200
    payload = response.json()
    checks = {item["key"]: item for item in payload["checks"]}

    assert payload["release_gate"] == "fail"
    assert payload["status"] == "not_ok"
    assert checks["market_data_policy"]["severity"] == "required"
    assert checks["market_data_policy"]["status"] == "not_ok"
    assert checks["market_data_policy"]["metrics"]["live_required"] is True
    assert checks["market_data_policy"]["metrics"]["market_visible"] is False


def test_product_readiness_health_gate_requires_restore_evidence_for_production(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "app_environment", "production")
    monkeypatch.setattr(settings, "admin_api_key", "prod-test-key")
    monkeypatch.setattr(settings, "market_data_live_enabled", True)
    monkeypatch.setattr(settings, "product_readiness_restore_evidence_path", None)

    response = client.get("/api/v1/health/product-readiness", params={"root": "Si"})

    assert response.status_code == 200
    payload = response.json()
    checks = {item["key"]: item for item in payload["checks"]}

    assert payload["release_gate"] == "fail"
    assert payload["status"] == "not_ok"
    assert checks["admin_runtime_security"]["status"] == "ok"
    assert checks["admin_runtime_security"]["severity"] == "required"
    assert checks["market_data_policy"]["status"] == "ok"
    assert checks["market_data_policy"]["severity"] == "required"
    assert checks["restore_drill_evidence"]["status"] == "not_ok"
    assert checks["restore_drill_evidence"]["severity"] == "required"
    assert checks["restore_drill_evidence"]["metrics"]["required"] is True


def test_product_readiness_health_gate_accepts_fresh_restore_evidence_for_production(
    client: TestClient,
    tmp_path,
    monkeypatch,
) -> None:
    evidence_path = tmp_path / "restore-evidence.json"
    evidence_path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(UTC).isoformat(),
                "root": "Si",
                "integrity_check": "ok",
                "roots": 1,
                "final_signals": 3,
                "release_gate": "pass",
                "admin_status": "ok",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(settings, "app_environment", "production")
    monkeypatch.setattr(settings, "admin_api_key", "prod-test-key")
    monkeypatch.setattr(settings, "market_data_live_enabled", True)
    monkeypatch.setattr(settings, "product_readiness_restore_evidence_path", evidence_path.as_posix())

    response = client.get("/api/v1/health/product-readiness", params={"root": "Si"})

    assert response.status_code == 200
    payload = response.json()
    checks = {item["key"]: item for item in payload["checks"]}

    assert payload["release_gate"] == "pass"
    assert checks["restore_drill_evidence"]["status"] == "ok"
    assert checks["restore_drill_evidence"]["severity"] == "required"
    assert checks["restore_drill_evidence"]["metrics"]["path"] == str(evidence_path)
    assert checks["restore_drill_evidence"]["metrics"]["release_gate"] == "pass"


def test_product_readiness_health_gate_blocks_when_required_market_data_is_degraded(
    client: TestClient,
    monkeypatch,
) -> None:
    from libs.dashboard.service import DashboardService

    original_build_workspace_snapshot = DashboardService.build_workspace_snapshot

    def build_degraded_workspace_snapshot(self, *args, **kwargs):
        snapshot = original_build_workspace_snapshot(self, *args, **kwargs)
        if snapshot.market_snapshot is not None:
            snapshot.market_snapshot.status = "degraded"
            snapshot.market_snapshot.status_detail = "Forced degraded status for readiness policy."
        return snapshot

    monkeypatch.setattr(DashboardService, "build_workspace_snapshot", build_degraded_workspace_snapshot)
    monkeypatch.setattr(settings, "product_readiness_require_live_market_data", True)
    monkeypatch.setattr(settings, "market_data_live_enabled", True)

    response = client.get("/api/v1/health/product-readiness", params={"root": "Si"})

    assert response.status_code == 200
    payload = response.json()
    checks = {item["key"]: item for item in payload["checks"]}

    assert payload["release_gate"] == "fail"
    assert checks["market_data_truth"]["status"] == "warning"
    assert checks["market_data_policy"]["severity"] == "required"
    assert checks["market_data_policy"]["status"] == "not_ok"
    assert checks["market_data_policy"]["metrics"]["market_status"] == "degraded"
