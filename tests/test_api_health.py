from __future__ import annotations

from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)


def test_health_sources_contains_moex_and_database() -> None:
    response = client.get("/api/v1/health/sources")

    assert response.status_code == 200
    payload = response.json()
    providers = {item["provider"] for item in payload}

    assert "moex" in providers
    assert "database" in providers
