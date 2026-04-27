from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_release_check_script_runs_required_gates() -> None:
    script = (REPO_ROOT / "scripts" / "release_check.ps1").read_text(encoding="utf-8")

    assert "tests\\test_alembic_migrations.py" in script
    assert "tests\\test_dashboard_formatting.py" in script
    assert "tests\\test_marketdata_service.py" in script
    assert "tests\\test_security_admin.py" in script
    assert "tests\\test_release_readiness_assets.py" in script
    assert "scripts\\smoke_local.ps1" in script
    assert "scripts\\performance_baseline.ps1" in script
    assert "scripts\\restore_drill.ps1" in script
    assert "tests\\test_maintenance_backup.py" in script
    assert "scripts\\browser_smoke.ps1" in script
    assert "scripts\\smoke_docker.ps1" in script
    assert "/api/v1/health/product-readiness" in script
    assert "/api/v1/admin/health" in script
    assert "/api/v1/notifications/telegram/preview" in script
    assert "git -C $repoRoot ls-files" in script


def test_product_ready_ci_workflow_runs_release_and_browser_gates() -> None:
    workflow = (REPO_ROOT / ".github" / "workflows" / "product-ready.yml").read_text(encoding="utf-8")

    assert "Product Ready Gate" in workflow
    assert "actions/setup-python@v5" in workflow
    assert "release_check.ps1" in workflow
    assert "-SkipFullPytest" in workflow
    assert "-SkipDocker" in workflow
    assert "-SkipBrowser" in workflow
    assert "playwright install chromium" in workflow
    assert "browser_smoke.ps1" in workflow


def test_performance_baseline_tracks_operator_surfaces() -> None:
    script = (REPO_ROOT / "scripts" / "performance_baseline.ps1").read_text(encoding="utf-8")

    expected_labels = {
        "api_dashboard",
        "api_workspace",
        "page_workspace",
        "api_signal_detail",
        "page_signal_detail",
        "page_runtime",
        "page_council",
        "api_journal",
        "page_journal",
        "api_product_readiness",
    }
    for label in expected_labels:
        assert label in script

    assert "BUDGETS_MS" in script
    assert "IMOEX_PERF_OUTPUT" in script
    assert "Performance budgets exceeded" in script


def test_release_checklist_documents_release_and_rollback_policy() -> None:
    checklist = (REPO_ROOT / "docs" / "release_checklist.md").read_text(encoding="utf-8")
    postgres_runbook = (REPO_ROOT / "docs" / "postgres_backup_restore_runbook.md").read_text(encoding="utf-8")
    acceptance = (REPO_ROOT / "docs" / "private_beta_acceptance_checklist.md").read_text(encoding="utf-8")
    alerting = (REPO_ROOT / "docs" / "alerting_expectations.md").read_text(encoding="utf-8")
    analytics = (REPO_ROOT / "docs" / "product_analytics_events.md").read_text(encoding="utf-8")

    assert "release_check.ps1" in checklist
    assert "performance_baseline.ps1" in checklist
    assert "restore_drill.ps1" in checklist
    assert "postgres_restore_drill.ps1" in checklist
    assert "private_beta_acceptance_checklist.md" in checklist
    assert "pg_dump --format=custom" in checklist
    assert "browser_smoke.ps1" in checklist
    assert "Market Data Policy" in checklist
    assert "Admin And Runtime Security" in checklist
    assert "ADMIN_API_KEY" in checklist
    assert "admin_runtime_security=ok" in checklist
    assert "restore_drill_evidence=ok" in checklist
    assert "PRODUCT_READINESS_RESTORE_EVIDENCE_PATH" in checklist
    assert "PRODUCT_READINESS_REQUIRE_LIVE_MARKET_DATA" in checklist
    assert "Rollback Checklist" in checklist
    assert "synthetic user-facing prices are not allowed" in checklist
    assert "Known Open Gates" in checklist
    assert "alerting_expectations.md" in checklist
    assert "External alerting expectations" in checklist
    assert "Postgres-equivalent backup and restore path" not in checklist
    assert "tracked local artifact cleanup before strict release-candidate CI enforcement" not in checklist
    assert "live-data production readiness policy in the health gate" not in checklist
    assert "Required Evidence Pack" in acceptance
    assert "Product-readiness JSON" in acceptance
    assert "Browser smoke JSON" in acceptance
    assert "Release Blockers" in acceptance
    assert "signals-only decision support" in acceptance
    assert "alerting_expectations.md" in acceptance
    assert "product_analytics_events.md" in acceptance
    assert "no secrets, prompt bodies, journal text, credentials, or API keys" in acceptance
    assert "Required Monitors" in alerting
    assert "Feed Loss And Market Freshness" in alerting
    assert "Stale Reference Data" in alerting
    assert "Scheduler Drift" in alerting
    assert "Backup And Restore Evidence" in alerting
    assert "Product-Readiness Gate" in alerting
    assert "Minimum Alert Payload" in alerting
    assert "signals-only decision support" in alerting
    assert "Product Analytics Event Catalog" in analytics
    assert "Workspace Triage" in analytics
    assert "Price And Chart Confidence" in analytics
    assert "Watchlist Workflow" in analytics
    assert "Journal And Review Loop" in analytics
    assert "Council And Prompt Governance" in analytics
    assert "Delivery Explainability" in analytics
    assert "Release And Trust Gates" in analytics
    assert "Never collect:" in analytics
    assert "raw journal note" in analytics
    assert "rendered prompt body" in analytics
    assert "Make analytics opt-in for private beta" in analytics
    assert "Any analytics event tied to order execution or brokerage behavior" in analytics
    assert "pg_restore --clean --if-exists" in postgres_runbook


def test_restore_drill_script_restores_into_fresh_database_path() -> None:
    script = (REPO_ROOT / "scripts" / "restore_drill.ps1").read_text(encoding="utf-8")

    assert "source database" in script
    assert "restored database" in script
    assert "Copy-Item -LiteralPath $backupPath -Destination $restoredDb" in script
    assert "PRAGMA integrity_check" in script
    assert "/api/v1/health/product-readiness" in script
    assert "/api/v1/admin/health" in script
    assert "SELECT COUNT(*) FROM final_signal" in script


def test_postgres_restore_drill_documents_safe_restore_path() -> None:
    script = (REPO_ROOT / "scripts" / "postgres_restore_drill.ps1").read_text(encoding="utf-8")

    assert "AllowDestructiveRestore" in script
    assert "pg_restore" in script
    assert "PGPASSWORD" in script
    assert "--no-owner" in script
    assert "--no-privileges" in script
    assert "/api/v1/health/product-readiness" in script
    assert "/api/v1/admin/health" in script


def test_browser_smoke_covers_workspace_and_runtime_prompt_governance() -> None:
    script = (REPO_ROOT / "scripts" / "browser_smoke.py").read_text(encoding="utf-8")
    wrapper = (REPO_ROOT / "scripts" / "browser_smoke.ps1").read_text(encoding="utf-8")

    assert "sync_playwright" in script
    assert "/workspace?root=" in script
    assert "--secondary-root" in script
    assert "workspace_root_switch" in script
    assert '[data-surface-state-strip="workspace"]' in script
    assert "[data-market-unavailable]" in script
    assert "/workspace/runtime?root=" in script
    assert "[data-runtime-prompt-diff-button]" in script
    assert 'select[name="control_mode"]' in script
    assert "[data-runtime-prompt-dismiss]" in script
    assert "[data-runtime-admin-key-form]" in script
    assert "runtime_admin_key_save_clear" in script
    assert "imoex_admin_key" in script
    assert "Browser smoke governance note." in script
    assert "sitecustomize.py" in script
    assert "market_fixture_day_week_month_charts_visible" in script
    assert "market_fixture_multi_root_switch" in script
    assert "market_fixture_mobile_charts_visible" in script
    assert "market_fixture_mobile_no_horizontal_overflow" in script
    assert "[data-market-chart-card]" in script
    assert "[data-market-current-price]" in script
    assert "--secondary-root" in wrapper
    assert "browser_smoke.py" in wrapper
