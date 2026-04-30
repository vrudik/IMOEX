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
    assert "tests\\test_private_beta_evidence_validation.py" in script
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


def test_private_beta_evidence_pack_script_collects_required_artifacts() -> None:
    script = (REPO_ROOT / "scripts" / "private_beta_evidence_pack.ps1").read_text(encoding="utf-8")

    assert "AllowMissingArtifacts" in script
    assert "ReleaseCheckLog" in script
    assert "BrowserSmokeJson" in script
    assert "ProductReadinessJson" in script
    assert "AdminHealthJson" in script
    assert "RestoreDrillSummary" in script
    assert "PerformanceBaselineJson" in script
    assert "AcceptanceChecklist" in script
    assert "ReleaseNotes" in script
    assert "docs\\alerting_expectations.md" in script
    assert "docs\\product_analytics_events.md" in script
    assert "docs\\private_beta_sales_readiness.md" in script
    assert "docs\\private_beta_acceptance_checklist.md" in script
    assert "docs\\private_beta_release_notes_template.md" in script
    assert "signals_only_decision_support" in script
    assert "release_decision_authorized" in script
    assert "production_deployment_authorized" in script
    assert "pricing_commitment_authorized" in script
    assert "order_routing_authorized" in script


def test_private_beta_candidate_check_script_collects_local_candidate_evidence() -> None:
    script = (REPO_ROOT / "scripts" / "private_beta_candidate_check.ps1").read_text(encoding="utf-8")

    assert "private_beta_evidence_pack.ps1" in script
    assert "validate_private_beta_evidence.ps1" in script
    assert "AcceptanceChecklist" in script
    assert "release_check.ps1" in script
    assert "browser_smoke.py" in script
    assert "performance_baseline.ps1" in script
    assert "restore_drill.ps1" in script
    assert "private_beta_release_notes_template.md" in script
    assert "private_beta_acceptance_checklist.md" in script
    assert "acceptance-checklist-draft.md" in script
    assert "acceptance_checklist-" in script
    assert "Candidate Output Prefill" in script
    assert "Candidate summary Markdown" in script
    assert "Candidate summary JSON" in script
    assert "product-readiness.json" in script
    assert "admin-health.json" in script
    assert "telegram-preview.json" in script
    assert "private-beta-evidence-validation.json" in script
    assert "git-status.txt" in script
    assert "CandidateRevision" in script
    assert "RequireCleanGit" in script
    assert "PreparedReleaseNotes" in script
    assert "release_notes_mode" in script
    assert "Full private-beta candidate generation requires completed release notes" in script
    assert "Private-beta candidate requires a clean git working tree" in script
    assert "candidate-summary.md" in script
    assert "Private-Beta Candidate Summary" in script
    assert "Candidate revision" in script
    assert "Working tree state" in script
    assert "Clean git required" in script
    assert "candidate_worktree_state" in script
    assert "require_clean_git" in script
    assert "candidate_review_status" in script
    assert "skipped_gates" in script
    assert "next_actions" in script
    assert "acceptance_checklist_draft" in script
    assert "Complete acceptance-checklist-draft.md" in script
    assert "Next Actions" in script
    assert "draft_evidence_only" in script
    assert "operator_acceptance_ready" in script
    assert "Evidence Validation" in script
    assert "evidence_validation_status" in script
    assert "evidence_validation_warnings" in script
    assert "evidence_validation_failures" in script
    assert "Order routing authorized by this wrapper: false" in script
    assert "/api/v1/health/product-readiness" in script
    assert "/api/v1/admin/health" in script
    assert "/api/v1/notifications/telegram/preview" in script
    assert "AllowDraftEvidence" in script
    assert "signals_only_decision_support" in script
    assert "release_decision_authorized" in script
    assert "production_deployment_authorized" in script
    assert "pricing_commitment_authorized" in script
    assert "order_routing_authorized" in script


def test_validate_private_beta_evidence_script_enforces_candidate_guardrails() -> None:
    script = (REPO_ROOT / "scripts" / "validate_private_beta_evidence.ps1").read_text(encoding="utf-8")

    assert "AllowDraft" in script
    assert "missing_required_artifacts" in script
    assert "candidate_revision" in script
    assert "candidate_revision_unknown" in script
    assert "draft_candidate_revision_unknown" in script
    assert "release_notes_candidate_revision_missing" in script
    assert "draft_release_notes_candidate_revision_missing" in script
    assert "release_notes_candidate_revision_mismatch" in script
    assert "draft_release_notes_candidate_revision_mismatch" in script
    assert "release_notes_analytics_mode_invalid" in script
    assert "draft_release_notes_analytics_mode_invalid" in script
    assert "release_notes_analytics_mode_mismatch" in script
    assert "draft_release_notes_analytics_mode_mismatch" in script
    assert "release_notes_telegram_mode_invalid" in script
    assert "draft_release_notes_telegram_mode_invalid" in script
    assert "release_notes_placeholders_present" in script
    assert "draft_release_notes_placeholders_present" in script
    assert "release_notes_accepted_warnings_missing" in script
    assert "draft_release_notes_accepted_warnings_missing" in script
    assert "release_notes_accepted_warning_detail_incomplete" in script
    assert "draft_release_notes_accepted_warning_detail_incomplete" in script
    assert "release_notes_market_data_mode_invalid" in script
    assert "draft_release_notes_market_data_mode_invalid" in script
    assert "release_notes_support_boundary_unconfirmed" in script
    assert "draft_release_notes_support_boundary_unconfirmed" in script
    assert "release_notes_walkthrough_check_not_pass" in script
    assert "draft_release_notes_walkthrough_check_not_pass" in script
    assert "release_notes_decision_status_missing" in script
    assert "draft_release_notes_decision_status_missing" in script
    assert "draft_release_notes_accepts_candidate" in script
    assert "release_notes_decision_owner_missing" in script
    assert "draft_release_notes_decision_owner_missing" in script
    assert "release_notes_decision_timestamp_missing" in script
    assert "draft_release_notes_decision_timestamp_missing" in script
    assert "release_notes_rollback_owner_missing" in script
    assert "draft_release_notes_rollback_owner_missing" in script
    assert "release_notes_rollback_revision_missing" in script
    assert "draft_release_notes_rollback_revision_missing" in script
    assert "release_notes_rollback_artifact_missing" in script
    assert "draft_release_notes_rollback_artifact_missing" in script
    assert "release_notes_rollback_stop_owner_missing" in script
    assert "draft_release_notes_rollback_stop_owner_missing" in script
    assert "release_notes_rollback_verification_missing" in script
    assert "draft_release_notes_rollback_verification_missing" in script
    assert "Candidate Output Prefill" in script
    assert "acceptance_checklist_prefill_missing" in script
    assert "draft_acceptance_checklist_prefill_missing" in script
    assert "acceptance_checklist_safety_phrase_missing" in script
    assert "signals_only_decision_support" in script
    assert "release_decision_authorized" in script
    assert "production_deployment_authorized" in script
    assert "pricing_commitment_authorized" in script
    assert "order_routing_authorized" in script
    assert "product_readiness" in script
    assert "admin_health" in script
    assert "release_notes" in script
    assert "release_gate=pass" in script
    assert "browser_smoke_missing_check" in script
    assert "restore_drill_not_pass" in script
    assert "performance_baseline_missing_label" in script
    assert "Explicit Non-Goals" in script
    assert "does not authorize production deployment" in script
    assert "UTF8Encoding($false)" in script


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
    sales = (REPO_ROOT / "docs" / "private_beta_sales_readiness.md").read_text(encoding="utf-8")
    release_notes = (REPO_ROOT / "docs" / "private_beta_release_notes_template.md").read_text(encoding="utf-8")

    assert "release_check.ps1" in checklist
    assert "performance_baseline.ps1" in checklist
    assert "restore_drill.ps1" in checklist
    assert "postgres_restore_drill.ps1" in checklist
    assert "private_beta_acceptance_checklist.md" in checklist
    assert "private_beta_candidate_check.ps1" in checklist
    assert "private_beta_evidence_pack.ps1" in checklist
    assert "validate_private_beta_evidence.ps1" in checklist
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
    assert "private_beta_sales_readiness.md" in checklist
    assert "private_beta_release_notes_template.md" in checklist
    assert "private-beta candidate evidence wrapper" in checklist
    assert "private-beta evidence manifest generation" in checklist
    assert "private-beta evidence validation" in checklist
    assert "Candidate Output Prefill" in checklist
    assert "release notes candidate revision matches the evidence manifest" in checklist
    assert "analytics mode matches the evidence manifest" in checklist
    assert "Telegram mode recorded as `disabled`, `preview`, `dry-run`, or `configured`" in checklist
    assert "market-data mode recorded as `live`, `hidden`, `degraded`, or `fixture for browser smoke only`" in checklist
    assert "accepted warnings recorded as `None` or concrete `warning, owner, expiry/follow-up` entries" in checklist
    assert "unresolved `<...>` placeholders" in checklist
    assert "support-boundary confirmations answered `yes`" in checklist
    assert "all operator walkthrough checks marked `pass`" in checklist
    assert "blocks any draft release notes that claim `Private-beta candidate accepted: yes`" in checklist
    assert "ISO-8601 UTC decision timestamp" in checklist
    assert "concrete rollback owner/revision/artifact/stop-owner fields" in checklist
    assert "rollback verification coverage" in checklist
    assert "Postgres-equivalent backup and restore path" not in checklist
    assert "tracked local artifact cleanup before strict release-candidate CI enforcement" not in checklist
    assert "live-data production readiness policy in the health gate" not in checklist
    assert "Required Evidence Pack" in acceptance
    assert "release notes candidate revision matches the evidence manifest" in acceptance
    assert "analytics mode matches the evidence manifest" in acceptance
    assert "Telegram mode as `disabled`, `preview`, `dry-run`, or `configured`" in acceptance
    assert "market-data mode as `live`, `hidden`, `degraded`, or `fixture for browser smoke only`" in acceptance
    assert "accepted warnings as `None` or concrete `warning, owner, expiry/follow-up` entries" in acceptance
    assert "private_beta_candidate_check.ps1" in acceptance
    assert "candidate-summary.md" in acceptance
    assert "acceptance-checklist-draft.md" in acceptance
    assert "Candidate Output Prefill" in acceptance
    assert "Operator-readable candidate summary path" in acceptance
    assert "Candidate git revision" in acceptance
    assert "must not be `unknown`" in acceptance
    assert "clean git working tree for final candidate approval" in acceptance
    assert "Candidate summary next actions" in acceptance
    assert "Candidate summary validation status and accepted warnings/failures" in acceptance
    assert "private_beta_evidence_pack.ps1" in acceptance
    assert "validate_private_beta_evidence.ps1" in acceptance
    assert "browser-smoke checks" in acceptance
    assert "restore-drill status" in acceptance
    assert "performance labels" in acceptance
    assert "Private-beta evidence manifest path" in acceptance
    assert "Private-beta evidence validation path" in acceptance
    assert "Product-readiness JSON" in acceptance
    assert "Browser smoke JSON" in acceptance
    assert "Release Blockers" in acceptance
    assert "signals-only decision support" in acceptance
    assert "alerting_expectations.md" in acceptance
    assert "product_analytics_events.md" in acceptance
    assert "private_beta_sales_readiness.md" in acceptance
    assert "private_beta_release_notes_template.md" in acceptance
    assert "no secrets, prompt bodies, journal text, credentials, or API keys" in acceptance
    assert "support boundaries were accepted" in acceptance
    assert "Release notes path and decision owner" in acceptance
    assert "no unresolved `<...>` placeholders" in acceptance
    assert "operator walkthrough results with every check marked `pass`" in acceptance
    assert "support-boundary confirmation answered `yes`" in acceptance
    assert "Draft evidence must never record `Private-beta candidate accepted: yes`" in acceptance
    assert "ISO-8601 UTC decision timestamp" in acceptance
    assert "concrete rollback owner" in acceptance
    assert "rollback verification coverage" in acceptance
    assert "-PreparedReleaseNotes" in acceptance
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
    assert "Private-Beta Sales Readiness" in sales
    assert "The private-beta promise is:" in sales
    assert "Demo Narrative" in sales
    assert "Support Boundaries" in sales
    assert "Onboarding Checklist" in sales
    assert "Qualification Questions" in sales
    assert "no broker execution" in sales
    assert "no autotrading" in sales
    assert "no order placement" in sales
    assert "Pricing, billing, subscription terms" in sales
    assert "Production deployment, uptime SLA" in sales
    assert "guaranteed outcomes" in sales
    assert "Private-Beta Release Notes Template" in release_notes
    assert "Accepted Warnings" in release_notes
    assert "Explicit Non-Goals" in release_notes
    assert "Operator Walkthrough Result" in release_notes
    assert "Support Boundary Confirmation" in release_notes
    assert "Rollback Record" in release_notes
    assert "Decision owner" in release_notes
    assert "does not authorize production deployment" in release_notes
    assert "order routing" in release_notes
    assert "autotrading" in release_notes
    assert "signals-only decision support" in release_notes
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
