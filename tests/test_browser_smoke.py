from __future__ import annotations

import errno
import json
from pathlib import Path
from types import SimpleNamespace

from scripts.browser_smoke import (
    _build_parser,
    _browser_startup_blocker_message,
    _is_browser_startup_permission_error,
    _planned_checks,
    _write_failure_payload,
)


def test_browser_smoke_classifies_permission_denied_as_startup_blocker() -> None:
    exc = PermissionError(errno.EACCES, "Access is denied")

    assert _is_browser_startup_permission_error(exc) is True
    assert _is_browser_startup_permission_error(RuntimeError("browserType.launch: Access is denied")) is True
    assert _is_browser_startup_permission_error(RuntimeError("browserType.launch: permission denied")) is True
    assert _is_browser_startup_permission_error(RuntimeError("browserType.launch: timeout")) is False

    message = _browser_startup_blocker_message(exc, channel="msedge")

    assert "browser startup is blocked by local OS permissions" in message
    assert "channel=msedge" in message
    assert "release blocker" in message
    assert "draft/local preflight" in message


def test_browser_smoke_failure_payload_is_machine_readable(tmp_path: Path) -> None:
    output_path = tmp_path / "browser-smoke.json"

    _write_failure_payload(
        output_path=output_path,
        args=SimpleNamespace(root="Si"),
        secondary_root="BR",
        base_url="http://127.0.0.1:8123",
        database_path=tmp_path / "browser.db",
        checks=["workspace_opened"],
        failure_code="browser_startup_blocked",
        message="startup blocked",
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["status"] == "fail"
    assert payload["failure_code"] == "browser_startup_blocked"
    assert payload["root"] == "Si"
    assert payload["secondary_root"] == "BR"
    assert payload["checks"] == []
    assert payload["planned_checks"] == ["workspace_opened"]


def test_browser_smoke_headed_flag_disables_headless_mode() -> None:
    parser = _build_parser()

    assert parser.parse_args([]).headless is True
    assert parser.parse_args(["--headed"]).headless is False


def test_browser_smoke_planned_checks_include_daily_workflow_and_chart_evidence() -> None:
    checks = _planned_checks(secondary_root="BR", skip_chart_fixture=False)

    assert "workspace_morning_brief_visible" in checks
    assert "workspace_watchlist_workbench_visible" in checks
    assert "workspace_root_switch" in checks
    assert "market_fixture_day_week_month_charts_visible" in checks
    assert "market_fixture_mobile_no_horizontal_overflow" in checks

    preflight_checks = _planned_checks(secondary_root=None, skip_chart_fixture=True)
    assert "workspace_watchlist_workbench_visible" in preflight_checks
    assert "workspace_root_switch" not in preflight_checks
    assert "market_fixture_day_week_month_charts_visible" not in preflight_checks
