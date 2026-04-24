# Product-Ready Execution Plan

Updated: 2026-04-23

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

- Watchlist upgrade for daily use.
- Review loop: end-of-day, post-resolution, tagging, drill-downs.
- Notification explainability.
- Backup, restore, and operator runbooks.
- Operator onboarding and glossary.

### P2

- Provider anomaly analytics.
- UX compression and keyboard-first polish.
- Mobile sanity pass.

## Current Tranche

This tranche is about establishing launch discipline without blocking future UX work.

- [x] Add a product-readiness execution plan to the repository.
- [x] Add a machine-readable product-readiness health gate for key operator surfaces.
- [x] Wire the health gate into the local smoke flow.
- [ ] Audit degraded states across workspace, signal detail, council, and runtime pages.
- [ ] Add prompt template versioning and restore points.
- [ ] Add performance budgets and capture baseline timings for workspace.

## Immediate Next Steps

1. Degraded-state audit: make every `no data / stale / unavailable` surface explicit and consistent.
2. Prompt governance v2: version history, diff-before-save, restore point, and validation.
3. Performance baseline: capture server build cost and front-end polling/render cost for workspace.
4. Release checklist: define the minimum pre-release verification pack.

