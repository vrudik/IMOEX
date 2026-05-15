# Private-Beta Acceptance Checklist

Updated: 2026-05-14

This checklist is the final non-production acceptance gate before any private-beta deployment decision. It does not authorize production rollout, pricing, brokerage connectivity, order routing, order execution, or autotrading. The app remains signals-only decision support.

## Required Evidence Pack

Attach or archive these artifacts for the candidate build:

- Optional local candidate output from `scripts/private_beta_candidate_check.ps1` when the evidence pack is produced on the operator workstation.
- Operator-readable candidate summary from `candidate-summary.md` when `scripts/private_beta_candidate_check.ps1` is used, including candidate git revision, working-tree state, browser-smoke command status, recorded failure code/detail and completed/planned check counts when smoke fails, daily workflow evidence rollup for Morning Command Brief, Today's Operating Queue, market freshness alerts, and Readiness Next Steps, validation reconciliation flags, evidence validation status, explicit safety flags, warnings, failures, and next actions.
- Candidate-local acceptance checklist draft from `acceptance-checklist-draft.md` when `scripts/private_beta_candidate_check.ps1` is used, including the generated `Candidate Output Prefill`.
- Private-beta evidence manifest from `scripts/private_beta_evidence_pack.ps1`.
- Evidence validation JSON from `scripts/validate_private_beta_evidence.ps1`, including signals-only/no-launch/no-pricing/no-order-routing/no-autotrading manifest flags, release-check green status or draft warning status, browser-smoke checks and failure status for Morning Command Brief, Today's Operating Queue, and Readiness Next Steps visibility, workspace snapshot readiness, `daily_workflow_evidence` for Morning Command Brief, Today's Operating Queue counts/reconciliation, and Readiness Next Steps gap status, Today's Operating Queue count reconciliation, first due identity, and next-step shape against the archived watchlist, Readiness Next Steps required gap keys, market-truth reconciliation, counts, statuses, and guardrail-language checks, Telegram preview readiness, Telegram ops preview readiness, nested execution-authorization flag guards for workspace and Telegram evidence, restore-drill status, performance labels, and release-note safety phrases.
- `release_check.ps1` output showing `product readiness OK` and `OK`.
- Browser smoke JSON from `scripts/browser_smoke.ps1`, including workspace, Morning Command Brief visibility, Today's Operating Queue visibility, Readiness Next Steps visibility, market freshness alert visibility, runtime prompt governance, multi-root switch, current price, day/week/month charts, drag measurement, mobile charts, and no horizontal overflow.
- Product-readiness JSON for the target environment, including backup freshness, restore-drill evidence, scheduler, delivery, migration, market-data policy, and admin/runtime security checks.
- Admin health JSON for the target environment.
- Workspace snapshot JSON from `/api/v1/workspace`, proving the Morning Command Brief, Today's Operating Queue, Readiness Next Steps, and any market freshness alerts API contracts are present, signals-only, truthful about market-data state, and free of nested execution-authorization flags.
- Telegram preview JSON from `/api/v1/notifications/telegram/preview`, proving preview readiness without authorizing unintended sends or carrying execution-authorization flags.
- Telegram ops preview JSON from `/api/v1/notifications/telegram/ops-preview`, proving ops alert preview readiness without authorizing alert sends or carrying execution-authorization flags.
- Restore-drill summary for the target database class: SQLite restore drill for SQLite, Postgres restore drill for Postgres.
- Performance baseline output for dashboard, workspace, signal detail, runtime, council, journal, and product-readiness surfaces.
- External alerting map from `docs/alerting_expectations.md`, including destinations or explicit non-production deferral.
- Product analytics mode from `docs/product_analytics_events.md`: disabled, local-only export, or explicitly approved opt-in telemetry.
- Private-beta sales-readiness pack from `docs/private_beta_sales_readiness.md`, including positioning, demo path, support boundaries, and onboarding checklist.
- Release notes based on `docs/private_beta_release_notes_template.md`, where the release notes candidate revision and analytics mode both match the evidence manifest, Telegram mode as `disabled`, `preview`, `dry-run`, or `configured`, recording market-data mode as `live`, `hidden`, `degraded`, or `fixture for browser smoke only`, accepted warnings as `None` or concrete `warning, owner, expiry/follow-up` entries, explicit non-goals, operator walkthrough results with every check marked `pass`, support-boundary confirmation, concrete rollback owner/revision/artifact/stop-owner fields, rollback verification coverage, concrete decision owner, `yes/no/deferred` decision status, and ISO-8601 UTC decision timestamp, with no unresolved `<...>` placeholders and every support-boundary confirmation answered `yes`.
- Full local candidate generation must pass completed release notes through `scripts/private_beta_candidate_check.ps1 -PreparedReleaseNotes`; otherwise the output remains draft evidence only.
- Draft evidence must warn when `release_check.ps1` output does not include both `product readiness OK` and `[release-check] OK`.
- Draft evidence must never record `Private-beta candidate accepted: yes`; accepted candidates require final evidence without `-AllowDraft`.

## Operator Acceptance Flow

Run the acceptance flow in a non-production environment that matches the intended beta setup as closely as possible:

1. Open `/workspace` and confirm the trust ribbon and market-data state are truthful.
2. Confirm the Morning Command Brief shows market truth, top attention, review delta, and do-not-chase safeguards without order-routing or autotrading language.
3. Confirm Today's Operating Queue shows review due, reviewed today, watched roots, signal-linked counts, and an operator-readable next step without execution language.
4. Confirm Readiness Next Steps lists market-data truth, Telegram mode, daily review, and delivery reason-trail readiness without authorizing launch, pricing, order routing, or autotrading.
5. Confirm market freshness alerts appear when the selected root is hidden or degraded, explain whether the blocker is session/market-hours, clearing, missing candles, or provider availability, remain signals-only, and point to product-readiness evidence.
6. Confirm current price, day/week/month chart cards, readable level strips, visible idea corridor/change levels, and `/workspace/market` candle, line, and level-map variants are either real and traceable or clearly unavailable.
7. Switch at least one secondary root from the workspace and confirm the selected root, charts, active directional-signal corridors when present, and decision pack stay in sync.
8. Open a signal detail page and confirm confidence, skeptic, invalidation, journal, and related-signal surfaces render.
9. Open `/workspace/council` and confirm role prompts are visible and remain signals-only.
10. Open `/workspace/runtime`, edit a draft prompt, preview the diff, then dismiss or restore it without changing the approved prompt.
11. Add a journal note with tags, then verify `/workspace/journal` can filter by that tag and shows the tag drill-down.
12. Review delivery windows and delivery history; every send, skip, suppress, or dry-run must show a reason trail.
13. Run Telegram preview or dry-run without sending unintended messages.
14. Confirm backup and restore evidence is fresh enough for the target environment.

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

- Candidate git revision, and it must not be `unknown` for final candidate approval.
- Candidate git working-tree state and `git-status.txt` snapshot when local candidate tooling is used.
- Confirmation of a clean git working tree for final candidate approval, or an explicitly accepted dirty-tree exception documented in release notes.
- Operator-readable candidate summary path.
- Candidate-local acceptance checklist draft path.
- Generated `Candidate Output Prefill` values reviewed for this candidate.
- Candidate summary next actions.
- Candidate summary validation status and accepted warnings/failures.
- Candidate summary safety flags, including `autotrading_authorized=false`, reviewed from the archived `candidate_summary` manifest artifact when local candidate tooling is used.
- Candidate summary daily workflow evidence rollup reviewed, including Morning Command Brief market/Telegram status, Today's Operating Queue counts, first due item, next step, validator reconciliation against the archived workspace watchlist, market freshness alert count, keys, required-key status, signals-only status, guardrail-language status, and Readiness Next Steps open/ready counts, required keys, market-truth reconciliation, and guardrail-language status.
- Private-beta evidence manifest path.
- Private-beta evidence validation path.
- Database class and restore-drill artifact path.
- Browser smoke artifact path.
- Product-readiness artifact path.
- Workspace snapshot JSON artifact path, with Morning Command Brief, Today's Operating Queue, Readiness Next Steps, and any market freshness alerts `signals_only=true`.
- Telegram preview JSON artifact path.
- Telegram ops preview JSON artifact path.
- Accepted warnings.
- Release notes path and decision owner.
- Confirmation that release notes candidate revision matches the evidence manifest.
- Confirmation that release notes analytics mode matches the evidence manifest.
- Confirmation that release notes record Telegram mode as `disabled`, `preview`, `dry-run`, or `configured`.
- Confirmation that release notes link Workspace snapshot JSON, Telegram preview JSON, and Telegram ops preview JSON evidence artifacts.
- Confirmation that release notes record market-data mode as `live`, `hidden`, `degraded`, or `fixture for browser smoke only`.
- Confirmation that release notes record accepted warnings as `None` or concrete `warning, owner, expiry/follow-up` entries.
- Confirmation that release notes mark every operator walkthrough check as `pass`.
- Confirmation that release notes include a concrete decision owner, `yes/no/deferred` decision status, and ISO-8601 UTC decision timestamp.
- Confirmation that any `Private-beta candidate accepted: yes` decision is backed by final evidence, not draft validation.
- Confirmation that release notes include concrete rollback owner, previous revision, backup/restore artifact, stop command/process owner, and rollback verification coverage.
- Confirmation that release notes have no unresolved template placeholders.
- Confirmation that release notes answer every support-boundary confirmation as `yes`.
- Confirmation that final local candidate generation used `-PreparedReleaseNotes` instead of template draft release notes.
- Rollback owner and rollback command sequence.
- Alert routing owner and any accepted alerting deferrals.
- Analytics mode and confirmation that no secrets, prompt bodies, journal text, credentials, or API keys are collected.
- Private-beta positioning owner and confirmation that support boundaries were accepted before the walkthrough.
- Confirmation that the app remains decision support only, with no order routing or autotrading.
