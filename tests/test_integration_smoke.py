from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from apps.worker.runner import main as worker_main


@pytest.mark.integration
def test_end_to_end_signal_dashboard_notification_smoke(client: TestClient) -> None:
    signals = client.get("/api/v1/signals", params={"root": "Si"})
    assert signals.status_code == 200
    signals_payload = signals.json()
    assert signals_payload

    generated_at = datetime.fromisoformat(signals_payload[0]["generated_at"].replace("Z", "+00:00"))
    as_of = (generated_at + timedelta(days=40)).astimezone(UTC).isoformat()

    recalc = client.post(
        "/api/v1/admin/recalculate",
        json={
            "root": "Si",
            "as_of": as_of,
            "resolve_due": True,
        },
    )
    assert recalc.status_code == 200
    assert recalc.json()["signals_resolved"] >= 1

    dashboard = client.get("/api/v1/dashboard", params={"root": "Si"})
    assert dashboard.status_code == 200
    assert dashboard.json()["spotlight_signals"]

    preview = client.get("/api/v1/notifications/telegram/preview", params={"root": "Si", "limit": 2})
    assert preview.status_code == 200
    assert "IMOEX Signal Brief" in preview.json()["message"]

    worker_exit = worker_main(["notify-telegram", "--root", "Si", "--dry-run"])
    assert worker_exit == 0
