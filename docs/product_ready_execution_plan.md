# Product-Ready Execution Plan

Updated: 2026-04-28

This document is the working execution plan for taking the IMOEX app from a feature-rich operator prototype to a product-ready decision-support system. The priority order is strict:

1. Truth
2. Reliability
3. Operator workflow
4. Launch discipline

## Product-Ready Definition

The app is product-ready when:

- Prices and charts are either real and traceable or honestly hidden.
- Core operator surfaces build reliably: `dashboard`, `workspace`, `signal detail`, `journal`, `runtime`, `council`.
- Council prompts are visible, editable, version-governed, and auditable.
- Degraded and empty states are intentional, readable, and non-deceptive.
- A single operator can complete the full loop: `scan -> compare -> focus -> journal -> review`.
- Release, backup, restore, and smoke flows are repeatable.

## Execution Phases

### Phase 1: Stabilize

Goal: make the product trustworthy under normal and degraded conditions.

Exit criteria:

- Product-readiness health gate is available and exercised in smoke flows.
- No synthetic user-facing prices remain on operator pages.
- All major surfaces have explicit empty/error/degraded states.
- Prompt management supports edit, reset, and audit visibility.
- Targeted regression coverage exists for health, workspace, runtime, and market-data truthfulness.

### Phase 2: Operator-Ready Beta

Goal: make the app usable as a daily operator cockpit.

Exit criteria:

- Watchlist becomes a stable daily working layer.
- Delivery history explains `sent / skipped / suppressed`.
- End-of-day and post-resolution review bundles are usable.
- Quality drill-downs by root, horizon, provider, and role are readable.
- First-run onboarding exists for a new operator.

### Phase 3: Product-Ready

Goal: make the product operationally safe for repeated real usage.

Exit criteria:

- Backup and restore workflow is documented and exercised.
- Audit trail covers runtime edits, prompt edits, workflow transitions, and delivery actions.
- Security baseline exists for local access and secret handling.
- Runbooks exist for degraded feeds, stale reference data, and delivery failures.

### Phase 4: Launch Hardening

Goal: make shipping and rollback boring.

Exit criteria:

- Release checklist and rollback checklist are documented.
- Smoke suite runs against launch-critical surfaces.
- Reliability soak pass is completed.
- Alerting exists for feed loss, stale references, scheduler drift, and backup failures.

## Priority Backlog

### P0

- Product-readiness health gate and release smoke.
- Truthful market-data contract across all operator surfaces.
- Unified degraded-state system.
- Prompt governance baseline with preview and auditability.
- Performance baseline for workspace and compare-heavy views.

### P1

- Morning Command Brief for the daily operator ritual.
- Watchlist upgrade for daily use.
- Review loop: end-of-day, post-resolution, tagging, drill-downs.
- Notification explainability.
- Backup, restore, and operator runbooks.
- Operator onboarding and glossary.

### P2

- Provider anomaly analytics.
- UX compression and keyboard-first polish.
- Mobile sanity pass.

## Completed Stabilization Work

The first stabilization pass established the basic product-ready control plane.

- [x] Add a product-readiness execution plan to the repository.
- [x] Add a machine-readable product-readiness health gate for key operator surfaces.
- [x] Wire the health gate into the local smoke flow.
- [x] Audit degraded states across workspace, signal detail, council, and runtime pages.
- [x] Add prompt template versioning, diff, validation, restore, approval, dismiss, and audit trail.
- [x] Add the autonomous delivery operating model with Product, Systems Analyst, UI/UX, Engineering, and QA/Release roles.
- [x] Complete the five-role readiness audit and define the next stabilization tranche.

## Current Tranche

This tranche is `Operator-Ready Beta`. It turns the stabilized control plane into a daily operator workflow that is understandable on first use and repeatable across review cycles.

- [x] Add performance budgets and capture baseline timings for workspace, signal detail, runtime, council, and compare-heavy views.
- [x] Add release and rollback checklists.
- [x] Add a single local release-check command that runs the minimum release gates.
- [x] Add backup restore drill support and verification.
- [x] Expand product-readiness checks with backup freshness, scheduler health, delivery readiness, migration status, and environment market-data policy.
- [x] Add browser-level smoke coverage for workspace and runtime prompt governance.
- [x] Add market-data provider failure circuit-breaker and tighten degraded-mode performance budgets.
- [x] Add security baseline for admin and runtime-control APIs with product-readiness enforcement.
- [x] Add runtime-page operator UI for saving and clearing the admin API key locally.
- [x] Expand browser smoke to cover current price plus day/week/month chart rendering and drag measurement.
- [x] Add Postgres backup and restore-drill runbook support for production-like deployments.
- [x] Add CI workflow for focused release checks and browser smoke on product-ready branches.
- [x] Identify and complete the first low-risk extraction from the large dashboard route module.
- [x] Enforce staging/production launch policy for fresh live market data and restore-drill evidence.
- [x] Extract reusable page sidebar rendering into a dedicated dashboard sidebar module.
- [x] Extract pure market-panel chart helpers into a dedicated dashboard market module.
- [x] Wire active market-panel HTML rendering through the dedicated dashboard market module.
- [x] Remove legacy in-file market renderer copies after a green verification pass.
- [x] Add a small import-boundary check to keep market rendering outside the route module.
- [x] Extract trust-ribbon rendering into a dedicated dashboard trust module with a boundary check.
- [x] Extract watchlist rendering into a dedicated dashboard watchlist module with a boundary check.
- [x] Extract decision timeline and review-bundle rendering into a dedicated dashboard decision module with boundary checks.
- [x] Extract confidence decomposition and similar-setup rendering into a dedicated dashboard insight module with boundary checks.
- [x] Extract horizon-comparison and signal-diff rendering into a dedicated dashboard comparison module with boundary checks.
- [x] Extract workspace root-pulse cards and signal-lane tiles into a dedicated dashboard workspace module with boundary checks.
- [x] Extract action, journal, and related-signal card rendering into a dedicated dashboard cards module with boundary checks.
- [x] Extract journal decision-log and journal-tape card rendering into a dedicated dashboard journal module with boundary checks.
- [x] Extract runtime/control-panel helper rendering into a dedicated dashboard control module with boundary checks.
- [x] Extract delivery-window and delivery-activity rendering into a dedicated dashboard delivery module with boundary checks.
- [x] Extract compact dashboard signal-list rendering into a dedicated dashboard signal-list module with boundary checks.
- [x] Extract workflow-state chip and panel rendering into a dedicated dashboard workflow module with boundary checks.
- [x] Extract metric, lifecycle timeline, and horizon-pulse visualization rendering into a dedicated dashboard visuals module with boundary checks.
- [x] Extract quality-pair and journal-filter helper rendering into a dedicated dashboard quality module with boundary checks.
- [x] Extract surface-state strip rendering into a dedicated dashboard surface module with boundary checks.
- [x] Extract delivery-activity export serialization into a dedicated dashboard export module with boundary checks.
- [x] Extract dashboard language cookie/query resolution into a dedicated dashboard language module with boundary checks.
- [x] Extract dashboard feature-gate enforcement into a dedicated dashboard gate module with boundary checks.
- [x] Extract page hint copy into a dedicated dashboard page-hints module with boundary checks.
- [x] Extract page utility shell rendering into a dedicated dashboard page-shell module with boundary checks.
- [x] Extract delivery snapshot data builders into a dedicated dashboard delivery-data module with boundary checks.
- [x] Extract workspace snapshot data builders into a dedicated dashboard workspace-data module with boundary checks.
- [x] Prune route-level delivery data contract imports after data-builder extraction with boundary checks.
- [x] Extract council role-label mapping into a dedicated dashboard council-data module with boundary checks.
- [x] Extract reusable council prompt-context text helpers into the dashboard council-data module with boundary checks.
- [x] Extract runtime prompt approval-state labeling into the dashboard control module with boundary checks.
- [x] Extract runtime prompt version and preview fallback helpers into the dashboard control module with boundary checks.
- [x] Extract runtime prompt history rendering into the dashboard control module with boundary checks.
- [x] Remove obsolete legacy runtime prompt-card renderer after the dedicated renderer path is covered.
- [x] Start Operator-Ready Beta with daily watchlist queue metadata and UI cards for priority, focus reason, and review state.
- [x] Add workspace Attention Inbox for the highest-priority signal/root next actions.
- [x] Add watchlist review actions so the daily queue can be marked reviewed directly from the workspace.
- [x] Add watchlist filters for review state, root, and signal-linked versus root-level items.
- [x] Add first-run workspace onboarding and an operator glossary for trust, price, horizons, council roles, stale states, and prompt governance.
- [x] Expand the workspace review bundle with end-of-day queue counts, watched roots, outcome summaries, tag suggestions, and next review actions.
- [x] Add lightweight journal tag capture from workspace quick capture and render saved tags in journal cards.
- [x] Add notification reason trails to delivery activity cards so sent, skipped, and suppressed actions explain why they happened.
- [x] Confirm browser smoke already covers multi-root and mobile current-price plus day/week/month chart confidence.
- [x] Add watchlist bulk review and remove-from-queue actions for the currently filtered daily queue.
- [x] Add browser-local onboarding collapse and dismiss controls so experienced operators can keep the cockpit compact.
- [x] Extend delivery activity CSV/JSONL exports with computed reason labels for offline notification review.
- [x] Add journal tag filters and tag quality drill-downs for the review loop.
- [x] Run the full Playwright browser smoke against workspace, runtime prompt governance, multi-root switching, and day/week/month chart confidence.
- [x] Add a private-beta acceptance checklist with evidence-pack requirements and release blockers.
- [x] Define external alerting expectations for feed loss, stale references, scheduler drift, backup failures, and product-readiness failures.
- [x] Define a privacy-first product analytics event catalog before adding any telemetry.
- [x] Add private-beta sales-readiness positioning, demo narrative, support boundaries, and onboarding checklist without pricing or deployment commitments.
- [x] Add a local private-beta evidence manifest generator so candidate artifacts can be checked without authorizing deployment, pricing, or execution.
- [x] Add a private-beta release-notes template for accepted warnings, explicit non-goals, support boundaries, rollback, and decision owner.
- [x] Add a local private-beta candidate evidence wrapper that collects release-check logs, product-readiness/admin snapshots, draft release notes, and an evidence manifest without authorizing launch.
- [x] Add a private-beta evidence validator so draft/full candidate packs can be checked for required artifacts and no-launch/no-pricing/no-order-routing guardrails.
- [x] Add behavioral release-gate tests for the private-beta evidence validator, including complete, draft-missing, and forbidden-launch-flag manifests.
- [x] Tighten private-beta evidence validation so browser smoke, restore drill, and performance baseline artifacts are checked for required content, not just file presence.
- [x] Add an operator-readable private-beta candidate summary so evidence directories can be reviewed without opening multiple JSON files.
- [x] Add evidence validation status plus warning/failure rollups to the private-beta candidate summary for faster operator review.
- [x] Add candidate git revision, working-tree state, and git-status snapshot to private-beta candidate summaries.
- [x] Add an opt-in clean-git guard to private-beta candidate generation for final candidate approval.
- [x] Add candidate review status, skipped-gate rollup, and next actions to private-beta candidate summaries.
- [x] Require a known candidate git revision in full private-beta evidence validation while allowing draft warning mode.
- [x] Add a candidate-local acceptance checklist draft to private-beta candidate output directories.
- [x] Prefill candidate-local acceptance checklist drafts with candidate metadata, artifact paths, validation status, and safety flags.
- [x] Wire candidate-local acceptance checklist drafts into private-beta evidence manifests.
- [x] Validate that full private-beta evidence includes a candidate-local acceptance checklist prefill and no-authorization safety phrase.
- [x] Validate that full private-beta release notes are completed and do not contain unresolved template placeholders.
- [x] Require prepared release notes for full private-beta candidate generation while keeping draft evidence explicit.
- [x] Validate that full private-beta release notes explicitly confirm every support-boundary item as accepted.
- [x] Validate that full private-beta release notes include decision status, concrete owner, and UTC decision timestamp.
- [x] Validate that full private-beta release notes include concrete rollback owner, revision, artifact, stop-owner, and verification coverage.
- [x] Validate that full private-beta release notes mark every operator walkthrough check as pass.
- [x] Block draft private-beta evidence if release notes claim the candidate is accepted.
- [x] Validate that full private-beta release notes record accepted warnings as None or concrete entries.
- [x] Validate that accepted warning entries include warning, owner, and expiry or follow-up.
- [x] Validate that full private-beta release notes record a truthful market-data mode.
- [x] Validate that full private-beta release notes candidate revision matches the evidence manifest.
- [x] Validate that full private-beta release notes analytics mode matches the evidence manifest.
- [x] Validate that full private-beta release notes record an explicit Telegram mode.
- [x] Include Telegram preview JSON in private-beta evidence manifests and validate preview readiness without authorizing sends.
- [x] Include Telegram ops preview JSON in private-beta evidence manifests and validate alert preview readiness without authorizing sends.
- [x] Add Telegram delivery and ops preview evidence links to the private-beta release notes template.
- [x] Validate that full private-beta release notes include concrete Telegram delivery and ops preview evidence links.
- [x] Start Morning Command Brief with a read-only workspace panel for market truth, top attention, review delta, and do-not-chase warnings.
- [x] Add a typed Morning Command Brief API contract so `/api/v1/workspace` exposes the daily brief without scraping HTML.
- [x] Archive and validate the Morning Command Brief workspace snapshot in private-beta evidence so the daily ritual is acceptance-checkable.
- [x] Add Morning Command Brief visibility to the browser-smoke evidence contract.
- [x] Align acceptance checklist wording with release-note validation for Workspace snapshot evidence links.

## Immediate Next Steps

Safe cleanup is now at the point where remaining extractions are no longer obvious low-risk tail work. Further route-module reductions should happen only when they support a product feature or a well-scoped renderer migration with browser coverage.

1. Productization: define packaging, pricing, and deployment only after explicit operator approval.
2. Private-beta readiness: run the full acceptance checklist and evidence manifest against a non-production candidate build.
3. Launch hardening: collect external alert destination test evidence once a deployment target is chosen.
4. Product analytics: implement opt-in/local-only telemetry only after explicit approval and privacy tests.
