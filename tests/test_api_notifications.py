from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from libs.bootstrap.container import get_app_container
from libs.utils.config import settings


def test_telegram_preview_returns_rendered_delivery_payload(client: TestClient) -> None:
    response = client.get("/api/v1/notifications/telegram/preview", params={"root": "Si", "limit": 2})

    assert response.status_code == 200
    payload = response.json()

    assert payload["root"] == "Si"
    assert payload["configured"] is False
    assert payload["event_kind"] == "digest"
    assert payload["message"]
    assert "IMOEX Signal Brief" in payload["message"]
    assert len(payload["signal_ids"]) >= 1


def test_telegram_preview_uses_saved_default_root_when_root_not_provided(client: TestClient) -> None:
    save_response = client.post(
        "/api/v1/workspace/preferences",
        json={
            "default_root": "BR",
            "subscribed_roots": ["BR"],
            "subscribed_horizons": ["H4W"],
            "min_priority_score": 0,
            "digest_limit": 2,
        },
    )
    assert save_response.status_code == 200

    response = client.get("/api/v1/notifications/telegram/preview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["root"] == "BR"


def test_telegram_send_returns_disabled_status_when_channel_is_off(client: TestClient) -> None:
    response = client.post("/api/v1/notifications/telegram/send", json={"root": "Si", "limit": 2})

    assert response.status_code == 200
    payload = response.json()

    assert payload["delivered"] is False
    assert payload["delivery_status"] == "disabled"
    assert payload["preview"]["root"] == "Si"


def test_telegram_preview_marks_event_disabled_when_not_subscribed(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "telegram_enabled", True)
    monkeypatch.setattr(settings, "telegram_bot_token", "test-token")
    monkeypatch.setattr(settings, "telegram_chat_id", "123456")
    save_response = client.post(
        "/api/v1/workspace/preferences",
        json={
            "default_root": "Si",
            "subscribed_roots": ["Si"],
            "subscribed_horizons": ["H1S", "H3S", "H2W", "H4W"],
            "subscribed_event_kinds": ["digest"],
            "min_priority_score": 0,
            "digest_limit": 3,
        },
    )
    assert save_response.status_code == 200

    response = client.get("/api/v1/notifications/telegram/preview", params={"root": "Si", "event_kind": "resolution"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["event_kind"] == "resolution"
    assert payload["delivery_allowed"] is False
    assert payload["suppressed_reason"] == "event_disabled"


def test_telegram_send_suppresses_delivery_during_quiet_hours(client: TestClient, monkeypatch) -> None:
    now = datetime.now(UTC)
    start = (now - timedelta(hours=2)).strftime("%H:%M")
    end = (now + timedelta(hours=2)).strftime("%H:%M")
    monkeypatch.setattr(settings, "telegram_enabled", True)
    monkeypatch.setattr(settings, "telegram_bot_token", "test-token")
    monkeypatch.setattr(settings, "telegram_chat_id", "123456")
    save_response = client.post(
        "/api/v1/workspace/preferences",
        json={
            "default_root": "Si",
            "subscribed_roots": ["Si"],
            "subscribed_horizons": ["H1S", "H3S", "H2W", "H4W"],
            "subscribed_event_kinds": ["digest", "signal_open", "resolution", "post_mortem"],
            "min_priority_score": 0,
            "quiet_hours_start": start,
            "quiet_hours_end": end,
            "suppress_during_quiet_hours": True,
            "digest_limit": 3,
        },
    )
    assert save_response.status_code == 200

    response = client.post("/api/v1/notifications/telegram/send", json={"root": "Si", "limit": 2})

    assert response.status_code == 200
    payload = response.json()
    assert payload["delivered"] is False
    assert payload["delivery_status"] == "quiet_hours"
    assert payload["preview"]["quiet_hours_active"] is True
    assert payload["preview"]["suppressed_reason"] == "quiet_hours"


def test_telegram_send_can_ignore_quiet_hours_when_requested(
    client: TestClient,
    monkeypatch,
) -> None:
    now = datetime.now(UTC)
    start = (now - timedelta(hours=2)).strftime("%H:%M")
    end = (now + timedelta(hours=2)).strftime("%H:%M")
    save_response = client.post(
        "/api/v1/workspace/preferences",
        json={
            "default_root": "Si",
            "subscribed_roots": ["Si"],
            "subscribed_horizons": ["H1S", "H3S", "H2W", "H4W"],
            "subscribed_event_kinds": ["digest", "signal_open", "resolution", "post_mortem"],
            "min_priority_score": 0,
            "quiet_hours_start": start,
            "quiet_hours_end": end,
            "suppress_during_quiet_hours": True,
            "digest_limit": 3,
        },
    )
    assert save_response.status_code == 200
    monkeypatch.setattr(settings, "telegram_enabled", True)
    monkeypatch.setattr(settings, "telegram_bot_token", "test-token")
    monkeypatch.setattr(settings, "telegram_chat_id", "123456")

    def _send_message(self, *, token, chat_id, text, parse_mode, disable_web_page_preview):
        assert token == "test-token"
        assert chat_id == "123456"
        return {"ok": True, "result": {"message_id": 91}}

    monkeypatch.setattr("libs.notifications.telegram.TelegramBotClient.send_message", _send_message)

    response = client.post(
        "/api/v1/notifications/telegram/send",
        json={"root": "Si", "limit": 2, "ignore_quiet_hours": True},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["delivered"] is True
    assert payload["delivery_status"] == "sent"
    assert payload["provider_message_id"] == "91"


def test_telegram_schedule_skip_next_is_consumed_once(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "telegram_enabled", True)
    monkeypatch.setattr(settings, "telegram_bot_token", "test-token")
    monkeypatch.setattr(settings, "telegram_chat_id", "123456")
    skip_response = client.post(
        "/api/v1/workspace/delivery/skip-next",
        json={"event_kind": "digest"},
    )
    assert skip_response.status_code == 200

    first = client.post(
        "/api/v1/notifications/telegram/send",
        json={"root": "Si", "event_kind": "digest", "delivery_source": "schedule"},
    )
    assert first.status_code == 200
    first_payload = first.json()
    assert first_payload["delivery_status"] == "skip_next"

    def _send_message(self, *, token, chat_id, text, parse_mode, disable_web_page_preview):
        return {"ok": True, "result": {"message_id": 92}}

    monkeypatch.setattr("libs.notifications.telegram.TelegramBotClient.send_message", _send_message)

    second = client.post(
        "/api/v1/notifications/telegram/send",
        json={"root": "Si", "event_kind": "digest", "delivery_source": "schedule"},
    )
    assert second.status_code == 200
    second_payload = second.json()
    assert second_payload["delivery_status"] == "sent"
    assert second_payload["provider_message_id"] == "92"


def test_telegram_send_uses_mocked_bot_client_when_configured(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "telegram_enabled", True)
    monkeypatch.setattr(settings, "telegram_bot_token", "test-token")
    monkeypatch.setattr(settings, "telegram_chat_id", "123456")

    def _send_message(self, *, token, chat_id, text, parse_mode, disable_web_page_preview):
        assert token == "test-token"
        assert chat_id == "123456"
        assert parse_mode == settings.telegram_parse_mode
        assert disable_web_page_preview is settings.telegram_disable_link_preview
        assert "IMOEX Signal Brief" in text
        return {"ok": True, "result": {"message_id": 77}}

    monkeypatch.setattr("libs.notifications.telegram.TelegramBotClient.send_message", _send_message)

    response = client.post("/api/v1/notifications/telegram/send", json={"root": "Si", "limit": 2})

    assert response.status_code == 200
    payload = response.json()

    assert payload["delivered"] is True
    assert payload["delivery_status"] == "sent"
    assert payload["provider_message_id"] == "77"
    assert payload["chat_id"] == "123456"


def test_telegram_routes_can_be_disabled_by_feature_flag(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "feature_flags_json", '{"telegram_delivery": false}')

    response = client.get("/api/v1/notifications/telegram/preview", params={"root": "Si"})

    assert response.status_code == 404


def test_telegram_ops_preview_returns_alert_payload(client: TestClient) -> None:
    response = client.get("/api/v1/notifications/telegram/ops-preview")

    assert response.status_code == 200
    payload = response.json()
    assert payload["message"]
    assert "IMOEX Ops Alerts" in payload["message"]


def test_telegram_ops_send_uses_mocked_bot_client_when_configured(
    client: TestClient,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "telegram_enabled", True)
    monkeypatch.setattr(settings, "telegram_bot_token", "test-token")
    monkeypatch.setattr(settings, "telegram_chat_id", "654321")

    def _send_message(self, *, token, chat_id, text, parse_mode, disable_web_page_preview):
        assert token == "test-token"
        assert chat_id == "654321"
        assert "IMOEX Ops Alerts" in text
        return {"ok": True, "result": {"message_id": 88}}

    monkeypatch.setattr("libs.notifications.telegram.TelegramBotClient.send_message", _send_message)

    response = client.post("/api/v1/notifications/telegram/ops-send", json={})

    assert response.status_code == 200
    payload = response.json()
    assert payload["delivered"] is True
    assert payload["provider_message_id"] == "88"


def test_telegram_ops_preview_detects_scheduler_alerts(client: TestClient) -> None:
    service = get_app_container().scheduler_service
    service.run_job("recalculate-open", as_of=datetime.now(UTC) - timedelta(minutes=30))
    service.repository.finish_scheduler_run(
        idempotency_key=service.list_run_history(job_id="recalculate-open", limit=1)[0].idempotency_key,
        status="failed",
        detail="synthetic failure",
        result={"error": "synthetic failure"},
        finished_at=datetime.now(UTC),
    )

    response = client.get("/api/v1/notifications/telegram/ops-preview", params={"stale_after_minutes": 1})

    assert response.status_code == 200
    payload = response.json()
    assert payload["alert_items"]
    assert any(item["kind"] == "scheduler_failed_runs" for item in payload["alert_items"])
