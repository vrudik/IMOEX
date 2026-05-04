from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from fastapi.testclient import TestClient
from libs.utils.config import settings


def test_dashboard_snapshot_returns_delivery_payload(client: TestClient) -> None:
    response = client.get("/api/v1/dashboard", params={"root": "Si"})

    assert response.status_code == 200
    payload = response.json()

    assert payload["selected_root"] == "Si"
    assert payload["roots"]
    assert payload["root_details"]["root"]["root_code"] == "Si"
    assert isinstance(payload["root_details"]["continuous_series"]["days_to_expiry"], int)
    assert payload["control_panel"]["market_data_feeds"]
    assert payload["spotlight_signals"]
    assert payload["recent_signals"]
    assert payload["evaluation"]["top_k"] == 3
    assert payload["admin_health"]["database_status"] in {"ok", "not_ok"}
    assert len(payload["quality_pairs"]) == 2
    assert len(payload["kpis"]) >= 4
    assert payload["control_panel"]["llm_product"] == "ChatGPT"
    assert payload["control_panel"]["data_mode"] in {"live", "snapshot", "degraded_feed"}
    assert payload["control_panel"]["data_mode_detail"]
    assert payload["control_panel"]["reference_sync"]["source"]
    assert payload["control_panel"]["reference_sync"]["status"] in {"fresh", "stale", "fallback"}
    assert payload["control_panel"]["model_roles"]
    assert payload["control_panel"]["market_data_feeds"]


def test_workspace_snapshot_returns_user_facing_payload(client: TestClient) -> None:
    response = client.get("/api/v1/workspace", params={"root": "Si"})

    assert response.status_code == 200
    payload = response.json()

    assert payload["selected_root"] == "Si"
    assert payload["pulses"]
    selected_pulse = next(item for item in payload["pulses"] if item["root_code"] == "Si")
    assert selected_pulse["current_price"] > 0
    assert selected_pulse["price_change_pct"] is not None
    assert payload["signal_lane"]
    assert payload["market_snapshot"]["current_price"] > 0
    assert payload["market_snapshot"]["daily"]["points"]
    assert payload["market_snapshot"]["weekly"]["points"]
    assert payload["market_snapshot"]["monthly"]["points"]
    assert {"open", "high", "low", "close"} <= set(payload["market_snapshot"]["daily"]["points"][0])
    assert payload["market_snapshot"]["daily"]["overlays"]
    assert {item["key"] for item in payload["market_snapshot"]["daily"]["overlays"]} >= {"entry", "invalidation", "target"}
    assert payload["attention_inbox"]
    assert payload["morning_brief"]["signals_only"] is True
    assert payload["morning_brief"]["market_status"] in {"fresh", "aging", "stale", "degraded", "hidden", "unknown"}
    assert payload["morning_brief"]["top_attention"]
    assert payload["morning_brief"]["top_attention"][0]["href"].startswith("/workspace")
    assert payload["morning_brief"]["telegram_status"] in {"ready", "preview"}
    assert payload["watchlist_workbench"]["signals_only"] is True
    assert payload["watchlist_workbench"]["total_items"] == len(payload["watchlist"])
    assert payload["watchlist_workbench"]["review_due_items"] >= 0
    assert payload["watchlist_workbench"]["reviewed_today_items"] >= 0
    assert isinstance(payload["watchlist_workbench"]["watched_roots"], list)
    assert payload["watchlist_workbench"]["next_step"]
    top_attention = payload["attention_inbox"][0]
    assert top_attention["root_code"]
    assert top_attention["href"].startswith("/workspace")
    assert top_attention["reason"]
    assert top_attention["what_changed"]
    assert top_attention["next_step"]
    assert top_attention["market_status"] in {"fresh", "aging", "stale", "degraded", "hidden", "unknown"}
    assert payload["focus_signal"]["root"] == "Si"
    assert payload["focus_signal"]["workflow_state"] == "watching"
    assert payload["trust_ribbon"]["items"]
    assert payload["comparison"]["items"]
    assert "focus_signal_diff" in payload
    assert payload["system_confidence"]["score"] >= 20
    assert isinstance(payload["root_details"]["continuous_series"]["days_to_expiry"], int)
    assert payload["control_panel"]["market_data_feeds"]
    assert payload["action_items"]
    assert payload["delivery_windows"]
    assert any(item["event_kind"] == "digest" for item in payload["delivery_windows"])
    assert "delivery_activity" in payload
    assert "delivery_activity_pagination" in payload
    assert payload["focus_visual"]["metric_bars"]
    assert payload["focus_visual"]["timeline"]
    assert "telegram_preview_message" in payload
    assert payload["control_panel"]["llm_owner"] == "OpenAI"
    assert payload["control_panel"]["data_mode"] in {"live", "snapshot", "degraded_feed"}
    assert payload["control_panel"]["data_mode_detail"]
    assert payload["control_panel"]["reference_sync"]["source"]
    assert payload["control_panel"]["reference_sync"]["status"] in {"fresh", "stale", "fallback"}
    assert payload["control_panel"]["model_roles"]
    assert payload["control_panel"]["market_data_feeds"]


def test_workspace_snapshot_uses_current_supported_contract_expiry_dates(client: TestClient) -> None:
    expected_contracts = {
        "Si": ("SiM6", "SiU6", date(2026, 6, 18)),
        "BR": ("BRK6", "BRM6", date(2026, 5, 4)),
        "MXI": ("MXM6", "MXU6", date(2026, 6, 18)),
    }

    for root_code, (active_contract, next_contract, expiry_date) in expected_contracts.items():
        response = client.get("/api/v1/workspace", params={"root": root_code})

        assert response.status_code == 200
        payload = response.json()
        trading_day = date.fromisoformat(payload["root_details"]["session"]["trading_day"])

        assert payload["root_details"]["continuous_series"]["active_contract"] == active_contract
        assert payload["root_details"]["continuous_series"]["next_contract"] == next_contract
        assert payload["root_details"]["continuous_series"]["expiry_date"] == expiry_date.isoformat()
        assert payload["root_details"]["continuous_series"]["days_to_expiry"] == max(
            0, (expiry_date - trading_day).days
        )


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
    assert "Оценка" in response.text
    assert "Дней до экспирации" in response.text
    assert "18.06.2026" in response.text
    assert "Источник цены" in response.text
    assert "Как это работает" in response.text
    assert "Модели и источники данных" not in response.text
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
    assert "Дней до экспирации" in response.text
    assert "18.06.2026" in response.text
    assert "Источник цены" in response.text
    assert "MSK" in response.text
    assert "Как это работает" in response.text
    assert "Модели и источники данных" not in response.text
    assert "workflow-button" in response.text
    assert "Trust ribbon" in response.text
    assert 'data-operator-onboarding' in response.text
    assert 'data-morning-brief' in response.text
    assert "\u0423\u0442\u0440\u0435\u043d\u043d\u0438\u0439 \u0431\u0440\u0438\u0444" in response.text
    assert 'data-operator-onboarding-collapse' in response.text
    assert 'data-operator-onboarding-dismiss' in response.text
    assert 'data-attention-inbox' in response.text
    assert 'data-attention-card' in response.text
    assert 'imoex_operator_onboarding_hidden' in response.text
    assert 'imoex_operator_onboarding_collapsed' in response.text
    assert "\u0422\u0440\u0435\u0431\u0443\u0435\u0442 \u0432\u043d\u0438\u043c\u0430\u043d\u0438\u044f" in response.text
    assert "\u041a\u0430\u043a \u0447\u0438\u0442\u0430\u0442\u044c workspace" in response.text
    assert "\u0413\u043b\u043e\u0441\u0441\u0430\u0440\u0438\u0439 \u043e\u043f\u0435\u0440\u0430\u0442\u043e\u0440\u0430" in response.text
    assert "\u0422\u0435\u043a\u0443\u0449\u0430\u044f \u0446\u0435\u043d\u0430 \u0438 \u0433\u0440\u0430\u0444\u0438\u043a\u0438" in response.text
    assert "\u041f\u043e\u0441\u043b\u0435\u0434\u043d\u044f\u044f \u0446\u0435\u043d\u0430" in response.text
    assert "\u0414\u043d\u0435\u0432\u043d\u043e\u0439 \u043c\u0430\u043a\u0441\u0438\u043c\u0443\u043c" in response.text
    assert "\u0414\u043d\u0435\u0432\u043d\u043e\u0439 \u043c\u0438\u043d\u0438\u043c\u0443\u043c" in response.text
    assert "\u0414\u0435\u043d\u044c \u00b7 1D" in response.text
    assert "\u041d\u0435\u0434\u0435\u043b\u044f \u00b7 1W" in response.text
    assert "\u041c\u0435\u0441\u044f\u0446 \u00b7 1M" in response.text
    assert 'data-root-preview-button' in response.text
    assert 'data-root-preview-popover' in response.text
    assert 'data-pin-root-preview' in response.text
    assert 'data-root-price-line' in response.text
    assert 'data-root-level-chip' in response.text
    assert 'data-signal-preview-button' in response.text
    assert 'data-signal-preview-popover' in response.text
    assert 'data-pin-signal-preview' in response.text
    assert 'data-signal-level-chip' in response.text
    assert 'data-watchlist-review' in response.text
    assert 'id="watchlist-action-status"' in response.text
    assert 'data-watchlist-filter-review' in response.text
    assert 'data-watchlist-filter-root' in response.text
    assert 'data-watchlist-filter-linked' in response.text
    assert 'data-watchlist-bulk-review' in response.text
    assert 'data-watchlist-bulk-remove' in response.text
    assert 'data-watchlist-remove' in response.text
    assert 'runWatchlistAction' in response.text
    assert 'visibleWatchlistItems' in response.text
    assert 'applyWatchlistFilters' in response.text
    assert '/api/v1/workspace/watchlist/' in response.text
    assert 'data-journal-tag-picker' in response.text
    assert 'name="tags" value="data issue"' in response.text
    assert 'data-surface-state-strip="workspace"' in response.text
    assert 'data-market-panel' in response.text
    assert 'data-market-current-line' in response.text
    assert 'data-market-current-hit' in response.text
    assert 'data-market-distance-bar' in response.text
    assert 'renderMarketOhlcReadout' in response.text
    assert 'attachInteractiveMarketCharts' in response.text
    assert 'data-market-ohlc-readout' in response.text
    assert 'data-market-crosshair-x' in response.text
    assert 'data-market-range-toolbar' in response.text
    assert 'data-market-range-button' in response.text
    assert 'data-market-level-legend' in response.text
    assert 'data-market-level-detail' in response.text
    assert 'data-market-overlay-line' in response.text
    assert 'data-market-level-button' in response.text
    assert 'data-market-measure-readout' in response.text
    assert 'data-market-measure-layer' in response.text
    assert 'data-market-measure-line' in response.text
    assert 'data-compare-board' in response.text
    assert 'data-compare-root' in response.text
    assert 'data-compare-signal' in response.text
    assert 'data-compare-root-slot="a"' in response.text
    assert 'data-compare-root-slot="b"' in response.text
    assert 'data-compare-root-delta' in response.text
    assert 'data-compare-root-regime' in response.text
    assert 'data-compare-chart-host' in response.text
    assert 'data-compare-chart-readout' in response.text
    assert 'data-compare-chart-measure-readout' in response.text
    assert 'data-compare-range-toolbar' in response.text
    assert 'data-compare-range-button' in response.text
    assert 'data-compare-signal-slot="a"' in response.text
    assert 'data-compare-signal-slot="b"' in response.text
    assert 'data-compare-signal-delta' in response.text
    assert 'data-compare-signal-regime' in response.text
    assert "bindCompareStickyCursor" in response.text
    assert "applyCompareChartMeasurement" in response.text
    assert "buildCompareRangeToolbar" in response.text
    assert "renderCompareRegimeStrip" in response.text
    assert "buildCompareRegimeDriftNote" in response.text
    assert "compare-regime-note" in response.text
    assert "setCompareChartLevelFocus" in response.text
    assert "Watchlist review" in response.text
    assert "Recent outcomes" in response.text
    assert "Suggested tags" in response.text
    assert "Next review actions" in response.text
    assert 'data-tooltip="' in response.text
    assert '"tooltip_shift_intro"' in response.text
    assert "compare-delta-note" in response.text
    assert "buildPairMismatchCallout" in response.text
    assert "Watchlist" in response.text
    assert "What changed since last cycle?" in response.text
    assert 'id="workspace-journal-form"' in response.text
    assert 'id="workspace-data"' in response.text


def test_workspace_council_page_renders_explainer_html(client: TestClient) -> None:
    response = client.get("/workspace/council", params={"root": "Si"})

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert 'lang="ru"' in response.text
    assert "Как совет принимает решение по Si" in response.text
    assert "Какие вводные получает совет" in response.text
    assert "Блок-схема решения" in response.text
    assert "Кто участвует в совете" in response.text
    assert "Как читать итоговые score" in response.text
    assert "Текущий стек моделей и источников" in response.text
    assert "18.06.2026" in response.text
    assert "Скептик" in response.text
    assert "Арбитр" in response.text
    assert "control-summary-grid" in response.text
    assert "\u041a\u0430\u0440\u0442\u0430 \u0440\u0430\u0437\u043d\u043e\u0433\u043b\u0430\u0441\u0438\u0439" in response.text
    assert "\u041a\u043e\u043d\u0442\u0440\u0444\u0430\u043a\u0442\u0438\u0447\u0435\u0441\u043a\u0438\u0435 \u043f\u043e\u0434\u0441\u043a\u0430\u0437\u043a\u0438" in response.text
    assert 'data-surface-state-strip="council"' in response.text
    assert 'data-council-prompt-card' in response.text
    assert 'data-council-prompt-preview' in response.text
    assert '/workspace/runtime?root=Si#runtime-prompts' in response.text
    assert 'data-root-switch' in response.text


def test_workspace_signal_snapshot_returns_detail_payload(client: TestClient) -> None:
    workspace = client.get("/api/v1/workspace", params={"root": "Si"})
    signal_id = workspace.json()["focus_signal"]["signal_id"]

    response = client.get(f"/api/v1/workspace/signals/{signal_id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["signal"]["signal_id"] == signal_id
    assert payload["signal"]["root"] == "Si"
    assert payload["signal"]["workflow_state"] == "watching"
    assert payload["market_snapshot"]["current_price"] > 0
    assert payload["market_snapshot"]["daily"]["points"]
    assert payload["market_snapshot"]["weekly"]["points"]
    assert payload["market_snapshot"]["monthly"]["points"]
    assert {"open", "high", "low", "close"} <= set(payload["market_snapshot"]["daily"]["points"][0])
    assert payload["market_snapshot"]["daily"]["overlays"]
    assert {item["key"] for item in payload["market_snapshot"]["daily"]["overlays"]} >= {"entry", "invalidation", "target"}
    assert payload["signal_diff"]["summary"]
    assert payload["confidence_decomposition"]["factors"]
    assert payload["decision_log"]
    assert payload["visual"]["metric_bars"]
    assert payload["visual"]["timeline"]
    assert "telegram_preview_message" in payload
    assert "related_signals" in payload
    assert payload["roots"]
    assert any(item["root_code"] == "Si" for item in payload["roots"])
    assert payload["control_panel"]["reference_sync"]["source"]
    assert payload["control_panel"]["reference_sync"]["status"] in {"fresh", "stale", "fallback"}


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
    assert "\u0414\u043d\u0435\u0439 \u0434\u043e \u044d\u043a\u0441\u043f\u0438\u0440\u0430\u0446\u0438\u0438" in response.text
    assert "18.06.2026" in response.text
    assert "\u0418\u0441\u0442\u043e\u0447\u043d\u0438\u043a \u0446\u0435\u043d\u044b" in response.text
    assert "MSK" in response.text
    assert "\u0422\u0435\u043a\u0443\u0449\u0430\u044f \u0446\u0435\u043d\u0430 \u0438 \u0433\u0440\u0430\u0444\u0438\u043a\u0438" in response.text
    assert "\u041f\u043e\u0441\u043b\u0435\u0434\u043d\u044f\u044f \u0446\u0435\u043d\u0430" in response.text
    assert "\u0414\u043d\u0435\u0432\u043d\u043e\u0439 \u043c\u0430\u043a\u0441\u0438\u043c\u0443\u043c" in response.text
    assert "\u0414\u043d\u0435\u0432\u043d\u043e\u0439 \u043c\u0438\u043d\u0438\u043c\u0443\u043c" in response.text
    assert "\u0414\u0435\u043d\u044c \u00b7 1D" in response.text
    assert "\u041d\u0435\u0434\u0435\u043b\u044f \u00b7 1W" in response.text
    assert "\u041c\u0435\u0441\u044f\u0446 \u00b7 1M" in response.text
    assert 'data-market-current-line' in response.text
    assert 'data-market-current-hit' in response.text
    assert 'data-market-distance-bar' in response.text
    assert 'renderMarketOhlcReadout' in response.text
    assert 'attachInteractiveMarketCharts' in response.text
    assert 'data-market-ohlc-readout' in response.text
    assert 'data-market-crosshair-x' in response.text
    assert 'data-market-range-toolbar' in response.text
    assert 'data-market-range-button' in response.text
    assert 'data-market-level-legend' in response.text
    assert 'data-market-level-detail' in response.text
    assert 'data-market-overlay-line' in response.text
    assert 'data-market-level-button' in response.text
    assert 'data-market-measure-readout' in response.text
    assert 'data-market-measure-layer' in response.text
    assert 'data-market-measure-line' in response.text
    assert "Confidence decomposition" in response.text
    assert "Similar historical setups" in response.text
    assert 'data-surface-state-strip="signal"' in response.text
    assert 'data-root-switch' in response.text
    assert 'data-market-panel' in response.text
    assert 'data-market-signal-id' in response.text
    assert "__imoexMarketLiveRefreshStop" in response.text
    assert "marketLiveRefreshTimer" in response.text
    assert "workflow-button" in response.text
    assert 'id="signal-journal-form"' in response.text
    assert 'id="signal-page-data"' in response.text


def test_workspace_watchlist_compare_and_signal_detail_endpoints(client: TestClient) -> None:
    workspace = client.get("/api/v1/workspace", params={"root": "Si"})
    assert workspace.status_code == 200
    signal_id = workspace.json()["focus_signal"]["signal_id"]

    create_watch = client.post(
        "/api/v1/workspace/watchlist",
        json={"root_code": "Si", "signal_id": signal_id, "note": "Morning priority"},
    )
    assert create_watch.status_code == 200
    watchlist = create_watch.json()
    assert watchlist
    assert watchlist[0]["root_code"] == "Si"
    assert watchlist[0]["note"] == "Morning priority"
    assert watchlist[0]["priority_rank"] == 1
    assert watchlist[0]["focus_reason"] == "Morning priority"
    assert watchlist[0]["review_state"] == "reviewed_today"
    assert watchlist[0]["last_reviewed_at"]

    get_watch = client.get("/api/v1/workspace/watchlist")
    assert get_watch.status_code == 200
    watch_items = get_watch.json()
    assert watch_items
    assert watch_items[0]["priority_rank"] == 1
    assert watch_items[0]["focus_reason"] == "Morning priority"
    watch_key = watch_items[0]["watch_key"]

    create_root_watch = client.post(
        "/api/v1/workspace/watchlist",
        json={"root_code": "BR", "note": "Root follow-up"},
    )
    assert create_root_watch.status_code == 200
    root_watch_items = create_root_watch.json()
    root_watch_key = next(item["watch_key"] for item in root_watch_items if item["signal_id"] is None)

    signal_linked_filter = client.get("/api/v1/workspace/watchlist", params={"linked": "signal"})
    assert signal_linked_filter.status_code == 200
    assert signal_linked_filter.json()
    assert all(item["signal_id"] for item in signal_linked_filter.json())

    root_level_filter = client.get("/api/v1/workspace/watchlist", params={"linked": "root"})
    assert root_level_filter.status_code == 200
    assert root_level_filter.json()
    assert all(item["signal_id"] is None for item in root_level_filter.json())

    root_filter = client.get("/api/v1/workspace/watchlist", params={"root": "BR"})
    assert root_filter.status_code == 200
    assert root_filter.json()
    assert {item["root_code"] for item in root_filter.json()} == {"BR"}

    reviewed_filter = client.get("/api/v1/workspace/watchlist", params={"review_state": "reviewed_today"})
    assert reviewed_filter.status_code == 200
    assert reviewed_filter.json()
    assert all(item["review_state"] == "reviewed_today" for item in reviewed_filter.json())

    workspace_after_watch = client.get("/api/v1/workspace", params={"root": "Si"})
    assert workspace_after_watch.status_code == 200
    review_bundle = workspace_after_watch.json()["review_bundle"]
    assert review_bundle["watchlist_items"] >= 2
    assert review_bundle["reviewed_today_items"] >= 2
    assert "Si" in review_bundle["watched_root_codes"]
    assert review_bundle["tag_suggestions"]
    assert review_bundle["next_review_actions"]

    due_filter = client.get("/api/v1/workspace/watchlist", params={"review_state": "review_due"})
    assert due_filter.status_code == 200
    assert due_filter.json() == []

    review_watch = client.post(f"/api/v1/workspace/watchlist/{watch_key}/review")
    assert review_watch.status_code == 200
    reviewed_items = review_watch.json()
    assert reviewed_items[0]["watch_key"] == watch_key
    assert reviewed_items[0]["review_state"] == "reviewed_today"
    assert reviewed_items[0]["last_reviewed_at"]

    compare = client.get("/api/v1/workspace/compare", params={"root": "Si"})
    assert compare.status_code == 200
    comparison_payload = compare.json()
    assert comparison_payload["root"] == "Si"
    assert comparison_payload["items"]
    assert any(item["horizon"] for item in comparison_payload["items"])

    market_preview = client.get("/api/v1/workspace/market-preview", params={"root": "Si"})
    assert market_preview.status_code == 200
    market_payload = market_preview.json()
    assert market_payload["root_code"] == "Si"
    assert market_payload["daily"]["points"]
    assert market_payload["weekly"]["points"]
    assert market_payload["monthly"]["points"]
    assert market_payload["daily"]["overlays"]
    assert {item["key"] for item in market_payload["daily"]["overlays"]} >= {"entry", "invalidation", "target"}

    diff = client.get(f"/api/v1/workspace/signals/{signal_id}/diff")
    assert diff.status_code == 200
    diff_payload = diff.json()
    assert diff_payload["signal_id"] == signal_id
    assert "summary" in diff_payload

    decision_log = client.get(f"/api/v1/workspace/signals/{signal_id}/decision-log")
    assert decision_log.status_code == 200
    timeline = decision_log.json()
    assert timeline
    assert "kind" in timeline[0]
    assert "title" in timeline[0]

    delete_watch = client.delete(f"/api/v1/workspace/watchlist/{watch_key}")
    assert delete_watch.status_code == 200
    assert delete_watch.json()
    delete_root_watch = client.delete(f"/api/v1/workspace/watchlist/{root_watch_key}")
    assert delete_root_watch.status_code == 200
    assert delete_root_watch.json() == []


def test_workspace_snapshot_omits_market_snapshot_when_live_data_is_unavailable(
    client_without_market_data: TestClient,
) -> None:
    workspace = client_without_market_data.get("/api/v1/workspace", params={"root": "Si"})

    assert workspace.status_code == 200
    payload = workspace.json()
    selected_pulse = next(item for item in payload["pulses"] if item["root_code"] == "Si")
    assert selected_pulse["current_price"] is None
    assert selected_pulse["price_change_pct"] is None
    assert payload["market_snapshot"] is None

    signal_id = payload["focus_signal"]["signal_id"]
    signal_snapshot = client_without_market_data.get(f"/api/v1/workspace/signals/{signal_id}")
    assert signal_snapshot.status_code == 200
    assert signal_snapshot.json()["market_snapshot"] is None

    market_preview = client_without_market_data.get("/api/v1/workspace/market-preview", params={"root": "Si"})
    assert market_preview.status_code == 200
    assert market_preview.json() is None


def test_workspace_page_renders_market_unavailable_panel_when_live_data_is_unavailable(
    client_without_market_data: TestClient,
) -> None:
    workspace = client_without_market_data.get("/workspace", params={"root": "Si"})

    assert workspace.status_code == 200
    assert 'data-market-panel' in workspace.text
    assert 'data-surface-state-strip="workspace"' in workspace.text
    assert "\u0413\u0440\u0430\u0444\u0438\u043a\u0438 \u0441\u043a\u0440\u044b\u0442\u044b" in workspace.text

    signal_id = client_without_market_data.get("/api/v1/workspace", params={"root": "Si"}).json()["focus_signal"]["signal_id"]
    signal_page = client_without_market_data.get(f"/workspace/signals/{signal_id}")
    assert signal_page.status_code == 200
    assert 'data-market-panel' in signal_page.text
    assert 'data-surface-state-strip="signal"' in signal_page.text
    assert "\u0413\u0440\u0430\u0444\u0438\u043a\u0438 \u0441\u043a\u0440\u044b\u0442\u044b" in signal_page.text


def test_council_and_runtime_pages_render_surface_state_strip(client_without_market_data: TestClient) -> None:
    council = client_without_market_data.get("/workspace/council", params={"root": "Si"})
    assert council.status_code == 200
    assert 'data-surface-state-strip="council"' in council.text
    assert (
        "\u0441\u0442\u0440\u0430\u043d\u0438\u0446\u0430 \u0441\u043e\u0432\u0435\u0442\u0430 "
        "\u0447\u0435\u0441\u0442\u043d\u043e \u043f\u043e\u043a\u0430\u0437\u044b\u0432\u0430\u0435\u0442"
    ) in council.text

    runtime = client_without_market_data.get("/workspace/runtime", params={"root": "Si"})
    assert runtime.status_code == 200
    assert 'data-surface-state-strip="runtime"' in runtime.text
    assert "\u0421\u043e\u0441\u0442\u043e\u044f\u043d\u0438\u0435 runtime" in runtime.text


def test_runtime_control_panel_endpoints_support_update_reset_and_audit(client: TestClient) -> None:
    snapshot = client.get("/api/v1/runtime/control-panel")
    assert snapshot.status_code == 200
    payload = snapshot.json()
    assert payload["model_routes"]
    assert payload["role_prompts"]
    assert payload["freshness_policy"]["fresh_max_seconds"] >= 1

    update_route = client.post(
        "/api/v1/runtime/control-panel/model-route",
        json={
            "role_key": "skeptic",
            "owner": "OpenAI",
            "product": "ChatGPT",
            "model": "gpt-5.4-mini",
            "control_mode": "editable",
            "detail": "Stress-test skeptic route",
        },
    )
    assert update_route.status_code == 200
    updated_payload = update_route.json()
    skeptic_route = next(item for item in updated_payload["model_routes"] if item["role_key"] == "skeptic")
    assert skeptic_route["model"] == "gpt-5.4-mini"
    assert any(event["action"] == "update" for event in updated_payload["audit_trail"])

    prompt_template_v1 = (
        "Role={role_label}\n"
        "Root={root_code}\n"
        "Summary={signal_summary}\n"
        "Confidence={confidence_final}\n"
        "Skeptic={skeptic_score}\n"
        "Packet={role_context_packet}\n"
        "Task=challenge the thesis but stay in decision support mode"
    )
    invalid_prompt_template = "Role={role_label}\nRoot={root_code}\nPacket={role_context_packet}\nMissing={missing_field}"
    prompt_template_v2 = (
        "Role={role_label}\n"
        "Root={root_code}\n"
        "Summary={signal_summary}\n"
        "Confidence={confidence_final}\n"
        "Skeptic={skeptic_score}\n"
        "Packet={role_context_packet}\n"
        "Detail=review\n"
        "Task=stress test the idea without execution instructions"
    )

    update_prompt = client.post(
        "/api/v1/runtime/control-panel/role-prompt",
        json={
            "role_key": "skeptic",
            "prompt_template": prompt_template_v1,
            "control_mode": "editable",
            "detail": "Stress-test skeptic prompt",
        },
    )
    assert update_prompt.status_code == 200, update_prompt.text
    prompt_payload = update_prompt.json()
    skeptic_prompt = next(item for item in prompt_payload["role_prompts"] if item["role_key"] == "skeptic")
    assert skeptic_prompt["prompt_template"] == prompt_template_v1
    assert "root_code" in skeptic_prompt["variables"]
    assert skeptic_prompt["default_prompt_template"]
    assert skeptic_prompt["current_version_id"]
    assert skeptic_prompt["version_history"]
    assert any(version["version_id"] == skeptic_prompt["current_version_id"] for version in skeptic_prompt["version_history"])
    assert any(event["category"] == "role_prompt" for event in prompt_payload["audit_trail"])
    saved_version_id = skeptic_prompt["current_version_id"]

    diff_prompt = client.post(
        "/api/v1/runtime/control-panel/role-prompt/diff",
        params={"root": "Si"},
        json={
            "role_key": "skeptic",
            "prompt_template": invalid_prompt_template,
            "control_mode": "fixed",
            "detail": "Diff preview skeptic prompt",
        },
    )
    assert diff_prompt.status_code == 200
    diff_payload = diff_prompt.json()
    assert diff_payload["role_key"] == "skeptic"
    assert diff_payload["has_changes"] is True
    assert diff_payload["can_save"] is False
    assert diff_payload["baseline_version_id"] == saved_version_id
    assert diff_payload["baseline_label"] == "approved_version"
    assert diff_payload["release_note_preview"]
    assert any(line["kind"] == "add" for line in diff_payload["lines"])
    assert "missing_field" in diff_payload["unresolved_variables"]
    assert any(issue["severity"] == "blocking" for issue in diff_payload["validation_issues"])
    assert diff_payload["before_rendered_prompt"]
    assert "Si" in diff_payload["before_rendered_prompt"]
    assert diff_payload["after_rendered_prompt"]

    invalid_save = client.post(
        "/api/v1/runtime/control-panel/role-prompt",
        json={
            "role_key": "skeptic",
            "prompt_template": invalid_prompt_template,
            "control_mode": "fixed",
            "detail": "Invalid skeptic prompt",
        },
    )
    assert invalid_save.status_code == 400
    assert "unsupported placeholders" in invalid_save.text.lower()

    update_prompt_v2 = client.post(
        "/api/v1/runtime/control-panel/role-prompt",
        json={
            "role_key": "skeptic",
            "prompt_template": prompt_template_v2,
            "control_mode": "fixed",
            "detail": "Updated skeptic prompt again",
        },
    )
    assert update_prompt_v2.status_code == 200
    updated_v2_payload = update_prompt_v2.json()
    skeptic_prompt_v2 = next(item for item in updated_v2_payload["role_prompts"] if item["role_key"] == "skeptic")
    assert skeptic_prompt_v2["prompt_template"] == prompt_template_v2
    assert skeptic_prompt_v2["control_mode"] == "fixed"
    assert skeptic_prompt_v2["approval_state"] == "pending_approval"
    assert skeptic_prompt_v2["pending_version_id"]
    assert skeptic_prompt_v2["approved_version_id"] == saved_version_id
    assert skeptic_prompt_v2["effective_prompt_template"] == prompt_template_v1
    assert skeptic_prompt_v2["version_history"]
    assert any(item["lifecycle_state"] == "draft" for item in skeptic_prompt_v2["version_history"])
    assert any(item["lifecycle_state"] == "approved" for item in skeptic_prompt_v2["version_history"])
    assert any(item["release_note"] for item in skeptic_prompt_v2["version_history"])

    approve_prompt = client.post(
        "/api/v1/runtime/control-panel/role-prompt/approve",
        json={
            "role_key": "skeptic",
            "version_id": skeptic_prompt_v2["pending_version_id"],
        },
    )
    assert approve_prompt.status_code == 200
    approved_prompt_payload = approve_prompt.json()
    approved_skeptic_prompt = next(item for item in approved_prompt_payload["role_prompts"] if item["role_key"] == "skeptic")
    assert approved_skeptic_prompt["prompt_template"] == prompt_template_v2
    assert approved_skeptic_prompt["effective_prompt_template"] == prompt_template_v2
    assert approved_skeptic_prompt["pending_version_id"] is None
    assert approved_skeptic_prompt["approval_state"] == "approved"
    assert any(item["lifecycle_state"] == "superseded" for item in approved_skeptic_prompt["version_history"])
    assert any(
        event["category"] == "role_prompt" and event["action"] == "approve"
        for event in approved_prompt_payload["audit_trail"]
    )

    restore_prompt = client.post(
        "/api/v1/runtime/control-panel/role-prompt/restore",
        json={"role_key": "skeptic", "version_id": saved_version_id},
    )
    assert restore_prompt.status_code == 200
    restore_prompt_payload = restore_prompt.json()
    restored_skeptic_prompt = next(item for item in restore_prompt_payload["role_prompts"] if item["role_key"] == "skeptic")
    assert restored_skeptic_prompt["prompt_template"] == prompt_template_v1
    assert restored_skeptic_prompt["control_mode"] == "editable"
    assert restored_skeptic_prompt["effective_prompt_template"] == prompt_template_v2
    assert restored_skeptic_prompt["pending_version_id"]
    assert restored_skeptic_prompt["approval_state"] == "pending_approval"
    assert any(
        event["category"] == "role_prompt" and event["action"] == "draft_restore"
        for event in restore_prompt_payload["audit_trail"]
    )

    approve_restored_prompt = client.post(
        "/api/v1/runtime/control-panel/role-prompt/approve",
        json={
            "role_key": "skeptic",
            "version_id": restored_skeptic_prompt["pending_version_id"],
        },
    )
    assert approve_restored_prompt.status_code == 200
    approve_restored_payload = approve_restored_prompt.json()
    approve_restored_skeptic = next(
        item for item in approve_restored_payload["role_prompts"] if item["role_key"] == "skeptic"
    )
    assert approve_restored_skeptic["prompt_template"] == prompt_template_v1
    assert approve_restored_skeptic["effective_prompt_template"] == prompt_template_v1
    assert approve_restored_skeptic["pending_version_id"] is None
    assert approve_restored_skeptic["control_mode"] == "editable"

    update_policy = client.post(
        "/api/v1/runtime/control-panel/freshness-policy",
        json={
            "fresh_max_seconds": 45,
            "aging_max_seconds": 240,
            "stale_max_seconds": 1200,
            "degraded_max_seconds": 5400,
        },
    )
    assert update_policy.status_code == 200
    policy_payload = update_policy.json()
    assert policy_payload["freshness_policy"]["fresh_max_seconds"] == 45
    assert any(event["category"] == "freshness_policy" for event in policy_payload["audit_trail"])

    reset_route = client.post("/api/v1/runtime/control-panel/model-route/reset")
    assert reset_route.status_code == 200
    reset_payload = reset_route.json()
    skeptic_route = next(item for item in reset_payload["model_routes"] if item["role_key"] == "skeptic")
    assert skeptic_route["model"] != "gpt-5.4-mini"
    assert any(event["action"] == "reset" for event in reset_payload["audit_trail"])

    reset_prompt = client.post("/api/v1/runtime/control-panel/role-prompt/reset")
    assert reset_prompt.status_code == 200
    reset_prompt_payload = reset_prompt.json()
    skeptic_prompt = next(item for item in reset_prompt_payload["role_prompts"] if item["role_key"] == "skeptic")
    assert "Сначала ищи сильнейший сценарий отказа" in skeptic_prompt["prompt_template"]
    assert "skeptic_verdict: pass | soft_fail | reject | human_review" in skeptic_prompt["prompt_template"]
    assert "role_context_packet" in skeptic_prompt["variables"]
    assert any(event["category"] == "role_prompt" and event["action"] == "reset" for event in reset_prompt_payload["audit_trail"])

    rendered_snapshot = client.get("/api/v1/runtime/control-panel", params={"root": "Si"})
    assert rendered_snapshot.status_code == 200
    rendered_payload = rendered_snapshot.json()
    rendered_skeptic = next(item for item in rendered_payload["role_prompts"] if item["role_key"] == "skeptic")
    rendered_roll = next(item for item in rendered_payload["role_prompts"] if item["role_key"] == "oi_roll")
    assert rendered_skeptic["rendered_prompt"]
    assert rendered_skeptic["effective_rendered_prompt"]
    assert "Si" in rendered_skeptic["rendered_prompt"]
    assert "packet" in rendered_skeptic["rendered_prompt"]
    assert "Confidence" in rendered_skeptic["rendered_prompt"]
    assert "roll" in rendered_roll["rendered_prompt"].lower()
    assert "наблюдаю" in rendered_skeptic["rendered_prompt"]
    assert "активен" in rendered_skeptic["rendered_prompt"]


def test_runtime_control_page_renders_html(client: TestClient) -> None:
    response = client.get("/workspace/runtime", params={"root": "Si"})

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert 'lang="ru"' in response.text
    assert "Пульт управления runtime" in response.text
    assert "Редактируемая маршрутизация ролей" in response.text
    assert "Промпты участников совета" in response.text
    assert "Политика актуальности" in response.text
    assert "Журнал изменений" in response.text
    assert 'data-surface-state-strip="runtime"' in response.text
    assert 'id="runtime-admin-key"' in response.text
    assert 'data-runtime-admin-key-form' in response.text
    assert 'data-runtime-admin-key-input' in response.text
    assert 'data-runtime-admin-key-clear' in response.text
    assert 'data-runtime-admin-key-state' in response.text
    assert 'imoex_admin_key' in response.text
    assert 'X-IMOEX-Admin-Key' in response.text
    assert "__imoexMarketLiveRefreshStop" in response.text
    assert "document.write" not in response.text
    assert "role_key" in response.text
    assert 'id="runtime-control-data"' in response.text
    assert 'data-runtime-policy-form' in response.text
    assert 'id="runtime-prompts"' in response.text
    assert 'data-runtime-prompt-form' in response.text
    assert 'data-runtime-prompt-template' in response.text
    assert 'data-runtime-prompt-preview' in response.text
    assert 'data-runtime-prompt-diff-button' in response.text
    assert 'data-runtime-prompt-diff' in response.text
    assert 'data-runtime-prompt-diff-approval' in response.text
    assert 'data-runtime-prompt-validation' in response.text
    assert 'data-runtime-prompt-history' in response.text
    assert 'data-runtime-prompt-restore' in response.text
    assert 'data-runtime-prompt-current-version' in response.text
    assert 'data-runtime-prompt-approved-version' in response.text
    assert 'data-runtime-prompt-approval-state' in response.text
    assert 'data-runtime-prompt-approval-reasons' in response.text
    assert 'data-runtime-prompt-dismiss' in response.text
    assert 'data-runtime-prompt-version-state' in response.text
    assert 'data-runtime-prompt-release-note' in response.text


def test_favicon_does_not_pollute_browser_console(client: TestClient) -> None:
    response = client.get("/favicon.ico")

    assert response.status_code == 204


def test_risky_editable_prompt_change_requires_approval(client: TestClient) -> None:
    live_prompt = (
        "Role={role_label}\n"
        "Root={root_code}\n"
        "Summary={signal_summary}\n"
        "Confidence={confidence_final}\n"
        "Skeptic={skeptic_score}\n"
        "Packet={role_context_packet}\n"
        "Task=blend the council into one operator-facing final call"
    )
    risky_prompt = (
        "Role={role_label}\n"
        "Desk={root_code}\n"
        "Situation={signal_summary}\n"
        "Confidence={confidence_final}\n"
        "Skeptic={skeptic_score}\n"
        "Packet={role_context_packet}\n"
        "WhyNow={why_now}\n"
        "Task=rebuild the arbiter narrative as a fresh decision memo with new framing"
    )

    save_live = client.post(
        "/api/v1/runtime/control-panel/role-prompt",
        json={
            "role_key": "arbiter",
            "prompt_template": live_prompt,
            "control_mode": "editable",
            "detail": "Live arbiter prompt",
        },
    )
    assert save_live.status_code == 200

    diff = client.post(
        "/api/v1/runtime/control-panel/role-prompt/diff",
        params={"root": "Si"},
        json={
            "role_key": "arbiter",
            "prompt_template": risky_prompt,
            "control_mode": "editable",
            "detail": "Risky arbiter rewrite",
        },
    )
    assert diff.status_code == 200
    diff_payload = diff.json()
    assert diff_payload["approval_required"] is True
    assert diff_payload["can_save"] is True
    assert diff_payload["approval_reasons"]
    assert "approval trigger" in diff_payload["summary"].lower()
    assert diff_payload["baseline_label"] == "approved_version"
    assert diff_payload["release_note_preview"]

    save_risky = client.post(
        "/api/v1/runtime/control-panel/role-prompt",
        json={
            "role_key": "arbiter",
            "prompt_template": risky_prompt,
            "control_mode": "editable",
            "detail": "Risky arbiter rewrite",
        },
    )
    assert save_risky.status_code == 200
    save_payload = save_risky.json()
    arbiter_prompt = next(item for item in save_payload["role_prompts"] if item["role_key"] == "arbiter")
    assert arbiter_prompt["approval_state"] == "pending_approval"
    assert arbiter_prompt["pending_version_id"]
    assert arbiter_prompt["effective_prompt_template"] == live_prompt
    assert arbiter_prompt["prompt_template"] == risky_prompt
    assert arbiter_prompt["approval_reasons"]
    assert any(item["lifecycle_state"] == "draft" for item in arbiter_prompt["version_history"])


def test_pending_draft_can_be_dismissed_without_resetting_effective_prompt(client: TestClient) -> None:
    live_prompt = (
        "Role={role_label}\n"
        "Root={root_code}\n"
        "Summary={signal_summary}\n"
        "Confidence={confidence_final}\n"
        "Skeptic={skeptic_score}\n"
        "Packet={role_context_packet}\n"
        "Task=live skeptic guardrail"
    )
    draft_prompt = (
        "Role={role_label}\n"
        "Root={root_code}\n"
        "Summary={signal_summary}\n"
        "Confidence={confidence_final}\n"
        "Skeptic={skeptic_score}\n"
        "Packet={role_context_packet}\n"
        "Detail=review\n"
        "Task=pending skeptic rewrite"
    )

    save_live = client.post(
        "/api/v1/runtime/control-panel/role-prompt",
        json={
            "role_key": "skeptic",
            "prompt_template": live_prompt,
            "control_mode": "editable",
            "detail": "Live skeptic prompt",
        },
    )
    assert save_live.status_code == 200

    save_draft = client.post(
        "/api/v1/runtime/control-panel/role-prompt",
        json={
            "role_key": "skeptic",
            "prompt_template": draft_prompt,
            "control_mode": "fixed",
            "detail": "Pending skeptic rewrite",
        },
    )
    assert save_draft.status_code == 200
    draft_payload = save_draft.json()
    skeptic_prompt = next(item for item in draft_payload["role_prompts"] if item["role_key"] == "skeptic")
    assert skeptic_prompt["pending_version_id"]

    dismiss = client.post(
        "/api/v1/runtime/control-panel/role-prompt/dismiss",
        json={
            "role_key": "skeptic",
            "version_id": skeptic_prompt["pending_version_id"],
        },
    )
    assert dismiss.status_code == 200
    dismiss_payload = dismiss.json()
    dismissed_skeptic = next(item for item in dismiss_payload["role_prompts"] if item["role_key"] == "skeptic")
    assert dismissed_skeptic["pending_version_id"] is None
    assert dismissed_skeptic["prompt_template"] == live_prompt
    assert dismissed_skeptic["effective_prompt_template"] == live_prompt
    assert dismissed_skeptic["approval_state"] == "live"
    assert any(item["lifecycle_state"] == "dismissed" for item in dismissed_skeptic["version_history"])
    assert any(item["action"] == "dismiss" for item in dismissed_skeptic["version_history"])
    assert any(
        event["category"] == "role_prompt" and event["action"] == "dismiss"
        for event in dismiss_payload["audit_trail"]
    )


def test_council_page_uses_effective_prompt_until_draft_is_approved(client: TestClient) -> None:
    prompt_template_live = (
        "Role={role_label}\n"
        "Root={root_code}\n"
        "Summary={signal_summary}\n"
        "Confidence={confidence_final}\n"
        "Skeptic={skeptic_score}\n"
        "Packet={role_context_packet}\n"
        "Task=live skeptic packet"
    )
    prompt_template_draft = (
        "Role={role_label}\n"
        "Root={root_code}\n"
        "Summary={signal_summary}\n"
        "Confidence={confidence_final}\n"
        "Skeptic={skeptic_score}\n"
        "Packet={role_context_packet}\n"
        "Task=draft skeptic packet pending approval"
    )

    save_live = client.post(
        "/api/v1/runtime/control-panel/role-prompt",
        json={
            "role_key": "skeptic",
            "prompt_template": prompt_template_live,
            "control_mode": "editable",
            "detail": "Live skeptic prompt",
        },
    )
    assert save_live.status_code == 200

    save_draft = client.post(
        "/api/v1/runtime/control-panel/role-prompt",
        json={
            "role_key": "skeptic",
            "prompt_template": prompt_template_draft,
            "control_mode": "fixed",
            "detail": "Pending skeptic draft",
        },
    )
    assert save_draft.status_code == 200
    draft_payload = save_draft.json()
    skeptic_prompt = next(item for item in draft_payload["role_prompts"] if item["role_key"] == "skeptic")
    assert skeptic_prompt["pending_version_id"]

    council_before_approve = client.get("/workspace/council", params={"root": "Si"})
    assert council_before_approve.status_code == 200
    assert "live skeptic packet" in council_before_approve.text
    assert "draft skeptic packet pending approval" not in council_before_approve.text
    assert 'data-council-prompt-status' in council_before_approve.text

    approve = client.post(
        "/api/v1/runtime/control-panel/role-prompt/approve",
        json={
            "role_key": "skeptic",
            "version_id": skeptic_prompt["pending_version_id"],
        },
    )
    assert approve.status_code == 200

    council_after_approve = client.get("/workspace/council", params={"root": "Si"})
    assert council_after_approve.status_code == 200
    assert "draft skeptic packet pending approval" in council_after_approve.text


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
            "tags": ["great context", "data issue"],
        },
    )
    assert create_response.status_code == 200
    assert create_response.json()["tags"] == ["great context", "data issue"]

    response = client.get("/api/v1/workspace/journal", params={"root": "Si", "kind": "thesis"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["selected_root"] == "Si"
    assert payload["selected_kind"] == "thesis"
    assert payload["decision_log"]
    assert "decision_summary" in payload["decision_log"][0]
    assert payload["entries"]
    assert payload["entries"][0]["entry"]["title"] == "Opening thesis"
    assert payload["entries"][0]["entry"]["tags"] == ["great context", "data issue"]
    assert payload["tag_counts"]
    assert payload["tag_counts"][0]["tag"] in {"data issue", "great context"}

    tag_response = client.get("/api/v1/workspace/journal", params={"root": "Si", "tag": "data issue"})
    assert tag_response.status_code == 200
    tag_payload = tag_response.json()
    assert tag_payload["selected_tag"] == "data issue"
    assert tag_payload["entries"]
    assert all("data issue" in item["entry"]["tags"] for item in tag_payload["entries"])

    missing_tag_response = client.get("/api/v1/workspace/journal", params={"root": "Si", "tag": "missing tag"})
    assert missing_tag_response.status_code == 200
    assert missing_tag_response.json()["entries"] == []


def _legacy_workspace_journal_page_renders_html(client: TestClient) -> None:
    workspace = client.get("/api/v1/workspace", params={"root": "Si"})
    signal_id = workspace.json()["focus_signal"]["signal_id"]
    client.post(
        f"/api/v1/journal/{signal_id}",
        json={
            "kind": "risk_note",
            "title": "Main risk",
            "note": "Roll share is rising faster than expected.",
            "author": "test",
            "tags": ["late", "data issue"],
        },
    )

    response = client.get("/workspace/journal", params={"root": "Si", "tag": "data issue"})

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert 'lang="ru"' in response.text
    assert "Память торговой системы" in response.text
    assert "Лента журнала" in response.text
    assert "Ð–ÑƒÑ€Ð½Ð°Ð» Ñ€ÐµÑˆÐµÐ½Ð¸Ð¹" in response.text
    assert 'id="journal-workspace-data"' in response.text


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
    assert "\u041f\u0430\u043c\u044f\u0442\u044c \u0442\u043e\u0440\u0433\u043e\u0432\u043e\u0439 \u0441\u0438\u0441\u0442\u0435\u043c\u044b" in response.text
    assert "\u0416\u0443\u0440\u043d\u0430\u043b \u0440\u0435\u0448\u0435\u043d\u0438\u0439" in response.text
    assert "\u041b\u0435\u043d\u0442\u0430 \u0436\u0443\u0440\u043d\u0430\u043b\u0430" in response.text
    assert 'data-journal-tag-filters' in response.text
    assert 'data-journal-tag-drilldown' in response.text
    assert "data issue" in response.text
    assert "Tag quality drill-down" in response.text
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
    assert "\u041f\u043e\u0434\u043f\u0438\u0441\u0430\u043d\u043d\u044b\u0435 \u0441\u0435\u0440\u0438\u0438" in response.text
    assert "\u041f\u043e\u0434\u043f\u0438\u0441\u0430\u043d\u043d\u044b\u0435 \u0433\u043e\u0440\u0438\u0437\u043e\u043d\u0442\u044b" in response.text
    assert "\u0421\u043e\u0431\u044b\u0442\u0438\u044f Telegram" in response.text
    assert "\u041b\u0438\u043c\u0438\u0442 \u0434\u0430\u0439\u0434\u0436\u0435\u0441\u0442\u0430" in response.text
    assert "\u041c\u0438\u043d. \u043f\u0440\u0438\u043e\u0440\u0438\u0442\u0435\u0442" in response.text
    assert "\u041d\u0430\u0447\u0430\u043b\u043e \u0442\u0438\u0445\u0438\u0445 \u0447\u0430\u0441\u043e\u0432" in response.text
    assert "\u041a\u043e\u043d\u0435\u0446 \u0442\u0438\u0445\u0438\u0445 \u0447\u0430\u0441\u043e\u0432" in response.text
    assert "\u041f\u043e\u043b\u0438\u0442\u0438\u043a\u0430 \u0442\u0438\u0445\u0438\u0445 \u0447\u0430\u0441\u043e\u0432" in response.text
    assert 'data-root-switch' in response.text
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
    assert "reason_label" in csv_response.text
    assert '"digest"' in csv_response.text
    assert "Sent because delivery was allowed and Telegram accepted the message." in csv_response.text

    jsonl_response = client.get(
        "/api/v1/workspace/delivery/activity/export",
        params={"root": "Si", "activity_event_kind": "digest", "export_format": "jsonl"},
    )
    assert jsonl_response.status_code == 200
    assert "application/x-ndjson" in jsonl_response.headers["content-type"]
    assert '"event_kind": "digest"' in jsonl_response.text
    assert '"reason_label": "Sent because delivery was allowed and Telegram accepted the message."' in jsonl_response.text


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


def test_runtime_control_page_can_be_disabled_by_feature_flag(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(settings, "feature_flags_json", '{"dashboard_ui": false}')

    response = client.get("/workspace/runtime")

    assert response.status_code == 404
