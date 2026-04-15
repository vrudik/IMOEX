from __future__ import annotations

import json
import logging

from libs.runtime.feature_flags import resolved_feature_flags
from libs.runtime.metrics import RuntimeMetricsRegistry
from libs.utils.logging import JsonLogFormatter


def test_json_log_formatter_outputs_structured_payload() -> None:
    formatter = JsonLogFormatter()
    record = logging.LogRecord(
        name="imoex.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="hello",
        args=(),
        exc_info=None,
    )
    record.request_id = "req-1"
    record.path = "/api/v1/roots"

    payload = json.loads(formatter.format(record))

    assert payload["logger"] == "imoex.test"
    assert payload["message"] == "hello"
    assert payload["request_id"] == "req-1"
    assert payload["path"] == "/api/v1/roots"


def test_runtime_metrics_registry_tracks_requests() -> None:
    registry = RuntimeMetricsRegistry()
    registry.record_request(method="GET", path="/api/v1/roots", status_code=200, duration_ms=12.5)
    registry.record_request(method="GET", path="/api/v1/roots", status_code=500, duration_ms=20.0)

    snapshot = registry.snapshot()
    metrics = {item.name: item.value for item in snapshot.metrics}

    assert metrics["http_requests_total"] == 2.0
    assert metrics["http_request_errors_total"] == 1.0
    assert snapshot.route_hits["GET /api/v1/roots"] == 2
    assert snapshot.status_counts["500"] == 1


def test_feature_flags_merge_defaults_and_runtime_overrides(monkeypatch) -> None:
    from libs.utils.config import settings

    monkeypatch.setattr(settings, "feature_flags_json", '{"dashboard_ui": false, "custom_probe": true}')
    flags = resolved_feature_flags()

    assert flags["dashboard_ui"] is False
    assert flags["telegram_delivery"] is True
    assert flags["custom_probe"] is True
