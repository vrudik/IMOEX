# Release And Rollback Checklist

Updated: 2026-04-24

This checklist defines the minimum release discipline for the IMOEX decision-support app. It is intentionally strict about truth, recovery, and repeatability.

## Release Goal

A release is acceptable when the app can support the private-beta daily loop:

`scan -> compare -> focus -> journal -> review`

without showing false market data, silently hiding failures, or requiring the author to debug the setup live.

Before any private-beta deployment decision, complete `docs/private_beta_acceptance_checklist.md` and archive its evidence pack with the candidate build.

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

The browser smoke checks:

- workspace opens in a real browser
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
- [ ] Release notes include known warnings.
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
- deployment packaging, pricing, and support commitments

## Release Decision

Release only when:

- required gates pass
- any warning is explicit and accepted
- rollback path is shorter than the expected incident response window
- the app remains a decision-support system with no execution or order-routing behavior
