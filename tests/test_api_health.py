from __future__ import annotations

from fastapi.testclient import TestClient


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
    assert checks["market_data_truth"]["status"] == "ok"
    assert checks["market_data_truth"]["metrics"]["market_visible"] is True
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
