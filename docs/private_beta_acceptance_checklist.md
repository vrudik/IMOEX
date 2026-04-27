# Private-Beta Acceptance Checklist

Updated: 2026-04-27

This checklist is the final non-production acceptance gate before any private-beta deployment decision. It does not authorize production rollout, pricing, brokerage connectivity, or order execution. The app remains signals-only decision support.

## Required Evidence Pack

Attach or archive these artifacts for the candidate build:

- `release_check.ps1` output showing `product readiness OK` and `OK`.
- Browser smoke JSON from `scripts/browser_smoke.ps1`, including workspace, runtime prompt governance, multi-root switch, current price, day/week/month charts, drag measurement, mobile charts, and no horizontal overflow.
- Product-readiness JSON for the target environment, including backup freshness, restore-drill evidence, scheduler, delivery, migration, market-data policy, and admin/runtime security checks.
- Admin health JSON for the target environment.
- Restore-drill summary for the target database class: SQLite restore drill for SQLite, Postgres restore drill for Postgres.
- Performance baseline output for dashboard, workspace, signal detail, runtime, council, journal, and product-readiness surfaces.
- External alerting map from `docs/alerting_expectations.md`, including destinations or explicit non-production deferral.
- Product analytics mode from `docs/product_analytics_events.md`: disabled, local-only export, or explicitly approved opt-in telemetry.
- Release notes listing accepted warnings and explicit non-goals.

## Operator Acceptance Flow

Run the acceptance flow in a non-production environment that matches the intended beta setup as closely as possible:

1. Open `/workspace` and confirm the trust ribbon and market-data state are truthful.
2. Confirm current price and day/week/month charts are either real and traceable or clearly unavailable.
3. Switch at least one secondary root from the workspace and confirm the selected root, charts, and decision pack stay in sync.
4. Open a signal detail page and confirm confidence, skeptic, invalidation, journal, and related-signal surfaces render.
5. Open `/workspace/council` and confirm role prompts are visible and remain signals-only.
6. Open `/workspace/runtime`, edit a draft prompt, preview the diff, then dismiss or restore it without changing the approved prompt.
7. Add a journal note with tags, then verify `/workspace/journal` can filter by that tag and shows the tag drill-down.
8. Review delivery windows and delivery history; every send, skip, suppress, or dry-run must show a reason trail.
9. Run Telegram preview or dry-run without sending unintended messages.
10. Confirm backup and restore evidence is fresh enough for the target environment.

## Release Blockers

Block private beta until resolved or explicitly accepted as local-only:

- Product-readiness gate does not pass for the target environment.
- Browser smoke fails on workspace, runtime prompt governance, root switch, charts, or mobile layout.
- Current prices or charts are synthetic, stale without warning, or not traceable.
- Restore drill evidence is missing, stale, or from the wrong database class.
- Admin/runtime security is not enabled for staging or production-like environments.
- Prompt governance cannot diff, approve, dismiss, restore, or audit changes.
- Delivery history lacks an explainable reason for send, skip, suppress, or dry-run outcomes.
- Rollback steps are unknown or depend on destructive manual recovery.

## Accepted Private-Beta Limits

These are acceptable only when documented in release notes:

- Local or beta environments may hide live market data if the UI clearly says prices and charts are unavailable.
- Browser smoke may use deterministic market fixtures for layout and interaction confidence.
- Telegram may remain in preview or dry-run mode until operator credentials are intentionally configured.
- Performance budgets may be advisory until strict enforcement is enabled.

## Decision Record

Before allowing the build into private beta, record:

- Candidate git revision.
- Database class and restore-drill artifact path.
- Browser smoke artifact path.
- Product-readiness artifact path.
- Accepted warnings.
- Rollback owner and rollback command sequence.
- Alert routing owner and any accepted alerting deferrals.
- Analytics mode and confirmation that no secrets, prompt bodies, journal text, credentials, or API keys are collected.
- Confirmation that the app remains decision support only, with no order routing or autotrading.
