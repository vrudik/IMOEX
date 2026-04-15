from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from libs.utils.config import settings


def test_dashboard_snapshot_returns_delivery_payload(client: TestClient) -> None:
    response = client.get("/api/v1/dashboard", params={"root": "Si"})

    assert response.status_code == 200
    payload = response.json()

    assert payload["selected_root"] == "Si"
    assert payload["roots"]
    assert payload["root_details"]["root"]["root_code"] == "Si"
    assert payload["spotlight_signals"]
    assert payload["recent_signals"]
    assert payload["evaluation"]["top_k"] == 3
    assert payload["admin_health"]["database_status"] in {"ok", "not_ok"}
    assert len(payload["quality_pairs"]) == 2
    assert len(payload["kpis"]) >= 4
    assert payload["control_panel"]["llm_product"] == "ChatGPT"
    assert payload["control_panel"]["model_roles"]
    assert payload["control_panel"]["market_data_feeds"]


def test_workspace_snapshot_returns_user_facing_payload(client: TestClient) -> None:
    response = client.get("/api/v1/workspace", params={"root": "Si"})

    assert response.status_code == 200
    payload = response.json()

    assert payload["selected_root"] == "Si"
    assert payload["pulses"]
    assert payload["signal_lane"]
    assert payload["focus_signal"]["root"] == "Si"
    assert payload["action_items"]
    assert payload["delivery_windows"]
    assert any(item["event_kind"] == "digest" for item in payload["delivery_windows"])
    assert "delivery_activity" in payload
    assert "delivery_activity_pagination" in payload
    assert payload["focus_visual"]["metric_bars"]
    assert payload["focus_visual"]["timeline"]
    assert "telegram_preview_message" in payload
    assert payload["control_panel"]["llm_owner"] == "OpenAI"
    assert payload["control_panel"]["model_roles"]
    assert payload["control_panel"]["market_data_feeds"]


def test_root_redirects_to_workspace(client: TestClient) -> None:
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 307
    assert response.headers["location"] == "/workspace"


def test_dashboard_page_renders_html_control_room(client: TestClient) -> None:
    response = client.get("/dashboard", params={"root": "Si"})

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert 'lang="ru"' in response.text
    assert "Сигнальная панель для Si" in response.text
    assert "Модели и источники данных" in response.text
    assert "Пульт серии" in response.text
    assert 'id="dashboard-data"' in response.text


def test_workspace_page_renders_user_journey_html(client: TestClient) -> None:
    response = client.get("/workspace", params={"root": "Si"})

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert 'lang="ru"' in response.text
    assert "Что делать с Si прямо сейчас?" in response.text
    assert "Пакет решения" in response.text
    assert "Календарь доставок" in response.text
    assert "Активность доставок" in response.text
    assert "Статус" in response.text
    assert "Экспорт CSV" in response.text
    assert "Отправить сейчас" in response.text
    assert "Визуальный пульс" in response.text
    assert "Модели и источники данных" in response.text
    assert 'id="workspace-journal-form"' in response.text
    assert 'id="workspace-data"' in response.text


def test_workspace_signal_snapshot_returns_detail_payload(client: TestClient) -> None:
    workspace = client.get("/api/v1/workspace", params={"root": "Si"})
    signal_id = workspace.json()["focus_signal"]["signal_id"]

    response = client.get(f"/api/v1/workspace/signals/{signal_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["signal"]["signal_id"] == signal_id
    assert payload["signal"]["root"] == "Si"
    assert payload["visual"]["metric_bars"]
    assert payload["visual"]["timeline"]
    assert "telegram_preview_message" in payload
    assert "related_signals" in payload


def test_workspace_signal_page_renders_detail_html(client: TestClient) -> None:
    workspace = client.get("/api/v1/workspace", params={"root": "Si"})
    signal_id = workspace.json()["focus_signal"]["signal_id"]

    response = client.get(f"/workspace/signals/{signal_id}")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert 'lang="ru"' in response.text
    assert "Сигнал | Пользовательский сценарий" in response.text
    assert "График сигнала" in response.text
    assert "Хронология" in response.text
    assert "Анатомия решения" in response.text
    assert 'id="signal-journal-form"' in response.text
    assert 'id="signal-page-data"' in response.text


def test_workspace_journal_snapshot_returns_filtered_entries(client: TestClient) -> None:
    workspace = client.get("/api/v1/workspace", params={"root": "Si"})
    signal_id = workspace.json()["focus_signal"]["signal_id"]
    create_response = client.post(
        f"/api/v1/journal/{signal_id}",
        json={
            "kind": "thesis",
            "title": "Opening thesis",
            "note": "Signal still aligned with the main setup.",
            "author": "test",
        },
    )
    assert create_response.status_code == 200

    response = client.get("/api/v1/workspace/journal", params={"root": "Si", "kind": "thesis"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["selected_root"] == "Si"
    assert payload["selected_kind"] == "thesis"
    assert payload["entries"]
    assert payload["entries"][0]["entry"]["title"] == "Opening thesis"


def test_workspace_journal_page_renders_html(client: TestClient) -> None:
    workspace = client.get("/api/v1/workspace", params={"root": "Si"})
    signal_id = workspace.json()["focus_signal"]["signal_id"]
    client.post(
        f"/api/v1/journal/{signal_id}",
        json={
            "kind": "risk_note",
            "title": "Main risk",
            "note": "Roll share is rising faster than expected.",
            "author": "test",
        },
    )

    response = client.get("/workspace/journal", params={"root": "Si"})

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert 'lang="ru"' in response.text
    assert "Память торговой системы" in response.text
    assert "Лента журнала" in response.text
    assert 'id="journal-workspace-data"' in response.text


def test_workspace_preferences_snapshot_can_be_saved_and_used(client: TestClient) -> None:
    save_response = client.post(
        "/api/v1/workspace/preferences",
        json={
            "default_root": "BR",
            "subscribed_roots": ["BR", "Si"],
            "subscribed_horizons": ["H4W"],
            "subscribed_event_kinds": ["digest", "resolution"],
            "min_priority_score": 2,
            "quiet_hours_start": "22:00",
            "quiet_hours_end": "07:00",
            "suppress_during_quiet_hours": True,
            "digest_limit": 2,
        },
    )
    assert save_response.status_code == 200
    payload = save_response.json()
    assert payload["preferences"]["default_root"] == "BR"
    assert payload["preferences"]["subscribed_horizons"] == ["H4W"]
    assert payload["preferences"]["subscribed_event_kinds"] == ["digest", "resolution"]
    assert payload["preferences"]["suppress_during_quiet_hours"] is True
    assert payload["delivery_windows"]
    assert "delivery_activity" in payload
    assert "delivery_activity_pagination" in payload
    assert any(item["event_kind"] == "resolution" for item in payload["delivery_windows"])

    workspace = client.get("/api/v1/workspace")
    assert workspace.status_code == 200
    assert workspace.json()["selected_root"] == "BR"


def test_workspace_preferences_page_renders_html(client: TestClient) -> None:
    response = client.get("/workspace/preferences")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert 'lang="ru"' in response.text
    assert "Управляйте тем, что приходит и когда" in response.text
    assert "Telegram" in response.text
    assert "Календарь доставок" in response.text
    assert "Активность доставок" in response.text
    assert "Статус" in response.text
    assert "Экспорт CSV" in response.text
    assert "Отправить сейчас" in response.text
    assert 'id="preferences-form"' in response.text
    assert 'id="preferences-data"' in response.text


def test_workspace_delivery_history_snapshot_returns_audit_payload(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "telegram_enabled", True)
    monkeypatch.setattr(settings, "telegram_bot_token", "test-token")
    monkeypatch.setattr(settings, "telegram_chat_id", "123456")

    def _send_message(self, *, token, chat_id, text, parse_mode, disable_web_page_preview):
        return {"ok": True, "result": {"message_id": 129}}

    monkeypatch.setattr("libs.notifications.telegram.TelegramBotClient.send_message", _send_message)
    response = client.post(
        "/api/v1/workspace/delivery/send-now",
        json={"root": "Si", "event_kind": "digest", "limit": 2},
    )
    assert response.status_code == 200

    history = client.get(
        "/api/v1/workspace/delivery-history",
        params={"root": "Si", "activity_event_kind": "digest", "activity_page_size": 10},
    )

    assert history.status_code == 200
    payload = history.json()
    assert payload["selected_root"] == "Si"
    assert payload["roots"]
    assert payload["delivery_activity"]
    assert payload["delivery_activity_filters"]["event_kind"] == "digest"
    assert payload["delivery_activity_pagination"]["page_size"] == 10


def test_workspace_delivery_history_page_renders_html(client: TestClient) -> None:
    response = client.get("/workspace/delivery-history", params={"root": "Si"})

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert 'lang="ru"' in response.text
    assert "Журнал доставки в Telegram" in response.text
    assert "Активность доставок" in response.text
    assert "Сводка по группам" in response.text
    assert "Экспорт CSV" in response.text
    assert 'id="delivery-history-data"' in response.text


def test_workspace_delivery_skip_next_updates_calendar(client: TestClient) -> None:
    response = client.post(
        "/api/v1/workspace/delivery/skip-next",
        json={"event_kind": "digest"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "digest" in payload["preferences"]["skip_next_event_kinds"]
    digest_window = next(item for item in payload["delivery_windows"] if item["event_kind"] == "digest")
    assert digest_window["skip_next_pending"] is True
    assert payload["delivery_activity"]
    assert payload["delivery_activity"][0]["action"] == "skip_next"


def test_workspace_delivery_undo_skip_clears_calendar(client: TestClient) -> None:
    skipped = client.post(
        "/api/v1/workspace/delivery/skip-next",
        json={"event_kind": "digest"},
    )
    assert skipped.status_code == 200

    response = client.post(
        "/api/v1/workspace/delivery/undo-skip",
        json={"event_kind": "digest"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["preferences"]["skip_next_event_kinds"] == []
    digest_window = next(item for item in payload["delivery_windows"] if item["event_kind"] == "digest")
    assert digest_window["skip_next_pending"] is False
    assert payload["delivery_activity"]
    assert payload["delivery_activity"][0]["action"] == "undo_skip"


def test_workspace_delivery_send_now_uses_notification_service(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "telegram_enabled", True)
    monkeypatch.setattr(settings, "telegram_bot_token", "test-token")
    monkeypatch.setattr(settings, "telegram_chat_id", "123456")

    def _send_message(self, *, token, chat_id, text, parse_mode, disable_web_page_preview):
        assert token == "test-token"
        assert chat_id == "123456"
        assert "Si" in text
        return {"ok": True, "result": {"message_id": 123}}

    monkeypatch.setattr("libs.notifications.telegram.TelegramBotClient.send_message", _send_message)

    response = client.post(
        "/api/v1/workspace/delivery/send-now",
        json={"root": "Si", "event_kind": "digest", "limit": 2},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["delivered"] is True
    assert payload["delivery_status"] == "sent"
    assert payload["preview"]["event_kind"] == "digest"

    workspace = client.get("/api/v1/workspace", params={"root": "Si"})
    assert workspace.status_code == 200
    activity = workspace.json()["delivery_activity"]
    assert activity
    assert activity[0]["action"] == "send_now"
    assert activity[0]["status"] == "sent"


def test_workspace_delivery_send_now_can_ignore_quiet_hours(client: TestClient, monkeypatch) -> None:
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

    def _send_message(self, *, token, chat_id, text, parse_mode, disable_web_page_preview):
        return {"ok": True, "result": {"message_id": 124}}

    monkeypatch.setattr("libs.notifications.telegram.TelegramBotClient.send_message", _send_message)

    response = client.post(
        "/api/v1/workspace/delivery/send-now",
        json={"root": "Si", "event_kind": "digest", "limit": 2, "ignore_quiet_hours": True},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["delivered"] is True
    assert payload["delivery_status"] == "sent"
    assert payload["provider_message_id"] == "124"


def test_workspace_delivery_activity_can_be_filtered_and_grouped(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "telegram_enabled", True)
    monkeypatch.setattr(settings, "telegram_bot_token", "test-token")
    monkeypatch.setattr(settings, "telegram_chat_id", "123456")

    def _send_message(self, *, token, chat_id, text, parse_mode, disable_web_page_preview):
        return {"ok": True, "result": {"message_id": 125}}

    monkeypatch.setattr("libs.notifications.telegram.TelegramBotClient.send_message", _send_message)

    send_response = client.post(
        "/api/v1/workspace/delivery/send-now",
        json={"root": "Si", "event_kind": "digest", "limit": 2},
    )
    assert send_response.status_code == 200
    skip_response = client.post(
        "/api/v1/workspace/delivery/skip-next",
        json={"event_kind": "digest"},
    )
    assert skip_response.status_code == 200

    response = client.get(
        "/api/v1/workspace",
        params={"root": "Si", "activity_event_kind": "digest", "activity_status": "sent"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["delivery_activity_filters"]["root_scope"] == "Si"
    assert payload["delivery_activity_filters"]["event_kind"] == "digest"
    assert payload["delivery_activity_filters"]["status"] == "sent"
    assert payload["delivery_activity"]
    assert all(item["event_kind"] == "digest" for item in payload["delivery_activity"])
    assert all(item["status"] == "sent" for item in payload["delivery_activity"])
    assert any(group["value"] == "digest" for group in payload["delivery_activity_by_event_kind"])
    assert any(group["value"] == "sent" for group in payload["delivery_activity_by_status"])


def test_preferences_delivery_activity_supports_root_filter_and_groups(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "telegram_enabled", True)
    monkeypatch.setattr(settings, "telegram_bot_token", "test-token")
    monkeypatch.setattr(settings, "telegram_chat_id", "123456")

    def _send_message(self, *, token, chat_id, text, parse_mode, disable_web_page_preview):
        return {"ok": True, "result": {"message_id": 126}}

    monkeypatch.setattr("libs.notifications.telegram.TelegramBotClient.send_message", _send_message)

    assert client.post(
        "/api/v1/workspace/delivery/send-now",
        json={"root": "Si", "event_kind": "digest", "limit": 2},
    ).status_code == 200
    assert client.post(
        "/api/v1/workspace/delivery/send-now",
        json={"root": "BR", "event_kind": "resolution", "limit": 2},
    ).status_code == 200

    unfiltered = client.get("/api/v1/workspace/preferences")
    assert unfiltered.status_code == 200
    unfiltered_payload = unfiltered.json()
    assert any(group["value"] == "Si" for group in unfiltered_payload["delivery_activity_by_root_scope"])
    assert any(group["value"] == "BR" for group in unfiltered_payload["delivery_activity_by_root_scope"])

    filtered = client.get("/api/v1/workspace/preferences", params={"activity_root_scope": "BR"})
    assert filtered.status_code == 200
    payload = filtered.json()
    assert payload["delivery_activity_filters"]["root_scope"] == "BR"
    assert payload["delivery_activity"]
    assert all(item["root_scope"] == "BR" for item in payload["delivery_activity"])


def test_workspace_delivery_activity_supports_pagination(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "telegram_enabled", True)
    monkeypatch.setattr(settings, "telegram_bot_token", "test-token")
    monkeypatch.setattr(settings, "telegram_chat_id", "123456")

    def _send_message(self, *, token, chat_id, text, parse_mode, disable_web_page_preview):
        return {"ok": True, "result": {"message_id": 127}}

    monkeypatch.setattr("libs.notifications.telegram.TelegramBotClient.send_message", _send_message)

    for _ in range(3):
        response = client.post(
            "/api/v1/workspace/delivery/send-now",
            json={"root": "Si", "event_kind": "digest", "limit": 2},
        )
        assert response.status_code == 200

    first_page = client.get(
        "/api/v1/workspace",
        params={"root": "Si", "activity_page": 1, "activity_page_size": 2},
    )
    assert first_page.status_code == 200
    first_payload = first_page.json()
    assert first_payload["delivery_activity_pagination"]["page"] == 1
    assert first_payload["delivery_activity_pagination"]["page_size"] == 2
    assert first_payload["delivery_activity_pagination"]["total_items"] >= 3
    assert first_payload["delivery_activity_pagination"]["has_next"] is True
    assert len(first_payload["delivery_activity"]) == 2

    second_page = client.get(
        "/api/v1/workspace",
        params={"root": "Si", "activity_page": 2, "activity_page_size": 2},
    )
    assert second_page.status_code == 200
    second_payload = second_page.json()
    assert second_payload["delivery_activity_pagination"]["page"] == 2
    assert second_payload["delivery_activity_pagination"]["has_previous"] is True
    assert second_payload["delivery_activity"]


def test_workspace_delivery_activity_export_supports_csv_and_jsonl(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "telegram_enabled", True)
    monkeypatch.setattr(settings, "telegram_bot_token", "test-token")
    monkeypatch.setattr(settings, "telegram_chat_id", "123456")

    def _send_message(self, *, token, chat_id, text, parse_mode, disable_web_page_preview):
        return {"ok": True, "result": {"message_id": 128}}

    monkeypatch.setattr("libs.notifications.telegram.TelegramBotClient.send_message", _send_message)

    response = client.post(
        "/api/v1/workspace/delivery/send-now",
        json={"root": "Si", "event_kind": "digest", "limit": 2},
    )
    assert response.status_code == 200

    csv_response = client.get(
        "/api/v1/workspace/delivery/activity/export",
        params={"root": "Si", "activity_event_kind": "digest", "export_format": "csv"},
    )
    assert csv_response.status_code == 200
    assert "text/csv" in csv_response.headers["content-type"]
    assert "activity_id,action,event_kind" in csv_response.text
    assert '"digest"' in csv_response.text

    jsonl_response = client.get(
        "/api/v1/workspace/delivery/activity/export",
        params={"root": "Si", "activity_event_kind": "digest", "export_format": "jsonl"},
    )
    assert jsonl_response.status_code == 200
    assert "application/x-ndjson" in jsonl_response.headers["content-type"]
    assert '"event_kind": "digest"' in jsonl_response.text


def test_dashboard_can_be_disabled_by_feature_flag(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "feature_flags_json", '{"dashboard_ui": false}')

    response = client.get("/api/v1/dashboard", params={"root": "Si"})

    assert response.status_code == 404


def test_workspace_can_be_disabled_by_feature_flag(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "feature_flags_json", '{"dashboard_ui": false}')

    response = client.get("/api/v1/workspace", params={"root": "Si"})

    assert response.status_code == 404


def test_workspace_signal_page_can_be_disabled_by_feature_flag(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "feature_flags_json", '{"dashboard_ui": false}')

    response = client.get("/workspace/signals/test-signal-id")

    assert response.status_code == 404


def test_workspace_journal_page_can_be_disabled_by_feature_flag(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "feature_flags_json", '{"dashboard_ui": false}')

    response = client.get("/workspace/journal")

    assert response.status_code == 404


def test_workspace_preferences_page_can_be_disabled_by_feature_flag(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "feature_flags_json", '{"dashboard_ui": false}')

    response = client.get("/workspace/preferences")

    assert response.status_code == 404


def test_workspace_delivery_history_page_can_be_disabled_by_feature_flag(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "feature_flags_json", '{"dashboard_ui": false}')

    response = client.get("/workspace/delivery-history")

    assert response.status_code == 404
