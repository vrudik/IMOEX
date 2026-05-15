# Release And Rollback Checklist

Updated: 2026-05-05

This checklist defines the minimum release discipline for the IMOEX decision-support app. It is intentionally strict about truth, recovery, and repeatability.

## Release Goal

A release is acceptable when the app can support the private-beta daily loop:

`scan -> compare -> focus -> journal -> review`

without showing false market data, silently hiding failures, or requiring the author to debug the setup live.

Before any private-beta deployment decision, complete `docs/private_beta_acceptance_checklist.md`, align the walkthrough with `docs/private_beta_sales_readiness.md`, and archive the evidence pack with the candidate build.

Use `docs/private_beta_release_notes_template.md` for the candidate release notes so accepted warnings, explicit non-goals, support boundaries, rollback owner, and decision owner are captured consistently. Full candidate evidence must use completed release notes with no unresolved `<...>` placeholders.

Generate a local evidence manifest after the required artifacts exist:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\private_beta_evidence_pack.ps1 `
  -ReleaseCheckLog ".\artifacts\release-check.log" `
  -BrowserSmokeJson ".\artifacts\browser-smoke.json" `
  -ProductReadinessJson ".\artifacts\product-readiness.json" `
  -AdminHealthJson ".\artifacts\admin-health.json" `
  -WorkspaceSnapshotJson ".\artifacts\workspace-snapshot.json" `
  -TelegramPreviewJson ".\artifacts\telegram-preview.json" `
  -TelegramOpsPreviewJson ".\artifacts\telegram-ops-preview.json" `
  -RestoreDrillSummary ".\artifacts\restore-drill-summary.json" `
  -PerformanceBaselineJson ".\artifacts\performance-baseline.json" `
  -AcceptanceChecklist ".\artifacts\acceptance-checklist-draft.md" `
  -ReleaseNotes ".\artifacts\release-notes.md"
```

For a draft manifest before artifacts are available, add `-AllowMissingArtifacts`. The script is only an evidence collector; it does not authorize production deployment, pricing, broker execution, order routing, autotrading, or private-beta launch.

Validate the manifest before treating it as candidate evidence:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\validate_private_beta_evidence.ps1 `
  -ManifestPath ".\artifacts\evidence-pack\private-beta-evidence-manifest.json"
```

For an intentionally incomplete draft, add `-AllowDraft`. Draft validation still enforces the signals-only and no-launch/no-pricing/no-order-routing/no-autotrading flags, warns when the release-check log does not include both `product readiness OK` and `[release-check] OK`, and blocks any draft release notes that claim `Private-beta candidate accepted: yes`. Full validation also requires a known candidate git revision, release notes candidate revision matches the evidence manifest, analytics mode matches the evidence manifest, Telegram mode recorded as `disabled`, `preview`, `dry-run`, or `configured`, concrete release-note links to Telegram preview JSON and Telegram ops preview JSON, candidate-local acceptance checklist prefill with explicit safety flags and a no-authorization safety phrase, operator-readable candidate summary safety flags when the summary is archived in the manifest, completed release notes with market-data mode recorded as `live`, `hidden`, `degraded`, or `fixture for browser smoke only`, accepted warnings recorded as `None` or concrete `warning, owner, expiry/follow-up` entries, no unresolved placeholders, all operator walkthrough checks marked `pass`, support-boundary confirmations answered `yes`, a concrete decision owner, a `yes/no/deferred` decision status, an ISO-8601 UTC decision timestamp, concrete rollback owner/revision/artifact/stop-owner fields, rollback verification coverage, and checks release-check green status, browser-smoke failure status and coverage for Morning Command Brief visibility, Today's Operating Queue visibility, Readiness Next Steps visibility, and market freshness alert visibility, restore-drill status, performance-baseline labels, product-readiness status, admin-health status, Morning Command Brief, Today's Operating Queue, and Readiness Next Steps workspace snapshot status, Today's Operating Queue count reconciliation against the archived watchlist, Readiness Next Steps required keys, counts, statuses, market-truth reconciliation, and guardrail-language checks, nested workspace and Telegram preview execution-authorization flag guards, execution-language guards, Telegram preview JSON, Telegram ops preview JSON, and release-note safety phrases. The validation JSON also includes a `daily_workflow_evidence` object with operator-reviewable Morning Command Brief status, Today's Operating Queue reconciliation booleans, and Readiness Next Steps readiness booleans; the candidate summary JSON mirrors market freshness alert counts, keys, and validation booleans for review tooling.

To produce a local non-production candidate directory with release-check logs, product-readiness JSON, admin-health JSON, workspace snapshot JSON, Telegram preview JSON, Telegram ops preview JSON, optional browser/performance/restore artifacts, draft release notes, `candidate-summary.md`, and an evidence manifest, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\private_beta_candidate_check.ps1 `
  -Root Si `
  -SkipDocker `
  -RequireCleanGit
```

For a faster draft on a workstation, add `-SkipFullPytest -SkipBrowser -SkipPerformance -SkipRestore -AllowDraftEvidence` and omit `-RequireCleanGit` if the tree is intentionally dirty. Draft output is not a private-beta approval.

For a diagnostic draft that intentionally attempts browser smoke on a workstation, use `-AllowDraftEvidence` without `-SkipBrowser`. If local OS permissions block browser startup, the wrapper keeps the failure JSON/log, records the browser-smoke failure code, failure detail, and completed/planned check counts in `candidate-summary.md`, runs draft validation, and writes a blocked summary; final candidate evidence still requires a passing browser smoke and must be rerun without `-AllowDraftEvidence`.

If release notes were completed separately, pass them into the wrapper with `-PreparedReleaseNotes <completed-release-notes.md>`. Without that parameter the wrapper copies the template as `release-notes-draft.md`, validates in draft mode, and records a next action to replace placeholders before final acceptance. A full candidate run without skipped release/browser/performance/restore gates now requires `-PreparedReleaseNotes`; use `-AllowDraftEvidence` when the intent is draft evidence only.

Review `candidate-summary.md` first: it includes candidate git revision, working-tree state, browser-smoke command and recorded failure details, daily workflow evidence, market freshness alert evidence and validation, validator reconciliation flags, safety flags including `autotrading_authorized=false`, evidence validation status, warning/failure rollups, and a `Next Actions` section for the remaining acceptance work. Wrapper-generated manifests archive this summary as `candidate_summary` evidence so the validator can confirm the visible safety flags are still present. The wrapper also fails if the final candidate summary or candidate-local acceptance checklist cannot be copied over the archived manifest evidence files. The same output directory includes `acceptance-checklist-draft.md` with a generated `Candidate Output Prefill` for recording the final non-production walkthrough. Then open the evidence validation JSON for the full machine-readable record. The wrapper does not authorize release, production deployment, pricing, broker execution, order routing, or autotrading.

The local candidate wrapper forces `APP_ENVIRONMENT=local`, disables live market data and MOEX reference auto-sync, and disables the live-market-data product-readiness requirement for its own API snapshots. This keeps local draft evidence truthful and reviewable when live feeds are unavailable; staging or production-like acceptance still requires target-environment product-readiness evidence with the stricter market-data policy enabled.

When `scripts/private_beta_candidate_check.ps1` generates the evidence pack, it passes the candidate-local `acceptance-checklist-draft.md` into the manifest so the archived `acceptance_checklist` artifact matches the candidate-specific decision record.

For production-like deployments, define external alert routing from `docs/alerting_expectations.md` before accepting the release.

## Required Release Gates

Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\release_check.ps1
```

For a faster local preflight without Docker:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\release_check.ps1 -SkipFullPytest -SkipDocker
```

The release gate must cover:

- full regression tests or focused release tests for preflight
- Alembic upgrade coverage
- local smoke flow
- product-readiness health gate
- admin health
- admin/runtime API protection readiness
- backup freshness, restore evidence, scheduler, delivery, migration, and market-data policy readiness
- Telegram dry-run or preview
- tracked local artifact check
- performance baseline capture
- backup restore drill
- private-beta candidate evidence wrapper
- private-beta evidence manifest generation
- private-beta evidence validation
- browser smoke for the private-beta golden path
- Docker smoke unless explicitly skipped for local preflight

## Continuous Integration

Every product-ready branch and pull request should run `.github/workflows/product-ready.yml`.

The workflow has two jobs:

- focused release check with `release_check.ps1 -SkipFullPytest -SkipDocker -SkipPerformance -SkipRestore -SkipBrowser`
- browser smoke with Playwright, including the current-price and day/week/month chart fixture pass

## Tracked Local Artifacts

`release_check.ps1` fails when local smoke databases or office cleanup backups are tracked by git. This is intentional because those files should not ship in a product release.

For diagnostics only, the check can continue past this blocker:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\release_check.ps1 -SkipFullPytest -SkipDocker -AllowTrackedLocalArtifacts
```

Do not use that override for a release candidate.

## Browser Smoke

Install the optional browser dependency before running the full release gate:

```powershell
.\.venv\Scripts\python.exe -m pip install -e .[browser]
.\.venv\Scripts\python.exe -m playwright install chromium
```

Run the browser smoke directly:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\browser_smoke.ps1 -Root Si
```

On Windows, an installed Edge channel can be used:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\browser_smoke.ps1 -Root Si -Channel msedge
```

If Playwright or the selected browser channel cannot start because local OS permissions block the browser process, `scripts/browser_smoke.py` records `failure_code=browser_startup_blocked` in the browser-smoke JSON and exits non-zero. Treat this as a release blocker unless the run is explicitly draft/local-only preflight with `-SkipBrowser`; final private-beta evidence still requires a passing browser smoke.

The browser smoke checks:

- workspace opens in a real browser
- Morning Command Brief is visible and remains signals-only
- Today's Operating Queue is visible and remains free of execution language
- Readiness Next Steps is visible and remains free of launch, pricing, order-routing, autotrading, and broker-execution language
- market freshness alerts are visible when live market data is hidden and remain signals-only
- workspace root switch works through the real sidebar selector
- hidden market-data state is visible when live data is disabled
- signal detail opens from the workspace
- runtime prompt diff renders through the UI
- risky prompt draft can be saved
- pending draft can be dismissed from the UI
- a fixture-backed market pass renders current price plus day, week, and month chart cards
- the fixture-backed market pass can switch from the primary root to a secondary root without losing prices or charts
- a mobile viewport renders the current-price block and day/week/month charts without horizontal overflow
- chart drag measurement is wired in the browser

## Market Data Policy

Private beta may pass with hidden market data only when the UI clearly shows that prices and charts are unavailable.

Staging and production enforce a stricter environment policy in `/api/v1/health/product-readiness`:

- live quote and candles are required for trading-session readiness
- hidden, disabled, stale, or degraded market data blocks the release gate
- hidden market data is acceptable only for local development, demo, or explicitly degraded local operation
- synthetic user-facing prices are not allowed

Set `APP_ENVIRONMENT=staging` or `APP_ENVIRONMENT=production` to enable the stricter policy automatically. Local or beta environments can opt in with `PRODUCT_READINESS_REQUIRE_LIVE_MARKET_DATA=true`.

## Admin And Runtime Security

Local development may run without an admin key. Any configured key, or an environment in `prod`, `production`, or `staging`, turns on API-key protection for admin and runtime-control APIs.

Production-like deployments must set:

- `APP_ENVIRONMENT=production` or `APP_ENVIRONMENT=staging`
- `ADMIN_API_KEY=<operator-secret>`
- `ADMIN_API_KEY_HEADER=X-IMOEX-Admin-Key` unless a different gateway header is intentional

The runtime UI sends `X-IMOEX-Admin-Key` from browser `localStorage["imoex_admin_key"]` when present. External operators can use the same header through API clients.

The runtime page includes an operator control for saving or clearing that browser-local key. Do not paste the key into screenshots, logs, or issue comments.

## Performance Baseline

Capture a baseline before every release candidate:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\performance_baseline.ps1 -Root Si
```

Use strict budget enforcement only after the current baseline is stable:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\performance_baseline.ps1 -Root Si -FailOnBudget
```

Tracked surfaces:

- dashboard API
- workspace API
- workspace page
- signal detail API
- signal detail page
- runtime page
- council page
- journal API and page
- product-readiness gate

Current private-beta budgets keep operator pages below 5s in degraded live-data conditions. The market-data layer also circuit-breaks repeated provider failures so one unavailable quote source does not multiply into per-root timeouts across workspace, runtime, council, and product-readiness checks.

## Restore Drill

Run the SQLite restore drill before a SQLite release candidate:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\restore_drill.ps1 -Root Si
```

The drill must:

- create a fresh source database
- build signals
- create a SQLite backup
- restore that backup into a separate database path
- run integrity checks against the restored database
- verify signals, product-readiness, and admin health on the restored database

For Postgres releases, use the dedicated restore drill against a fresh disposable target database:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\postgres_restore_drill.ps1 `
  -SourceDatabaseUrl "<source-postgres-url>" `
  -RestoredDatabaseUrl "<fresh-restore-target-url>" `
  -Root Si `
  -AllowDestructiveRestore
```

See `docs/postgres_backup_restore_runbook.md` for the full operator runbook. Postgres backups are created through `pg_dump --format=custom --no-owner --no-privileges` and restored through `pg_restore`.

For staging and production, attach the restore-drill JSON summary to the product-readiness gate:

```powershell
$env:PRODUCT_READINESS_RESTORE_EVIDENCE_PATH = ".\.restore-drill\restore-drill-summary.json"
$env:PRODUCT_READINESS_RESTORE_EVIDENCE_MAX_AGE_HOURS = "72"
```

The `restore_drill_evidence` check requires a fresh JSON summary with `release_gate=pass`, positive `roots` and `final_signals`, and `integrity_check=ok` when the SQLite drill reports it. Local environments can opt in with `PRODUCT_READINESS_REQUIRE_RESTORE_EVIDENCE=true`.

## Pre-Release Checklist

- [ ] `release_check.ps1` passes.
- [ ] Product-readiness returns `release_gate=pass`.
- [ ] Product-readiness includes backup, restore evidence, scheduler, delivery, migration, and market-data policy checks.
- [ ] Product-readiness includes `admin_runtime_security=ok` for the target environment.
- [ ] Staging/production product-readiness includes `restore_drill_evidence=ok` and `market_data_policy=ok`.
- [ ] Runtime admin-key browser control can save and clear the operator key.
- [ ] Market-data posture is understood for the target environment.
- [ ] No synthetic user-facing prices are visible.
- [ ] Runtime prompt governance can diff, save, approve, dismiss, restore, and audit.
- [ ] Backup is created and visible in admin health.
- [ ] Restore drill passes for the target database class.
- [ ] Postgres releases have a fresh `postgres_restore_drill.ps1` JSON summary.
- [ ] Browser smoke passes or is explicitly skipped for local-only preflight.
- [ ] Scheduler health and recent failures are reviewed.
- [ ] External alerting expectations are mapped for feed loss, stale references, scheduler drift, backup failures, and product-readiness failures.
- [ ] Telegram preview or dry-run is successful.
- [ ] Release notes follow `docs/private_beta_release_notes_template.md`, release notes candidate revision matches the evidence manifest, analytics mode matches the evidence manifest, Telegram mode recorded as `disabled`, `preview`, `dry-run`, or `configured`, record market-data mode as `live`, `hidden`, `degraded`, or `fixture for browser smoke only`, record accepted warnings as `None` or concrete `warning, owner, expiry/follow-up` entries, include non-goals, all operator walkthrough checks marked `pass`, support boundaries, concrete rollback owner/revision/artifact/stop-owner fields, rollback verification coverage, concrete decision owner, `yes/no/deferred` decision status, ISO-8601 UTC decision timestamp, contain no unresolved `<...>` placeholders, and answer every support-boundary confirmation as `yes`.
- [ ] Rollback steps are known before deployment starts.

## Rollback Checklist

Before deploying:

- [ ] Create or verify a fresh backup.
- [ ] Record the current git revision.
- [ ] Record the current database URL and backup directory.
- [ ] Record the current environment market-data policy.

If rollback is needed:

- [ ] Stop the preview, scheduler, or production process.
- [ ] Restore the previous application revision.
- [ ] Restore the database from the selected backup if the release changed schema or data.
- [ ] Run product-readiness health gate.
- [ ] Run local smoke or target-environment smoke.
- [ ] Verify workspace, runtime, council, and dashboard surfaces.
- [ ] Verify Telegram preview or dry-run.
- [ ] Record the rollback reason and follow-up action.

## Known Open Gates

These are not yet complete enough for production launch:

- performance budget enforcement in release mode
- external alert destination configuration and test evidence
- deployment packaging, pricing, and paid support commitments

## Release Decision

Release only when:

- required gates pass
- any warning is explicit and accepted
- rollback path is shorter than the expected incident response window
- the app remains a decision-support system with no execution, order-routing, or autotrading behavior
