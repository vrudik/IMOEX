from __future__ import annotations

import argparse
import errno
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from textwrap import dedent


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]

    try:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
        from playwright.sync_api import sync_playwright
    except ImportError:
        message = (
            "Playwright is not installed. Install the browser smoke dependency with "
            "`python -m pip install -e .[browser]` and install a browser with "
            "`python -m playwright install chromium`, or run release_check.ps1 with -SkipBrowser for local preflight."
        )
        print(f"[browser-smoke] {message}", file=sys.stderr)
        return 0 if args.allow_missing_dependency else 86

    root_dir = Path(tempfile.gettempdir()) / "imoex-browser-smoke"
    run_id = datetime.now(UTC).strftime("%Y%m%d%H%M%S")
    database_path = root_dir / f"browser-{run_id}.db"
    backups_path = root_dir / f"backups-{run_id}"
    output_path = Path(args.output) if args.output else root_dir / f"browser-smoke-{run_id}.json"
    secondary_root = _secondary_root(primary=args.root, requested=args.secondary_root)
    root_dir.mkdir(parents=True, exist_ok=True)
    backups_path.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["PYTHONPATH"] = f"{repo_root / '.vendor'}{os.pathsep}{repo_root}{os.pathsep}{env.get('PYTHONPATH', '')}"
    env["DATABASE_URL"] = f"sqlite:///{database_path.as_posix()}"
    env["BACKUPS_DIR"] = backups_path.as_posix()
    env["MARKET_DATA_LIVE_ENABLED"] = "false"
    env["MOEX_REFERENCE_AUTO_SYNC_ENABLED"] = "false"
    env["LOG_JSON"] = "false"

    print(f"[browser-smoke] database: {database_path}")
    print(f"[browser-smoke] output: {output_path}")

    _run([sys.executable, "-m", "apps.worker.runner", "recalculate", "--root", args.root], cwd=repo_root, env=env)
    if secondary_root:
        _run(
            [sys.executable, "-m", "apps.worker.runner", "recalculate", "--root", secondary_root],
            cwd=repo_root,
            env=env,
        )

    port = args.port or _find_free_port()
    base_url = f"http://127.0.0.1:{port}"
    server = _start_server(repo_root=repo_root, env=env, port=port)
    checks = _planned_checks(secondary_root=secondary_root, skip_chart_fixture=args.skip_chart_fixture)
    try:
        _wait_for_ready(base_url, timeout_seconds=args.timeout_seconds)
        console_errors: list[str] = []
        page_errors: list[str] = []
        with sync_playwright() as playwright:
            browser, page = _new_browser_page(playwright, args=args, console_errors=console_errors, page_errors=page_errors)

            _workspace_smoke(
                page,
                base_url=base_url,
                root=args.root,
                secondary_root=secondary_root,
                timeout_ms=args.timeout_seconds * 1000,
            )
            _runtime_prompt_smoke(page, base_url=base_url, root=args.root, timeout_ms=args.timeout_seconds * 1000)

            browser.close()

        _stop_server(server)

        if not args.skip_chart_fixture:
            fixture_env = env.copy()
            fixture_dir = _write_market_fixture_sitecustomize(root_dir)
            fixture_env["PYTHONPATH"] = f"{fixture_dir}{os.pathsep}{env['PYTHONPATH']}"
            fixture_env["APP_ENVIRONMENT"] = "browser_smoke"
            fixture_env["MARKET_DATA_LIVE_ENABLED"] = "true"
            chart_port = _find_free_port()
            chart_base_url = f"http://127.0.0.1:{chart_port}"
            chart_server = _start_server(repo_root=repo_root, env=fixture_env, port=chart_port)
            try:
                _wait_for_ready(chart_base_url, timeout_seconds=args.timeout_seconds)
                with sync_playwright() as playwright:
                    browser, page = _new_browser_page(
                        playwright,
                        args=args,
                        console_errors=console_errors,
                        page_errors=page_errors,
                    )
                    _market_chart_smoke(
                        page,
                        base_url=chart_base_url,
                        root=args.root,
                        timeout_ms=args.timeout_seconds * 1000,
                    )
                    if secondary_root:
                        _market_chart_root_switch_smoke(
                            page,
                            secondary_root=secondary_root,
                            timeout_ms=args.timeout_seconds * 1000,
                        )
                    browser.close()

                    browser, page = _new_browser_page(
                        playwright,
                        args=args,
                        console_errors=console_errors,
                        page_errors=page_errors,
                        viewport={"width": 390, "height": 900},
                        is_mobile=True,
                    )
                    _market_mobile_chart_smoke(
                        page,
                        base_url=chart_base_url,
                        root=secondary_root or args.root,
                        timeout_ms=args.timeout_seconds * 1000,
                    )
                    browser.close()
            except Exception:
                _stop_server(chart_server)
                _dump_server_output(chart_server)
                raise
            finally:
                _stop_server(chart_server)

        if console_errors or page_errors:
            raise AssertionError(
                "Browser smoke captured page errors: "
                + json.dumps({"console_errors": console_errors, "page_errors": page_errors}, ensure_ascii=False)
            )

        payload = {
            "generated_at": datetime.now(UTC).isoformat(),
            "root": args.root,
            "secondary_root": secondary_root,
            "base_url": base_url,
            "database_path": str(database_path),
            "status": "pass",
            "checks": checks,
            "planned_checks": checks,
        }
        output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print("[browser-smoke] OK")
        return 0
    except (PlaywrightError, PlaywrightTimeoutError, AssertionError, RuntimeError) as exc:
        if _is_browser_startup_permission_error(exc):
            failure_code = "browser_startup_blocked"
            message = _browser_startup_blocker_message(exc, channel=args.channel)
        else:
            failure_code = "browser_smoke_failed"
            message = str(exc)
        print(f"[browser-smoke] failed: {message}", file=sys.stderr)
        _write_failure_payload(
            output_path=output_path,
            args=args,
            secondary_root=secondary_root,
            base_url=base_url,
            database_path=database_path,
            checks=checks,
            failure_code=failure_code,
            message=message,
        )
        _stop_server(server)
        _dump_server_output(server)
        return 1
    except OSError as exc:
        if not _is_browser_startup_permission_error(exc):
            raise
        message = _browser_startup_blocker_message(exc, channel=args.channel)
        print(f"[browser-smoke] failed: {message}", file=sys.stderr)
        _write_failure_payload(
            output_path=output_path,
            args=args,
            secondary_root=secondary_root,
            base_url=base_url,
            database_path=database_path,
            checks=checks,
            failure_code="browser_startup_blocked",
            message=message,
        )
        _stop_server(server)
        _dump_server_output(server)
        return 1
    finally:
        _stop_server(server)


def _workspace_smoke(page, *, base_url: str, root: str, secondary_root: str | None, timeout_ms: int) -> None:
    page.goto(f"{base_url}/workspace?root={root}", wait_until="domcontentloaded", timeout=timeout_ms)
    page.wait_for_selector('[data-surface-state-strip="workspace"]', timeout=timeout_ms)
    page.wait_for_selector("[data-morning-brief]", timeout=timeout_ms)
    page.wait_for_selector("[data-morning-brief-market]", timeout=timeout_ms)
    page.wait_for_selector("[data-morning-brief-attention]", timeout=timeout_ms)
    page.wait_for_selector("[data-morning-brief-delta]", timeout=timeout_ms)
    page.wait_for_selector("[data-morning-brief-dont-chase]", timeout=timeout_ms)
    page.wait_for_selector("[data-watchlist-workbench]", timeout=timeout_ms)
    page.wait_for_selector("[data-watchlist-workbench-summary]", timeout=timeout_ms)
    page.wait_for_selector("[data-watchlist-filters]", timeout=timeout_ms)
    page.wait_for_function(
        """() => {
          const brief = document.querySelector("[data-morning-brief]");
          return brief
            && brief.textContent.includes("signals-only")
            && !/order routing|autotrading|broker execution/i.test(brief.textContent);
        }""",
        timeout=timeout_ms,
    )
    page.wait_for_function(
        """() => {
          const workbench = document.querySelector("[data-watchlist-workbench]");
          const summaryCards = document.querySelectorAll("[data-watchlist-workbench-summary] article");
          return workbench
            && summaryCards.length >= 4
            && workbench.textContent.includes("Today")
            && workbench.textContent.includes("Operating Queue")
            && !/order routing|autotrading|broker execution/i.test(workbench.textContent);
        }""",
        timeout=timeout_ms,
    )
    page.wait_for_selector("[data-compare-board]", timeout=timeout_ms)
    page.wait_for_selector("[data-market-unavailable]", timeout=timeout_ms)
    if secondary_root:
        _workspace_root_switch_smoke(page, secondary_root=secondary_root, timeout_ms=timeout_ms)
    signal_link = page.locator('a[href^="/workspace/signals/"]').first
    signal_link.wait_for(state="visible", timeout=timeout_ms)
    signal_link.click()
    page.wait_for_selector('[data-surface-state-strip="signal"]', timeout=timeout_ms)


def _workspace_root_switch_smoke(page, *, secondary_root: str, timeout_ms: int) -> None:
    switch = page.locator("[data-root-switch]").first
    switch.wait_for(state="visible", timeout=timeout_ms)
    page.wait_for_function(
        """(root) => Array.from(document.querySelectorAll("[data-root-switch] option"))
        .some((option) => option.value.toUpperCase() === root.toUpperCase())""",
        arg=secondary_root,
        timeout=timeout_ms,
    )
    switch.select_option(secondary_root)
    page.wait_for_function(
        """(root) => {
          const urlRoot = new URL(window.location.href).searchParams.get("root") || "";
          const select = document.querySelector("[data-root-switch]");
          const panel = document.querySelector("[data-market-panel]");
          return select
            && panel
            && select.value.toUpperCase() === root.toUpperCase()
            && urlRoot.toUpperCase() === root.toUpperCase()
            && (panel.dataset.marketRootCode || "").toUpperCase() === root.toUpperCase();
        }""",
        arg=secondary_root,
        timeout=timeout_ms,
    )
    page.wait_for_selector('[data-surface-state-strip="workspace"]', timeout=timeout_ms)
    page.wait_for_selector("[data-compare-board]", timeout=timeout_ms)


def _planned_checks(*, secondary_root: str | None, skip_chart_fixture: bool) -> list[str]:
    checks = [
        "workspace_opened",
        "workspace_morning_brief_visible",
        "workspace_watchlist_workbench_visible",
        "market_unavailable_state_visible",
        "signal_detail_opened",
        "runtime_admin_key_save_clear",
        "runtime_prompt_diff",
        "runtime_prompt_draft_saved",
        "runtime_prompt_draft_dismissed",
    ]
    if secondary_root:
        checks.append("workspace_root_switch")
    if not skip_chart_fixture:
        checks.extend(
            [
                "market_fixture_current_price_visible",
                "market_fixture_day_week_month_charts_visible",
                "market_fixture_chart_measurement",
                "market_fixture_multi_root_switch",
                "market_fixture_mobile_charts_visible",
                "market_fixture_mobile_no_horizontal_overflow",
            ]
        )
    return checks


def _market_chart_smoke(page, *, base_url: str, root: str, timeout_ms: int) -> None:
    page.goto(f"{base_url}/workspace?root={root}", wait_until="domcontentloaded", timeout=timeout_ms)
    page.wait_for_selector('[data-surface-state-strip="workspace"]', timeout=timeout_ms)
    page.wait_for_selector("[data-market-panel] [data-market-current-price]", timeout=timeout_ms)
    page.wait_for_function(
        '() => document.querySelectorAll("[data-market-panel] [data-market-chart-card]").length >= 3',
        timeout=timeout_ms,
    )
    page.wait_for_selector(
        '[data-market-chart-card][data-market-timeframe="1D"] [data-market-current-line]',
        state="attached",
        timeout=timeout_ms,
    )
    page.wait_for_selector(
        '[data-market-chart-card][data-market-timeframe="1W"] [data-market-current-line]',
        state="attached",
        timeout=timeout_ms,
    )
    page.wait_for_selector(
        '[data-market-chart-card][data-market-timeframe="1M"] [data-market-current-line]',
        state="attached",
        timeout=timeout_ms,
    )
    page.wait_for_function(
        '() => document.querySelectorAll("[data-market-panel] [data-market-unavailable]").length === 0',
        timeout=timeout_ms,
    )

    chart = page.locator('[data-market-chart-card][data-market-timeframe="1D"] [data-market-chart-svg]').first
    chart.wait_for(state="visible", timeout=timeout_ms)
    box = chart.bounding_box()
    if box is None:
        raise AssertionError("Market chart SVG did not produce a browser bounding box.")
    start_x = box["x"] + box["width"] * 0.25
    end_x = box["x"] + box["width"] * 0.75
    y = box["y"] + box["height"] * 0.5
    page.mouse.move(start_x, y)
    page.mouse.down()
    page.mouse.move(end_x, y, steps=6)
    page.mouse.up()
    page.wait_for_selector(
        '[data-market-chart-card][data-market-timeframe="1D"] [data-market-measure-readout]',
        timeout=timeout_ms,
    )


def _market_chart_root_switch_smoke(page, *, secondary_root: str, timeout_ms: int) -> None:
    _workspace_root_switch_smoke(page, secondary_root=secondary_root, timeout_ms=timeout_ms)
    page.wait_for_function(
        """(root) => {
          const panel = document.querySelector("[data-market-panel]");
          const price = document.querySelector("[data-market-panel] [data-market-current-price]");
          const charts = document.querySelectorAll("[data-market-panel] [data-market-chart-card]");
          return panel
            && price
            && charts.length >= 3
            && (panel.dataset.marketRootCode || "").toUpperCase() === root.toUpperCase()
            && price.textContent.toUpperCase().includes(root.toUpperCase());
        }""",
        arg=secondary_root,
        timeout=timeout_ms,
    )
    page.wait_for_function(
        '() => document.querySelectorAll("[data-market-panel] [data-market-unavailable]").length === 0',
        timeout=timeout_ms,
    )


def _market_mobile_chart_smoke(page, *, base_url: str, root: str, timeout_ms: int) -> None:
    page.goto(f"{base_url}/workspace?root={root}", wait_until="domcontentloaded", timeout=timeout_ms)
    page.wait_for_selector('[data-surface-state-strip="workspace"]', timeout=timeout_ms)
    page.wait_for_selector("[data-market-panel] [data-market-current-price]", timeout=timeout_ms)
    page.wait_for_function(
        '() => document.querySelectorAll("[data-market-panel] [data-market-chart-card]").length >= 3',
        timeout=timeout_ms,
    )
    page.wait_for_function(
        """() => {
          const cards = Array.from(document.querySelectorAll("[data-market-panel] [data-market-chart-card]"));
          return cards.length >= 3 && cards.every((card) => {
            const rect = card.getBoundingClientRect();
            return rect.width >= 220 && rect.left >= -1 && rect.right <= window.innerWidth + 1;
          });
        }""",
        timeout=timeout_ms,
    )
    page.wait_for_function(
        "() => document.documentElement.scrollWidth <= window.innerWidth + 2",
        timeout=timeout_ms,
    )


def _runtime_prompt_smoke(page, *, base_url: str, root: str, timeout_ms: int) -> None:
    page.goto(f"{base_url}/workspace/runtime?root={root}#runtime-prompts", wait_until="domcontentloaded", timeout=timeout_ms)
    page.wait_for_selector('[data-surface-state-strip="runtime"]', timeout=timeout_ms)
    page.wait_for_selector("[data-runtime-admin-key-form]", timeout=timeout_ms)
    page.locator("[data-runtime-admin-key-input]").fill("browser-smoke-admin-key")
    page.locator('[data-runtime-admin-key-form] button[type="submit"]').click()
    page.wait_for_function(
        '() => window.localStorage.getItem("imoex_admin_key") === "browser-smoke-admin-key"',
        timeout=timeout_ms,
    )
    page.locator("[data-runtime-admin-key-clear]").click()
    page.wait_for_function(
        '() => window.localStorage.getItem("imoex_admin_key") === null',
        timeout=timeout_ms,
    )
    card = page.locator("[data-runtime-prompt-card]").first
    card.wait_for(state="visible", timeout=timeout_ms)

    diff_button = card.locator("[data-runtime-prompt-diff-button]")
    diff_button.click()
    page.wait_for_selector("[data-runtime-prompt-diff]:not([hidden])", timeout=timeout_ms)

    control_mode = card.locator('select[name="control_mode"]')
    control_mode.select_option("fixed")
    template = card.locator("[data-runtime-prompt-template]")
    current_template = template.input_value()
    if "Browser smoke governance note." not in current_template:
        template.fill(current_template.rstrip() + "\n\nBrowser smoke governance note. Keep the prompt signals-only.")
    card.locator('button[type="submit"]').first.click()
    page.wait_for_load_state("domcontentloaded", timeout=timeout_ms)
    page.wait_for_selector("[data-runtime-prompt-dismiss]", timeout=timeout_ms)
    page.locator("[data-runtime-prompt-dismiss]").first.click()
    page.wait_for_function(
        '() => document.querySelectorAll("[data-runtime-prompt-dismiss]").length === 0',
        timeout=timeout_ms,
    )


def _new_browser_page(
    playwright,
    *,
    args,
    console_errors: list[str],
    page_errors: list[str],
    viewport: dict[str, int] | None = None,
    is_mobile: bool = False,
):
    launch_kwargs: dict[str, object] = {"headless": args.headless}
    if args.channel:
        launch_kwargs["channel"] = args.channel
    browser = playwright.chromium.launch(**launch_kwargs)
    page_kwargs: dict[str, object] = {"viewport": viewport or {"width": 1440, "height": 1000}}
    if is_mobile:
        page_kwargs.update({"is_mobile": True, "has_touch": True})
    page = browser.new_page(**page_kwargs)
    page.on(
        "console",
        lambda message: console_errors.append(message.text) if message.type == "error" else None,
    )
    page.on("pageerror", lambda error: page_errors.append(str(error)))
    return browser, page


def _is_browser_startup_permission_error(exc: BaseException) -> bool:
    if isinstance(exc, PermissionError) or getattr(exc, "winerror", None) == 5 or getattr(exc, "errno", None) in {
        errno.EACCES,
        errno.EPERM,
    }:
        return True
    message = str(exc).lower()
    return "access is denied" in message or "permission denied" in message


def _browser_startup_blocker_message(exc: BaseException, *, channel: str | None) -> str:
    channel_hint = f" channel={channel}" if channel else ""
    return (
        "browser startup is blocked by local OS permissions"
        f"{channel_hint}: {exc}. This is a release blocker; install or allow the Playwright browser runtime, "
        "or run only an explicitly draft/local preflight with the browser gate skipped."
    )


def _write_failure_payload(
    *,
    output_path: Path,
    args: argparse.Namespace,
    secondary_root: str | None,
    base_url: str,
    database_path: Path,
    checks: list[str],
    failure_code: str,
    message: str,
) -> None:
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "root": args.root,
        "secondary_root": secondary_root,
        "base_url": base_url,
        "database_path": str(database_path),
        "status": "fail",
        "failure_code": failure_code,
        "failure": message,
        "checks": [],
        "planned_checks": checks,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _secondary_root(*, primary: str, requested: str | None) -> str | None:
    candidate = (requested or "").strip() or "BR"
    if candidate.upper() == primary.upper():
        candidate = "MXI" if primary.upper() == "BR" else "BR"
    return candidate


def _wait_for_ready(base_url: str, *, timeout_seconds: int) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{base_url}/api/v1/health/ready", timeout=3) as response:
                if response.status == 200:
                    return
        except Exception as exc:  # pragma: no cover - diagnostic path
            last_error = exc
        time.sleep(0.5)
    raise RuntimeError(f"API did not become ready in time: {last_error}")


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _start_server(*, repo_root: Path, env: dict[str, str], port: int) -> subprocess.Popen[str]:
    return subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "apps.api.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],
        cwd=repo_root,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def _write_market_fixture_sitecustomize(root_dir: Path) -> Path:
    fixture_dir = root_dir / "market-fixture"
    fixture_dir.mkdir(parents=True, exist_ok=True)
    (fixture_dir / "sitecustomize.py").write_text(
        dedent(
            r'''
            from __future__ import annotations

            from datetime import UTC, datetime, timedelta

            from libs.adapters.contracts import Bar
            import libs.marketdata.service as marketdata_service
            from libs.marketdata.service import LiveInstrumentMarketSnapshot, LiveQuoteSnapshot


            class BrowserSmokeMarketDataService:
                def get_quote_snapshot(
                    self,
                    *,
                    root_code: str,
                    contract: str,
                    providers: list[str],
                    unit_hint: str | None = None,
                    now: datetime | None = None,
                ) -> LiveQuoteSnapshot:
                    current_time = now or datetime(2026, 4, 24, 9, 40, tzinfo=UTC)
                    current_price = _base_price(root_code)
                    previous_price = round(current_price * 0.9945, 2)
                    change_abs = round(current_price - previous_price, 2)
                    change_pct = round(change_abs / previous_price, 4)
                    return LiveQuoteSnapshot(
                        provider="browser_smoke_fixture",
                        root_code=root_code,
                        contract=contract,
                        unit=unit_hint or _unit(root_code),
                        current_price=current_price,
                        price_change_abs=change_abs,
                        price_change_pct=change_pct,
                        as_of=current_time,
                        status="fresh",
                        detail="Deterministic browser-smoke market fixture.",
                    )

                def get_market_snapshot(
                    self,
                    *,
                    root_code: str,
                    contract: str,
                    providers: list[str],
                    unit_hint: str | None = None,
                    now: datetime | None = None,
                ) -> LiveInstrumentMarketSnapshot:
                    quote = self.get_quote_snapshot(
                        root_code=root_code,
                        contract=contract,
                        providers=providers,
                        unit_hint=unit_hint,
                        now=now,
                    )
                    current_time = quote.as_of
                    return LiveInstrumentMarketSnapshot(
                        provider="browser_smoke_fixture",
                        root_code=root_code,
                        contract=contract,
                        unit=quote.unit,
                        as_of=current_time,
                        status="fresh",
                        detail="Deterministic browser-smoke market fixture.",
                        quote=quote,
                        daily_bars=_build_bars(
                            root_code=root_code,
                            contract=contract,
                            timeframe="1D",
                            current_price=quote.current_price,
                            count=12,
                            step_ratio=0.0007,
                            interval=timedelta(minutes=30),
                            end_at=current_time,
                        ),
                        weekly_bars=_build_bars(
                            root_code=root_code,
                            contract=contract,
                            timeframe="1W",
                            current_price=quote.current_price,
                            count=7,
                            step_ratio=0.0014,
                            interval=timedelta(days=1),
                            end_at=current_time,
                        ),
                        monthly_bars=_build_bars(
                            root_code=root_code,
                            contract=contract,
                            timeframe="1M",
                            current_price=quote.current_price,
                            count=6,
                            step_ratio=0.0022,
                            interval=timedelta(days=5),
                            end_at=current_time,
                        ),
                    )


            def _build_bars(
                *,
                root_code: str,
                contract: str,
                timeframe: str,
                current_price: float,
                count: int,
                step_ratio: float,
                interval: timedelta,
                end_at: datetime,
            ) -> list[Bar]:
                step = max(current_price * step_ratio, 0.5)
                bars: list[Bar] = []
                for index in range(count):
                    close = round(current_price - step * (count - index - 1), 2)
                    open_price = round(close - step * 0.35, 2)
                    high_price = round(max(open_price, close) + step * 0.4, 2)
                    low_price = round(min(open_price, close) - step * 0.32, 2)
                    bar_end = end_at - interval * (count - index - 1)
                    bar_start = bar_end - interval
                    bars.append(
                        Bar(
                            provider="browser_smoke_fixture",
                            root=root_code,
                            contract=contract,
                            timeframe=timeframe,
                            open=open_price,
                            high=high_price,
                            low=low_price,
                            close=close,
                            volume=float(1000 + index * 125),
                            start_at=bar_start,
                            end_at=bar_end,
                        )
                    )
                return bars


            def _base_price(root_code: str) -> float:
                return {
                    "SI": 96325.0,
                    "BR": 6845.0,
                    "MXI": 328950.0,
                }.get(root_code.upper(), 1000.0)


            def _unit(root_code: str) -> str:
                return "USD" if root_code.upper() == "BR" else "RUB"


            _fixture_service = BrowserSmokeMarketDataService()


            def get_market_data_service() -> BrowserSmokeMarketDataService:
                return _fixture_service


            marketdata_service.get_market_data_service = get_market_data_service
            '''
        ).lstrip(),
        encoding="utf-8",
    )
    return fixture_dir


def _run(command: list[str], *, cwd: Path, env: dict[str, str]) -> None:
    completed = subprocess.run(command, cwd=cwd, env=env, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"Command failed with exit code {completed.returncode}: {' '.join(command)}")


def _dump_server_output(server: subprocess.Popen[str]) -> None:
    if server.stdout is None:
        return
    try:
        output = server.stdout.read()
    except Exception:
        return
    if output:
        print("[browser-smoke] server output", file=sys.stderr)
        print(output[-4000:], file=sys.stderr)


def _stop_server(server: subprocess.Popen[str]) -> None:
    if server.poll() is not None:
        return
    server.terminate()
    try:
        server.wait(timeout=10)
    except subprocess.TimeoutExpired:
        server.kill()
        server.wait(timeout=10)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run browser-level smoke checks for the IMOEX operator UI.")
    parser.add_argument("--root", default="Si")
    parser.add_argument("--secondary-root", default="BR")
    parser.add_argument("--port", type=int)
    parser.add_argument("--timeout-seconds", type=int, default=45)
    parser.add_argument("--output")
    parser.add_argument("--channel", help="Optional Playwright browser channel, for example msedge.")
    parser.add_argument("--headed", action="store_false", dest="headless")
    parser.add_argument("--skip-chart-fixture", action="store_true")
    parser.add_argument("--allow-missing-dependency", action="store_true")
    parser.set_defaults(headless=True)
    return parser


if __name__ == "__main__":
    raise SystemExit(main())
