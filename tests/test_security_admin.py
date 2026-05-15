from __future__ import annotations

from fastapi.testclient import TestClient

from libs.utils.config import settings


ADMIN_KEY = "test-admin-key"


def test_admin_routes_require_api_key_when_configured(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "admin_api_key", ADMIN_KEY)

    missing = client.get("/api/v1/admin/health")
    assert missing.status_code == 401

    wrong = client.get("/api/v1/admin/health", headers={"X-IMOEX-Admin-Key": "wrong"})
    assert wrong.status_code == 401

    bootstrap = client.get("/api/v1/signals", params={"root": "Si"})
    assert bootstrap.status_code == 200

    allowed = client.get("/api/v1/admin/health", headers={"X-IMOEX-Admin-Key": ADMIN_KEY})
    assert allowed.status_code == 200
    assert allowed.json()["roots_count"] >= 1


def test_runtime_control_routes_require_api_key_when_configured(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "admin_api_key", ADMIN_KEY)

    hidden_snapshot = client.get("/api/v1/runtime/control-panel")
    assert hidden_snapshot.status_code == 401

    visible_snapshot = client.get("/api/v1/runtime/control-panel", headers={"X-IMOEX-Admin-Key": ADMIN_KEY})
    assert visible_snapshot.status_code == 200

    blocked_update = client.post(
        "/api/v1/runtime/control-panel/model-route",
        json={
            "role_key": "skeptic",
            "owner": "OpenAI",
            "product": "ChatGPT",
            "model": "gpt-5.4-mini",
            "control_mode": "editable",
            "detail": "Guarded route update",
        },
    )
    assert blocked_update.status_code == 401

    allowed_update = client.post(
        "/api/v1/runtime/control-panel/model-route",
        headers={"X-IMOEX-Admin-Key": ADMIN_KEY},
        json={
            "role_key": "skeptic",
            "owner": "OpenAI",
            "product": "ChatGPT",
            "model": "gpt-5.4-mini",
            "control_mode": "editable",
            "detail": "Guarded route update",
        },
    )
    assert allowed_update.status_code == 200
    assert any(event["category"] == "model_route" for event in allowed_update.json()["audit_trail"])


def test_production_environment_blocks_admin_routes_without_configured_key(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "app_environment", "production")
    monkeypatch.setattr(settings, "admin_api_key", None)

    response = client.get("/api/v1/admin/health")

    assert response.status_code == 503
    assert "ADMIN_API_KEY" in response.json()["detail"]


def test_product_readiness_blocks_production_without_admin_key(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "app_environment", "production")
    monkeypatch.setattr(settings, "admin_api_key", None)

    response = client.get("/api/v1/health/product-readiness", params={"root": "Si"})

    assert response.status_code == 200
    payload = response.json()
    checks = {item["key"]: item for item in payload["checks"]}
    security = checks["admin_runtime_security"]

    assert payload["release_gate"] == "fail"
    assert payload["status"] == "not_ok"
    assert security["severity"] == "required"
    assert security["status"] == "not_ok"
    assert security["metrics"]["environment"] == "production"
    assert security["metrics"]["protected_environment"] is True
