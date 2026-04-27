# Alerting Expectations

Updated: 2026-04-27

This document defines the minimum external alerting expectations for private-beta and production-like IMOEX deployments. It does not configure any vendor, credential, webhook, pager, or production destination by itself. The app remains signals-only decision support.

## Alerting Principle

Alert only on conditions that can make the operator trust stale, missing, or unsafe context:

- market-data feed loss or stale price/charts
- stale MOEX reference data
- scheduler drift or missed recalculation/delivery jobs
- backup failure, stale backup, or missing restore evidence
- product-readiness release gate failure
- admin/runtime security disabled in staging or production-like environments

Alerts should point to the relevant runbook and include enough context to decide whether the app should stay in private-beta operation, be degraded, or be paused.

## Required Monitors

### Feed Loss And Market Freshness

Source:

- `/api/v1/health/product-readiness?root=<root>`
- workspace trust ribbon and market-data status
- provider failure/circuit-breaker logs

Trigger:

- `market_data_policy` is not `ok` in staging or production-like environments.
- live quote or candle freshness is stale/degraded beyond the configured SLA.
- provider failure circuit breaker is open for a launch-critical root.

Operator action:

- Treat prices and charts as unavailable unless the UI explicitly shows fresh traceable data.
- Keep decision support visible only with degraded warnings.
- Do not raise conviction based on stale or hidden market data.

### Stale Reference Data

Source:

- `/api/v1/health/product-readiness?root=<root>`
- reference sync status in dashboard/runtime surfaces
- `moex_reference_auto_sync_failed` logs

Trigger:

- reference sync age exceeds the configured freshness SLA.
- reference sync fails repeatedly for a launch-critical root.
- active/next contract metadata is missing for a launch-critical root.

Operator action:

- Re-run reference sync or switch to documented degraded operation.
- Validate active contract, next contract, expiry date, and roll state before using signals.

### Scheduler Drift

Source:

- `/api/v1/health/product-readiness?root=<root>`
- scheduler health in admin health
- delivery activity history

Trigger:

- recalculation job is late beyond the configured cycle SLA.
- scheduled digest/resolution delivery job is missed or repeatedly skipped unexpectedly.
- scheduler is disabled in a target environment that expects automated cycles.

Operator action:

- Run manual recalculation or delivery preview.
- Confirm delivery history reason trail explains any skipped, suppressed, or dry-run outcome.

### Backup And Restore Evidence

Source:

- `/api/v1/health/product-readiness?root=<root>`
- `/api/v1/admin/health`
- restore-drill JSON summary
- backup directory or Postgres backup artifact inventory

Trigger:

- latest backup is missing or older than the configured maximum age.
- restore-drill evidence is missing, stale, failed, or from the wrong database class.
- admin health cannot see the expected backup artifacts.

Operator action:

- Run the correct restore drill before accepting the release.
- Block private beta if backup and restore evidence cannot be produced.

### Product-Readiness Gate

Source:

- `/api/v1/health/product-readiness?root=<root>`
- release-check output

Trigger:

- `release_gate` is not `pass`.
- any required check is missing for the target environment.
- admin/runtime security is not `ok` in staging or production-like environments.

Operator action:

- Do not deploy or promote the candidate.
- Attach the failing product-readiness JSON to the release notes and fix or explicitly downgrade the environment.

## Minimum Alert Payload

Every external alert should include:

- environment and root
- failing check name
- current status and stale/degraded age when available
- link or path to product-readiness JSON
- link or path to release or restore evidence
- runbook section to follow
- whether operation should continue, degrade, or pause

## Private-Beta Policy

For private beta:

- Alerts may be routed to email, chat, issue tracker, or any operator-approved system.
- Credentials and destinations must be configured outside this repository.
- Missing external alerting is acceptable only for local development, not for a private-beta candidate.
- Alerting evidence should be recorded in `docs/private_beta_acceptance_checklist.md` before any deployment decision.

## Production-Like Blockers

Block a production-like release when:

- there is no alert destination for feed loss, stale references, scheduler drift, backup failure, and product-readiness failure
- alert routing cannot be tested without exposing secrets
- alerts do not identify whether the app should continue, degrade, or pause
- the operator cannot link an alert back to a runbook and evidence artifact
