# Five-Role Product Readiness Audit

Updated: 2026-04-24

This audit consolidates the independent read-only reviews from the standing roles:

1. Product Lead
2. Systems Analyst
3. UI/UX Lead
4. Engineering Lead
5. QA and Release Lead

The shared conclusion is clear: the app already has a strong feature base, but product readiness now depends on turning that base into a reliable, measurable, and sellable daily cockpit.

## Private Beta Promise

The smallest credible promise:

> In 15 minutes, a single IMOEX/FORTS operator can open one cockpit, verify whether market data is trustworthy, compare the most important instruments and signals, understand what changed, read council disagreement, journal a decision, and close the day with a review trail.

The product should be sold as a disciplined decision-support cockpit, not as an AI oracle and not as an execution system.

## Role Findings

### Product Lead

Main finding: beta scope is not yet separated from the full product.

Priority gaps:

- define a sharp ICP: one active IMOEX/FORTS operator
- freeze the private-beta package
- turn onboarding into a guided first-run journey
- make review and outcomes as important as signal discovery
- package deployment, support, update policy, and pricing hypothesis

Recommended product decision:

- sell the beta around a repeatable daily loop: `scan -> compare -> focus -> journal -> review`

### Systems Analyst

Main finding: many planned capabilities are now implemented, but the docs and gates lag behind the code.

Implemented foundation:

- operator pages: workspace, signal detail, journal, delivery history, council, runtime, dashboard
- product-readiness health gate
- truthful market-data posture: live data or hidden state
- trader workflow primitives: watchlist, compare, signal diff, decision log, review bundle
- runtime prompt governance: diff, validation, versions, restore, approve, dismiss, audit
- notification suppression reasons and delivery status
- SQLite backup creation and admin health indicators
- local smoke flow

Still missing:

- performance budgets
- restore drill
- security/access baseline
- release and rollback checklist
- stronger watchlist-as-home flow
- onboarding and glossary
- live-data operational readiness policy

### UI/UX Lead

Main finding: the product can do a lot, but the first screen does not yet guide the operator strongly enough.

Top UX risks:

- the workspace feels like several powerful panels, not one cockpit
- the first viewport should answer: what matters, can I trust the data, where is price vs idea, what should I do next
- developer and diagnostic links compete with primary operator flow
- trust states are honest but too verbose for repeated daily use
- chart interactions are powerful but need one consistent toolbar and readout
- runtime prompt governance needs clearer visual risk levels
- daily review is not yet prominent enough

Recommended UX tranche:

- workspace cockpit header
- golden path reorder
- compact trust chips across all core surfaces

### Engineering Lead

Main finding: independent delivery is limited by coupling, especially in `apps/api/routes/dashboard.py`.

Critical engineering tasks:

- reconcile the execution plan with actual shipped state
- add performance baseline for workspace, signal detail, runtime, council, and compare-heavy views
- reduce collision risk in `dashboard.py`
- quarantine or remove synthetic user-facing market snapshot paths
- make schema evolution boring with migrations as source of truth
- add browser-level smoke coverage for key UI interactions

Engineering recommendation:

- run one stabilization tranche before large feature or UX work

### QA and Release Lead

Main finding: local smoke and health gates exist, but release readiness is not yet automatic or recovery-proven.

Current gates:

- health endpoints
- product-readiness gate
- local smoke script
- Docker smoke script
- API and service regression tests
- degraded-state and prompt-governance tests
- backup creation indicators
- Alembic upgrade test

Launch blockers:

- no restore drill
- SQLite backup exists, but Postgres recovery story is not equivalent
- no automated CI/release pipeline
- product-readiness does not yet cover backup freshness, scheduler health, delivery readiness, migration status, or environment market-data policy
- no performance or soak gate
- browser interactions are mostly protected by DOM marker tests, not real browser flows

Recommended QA tranche:

- create a single release check script
- add restore drill support
- expand product-readiness checks
- strengthen Docker smoke
- add browser smoke for the golden path

## Consolidated Product-Ready Gaps

P0:

- release checklist and rollback checklist
- performance baseline and budgets
- restore drill and recovery verification
- product-readiness expansion for backup, scheduler, delivery, migrations, and environment market-data policy
- security/access baseline for admin/runtime controls
- stale docs reconciled with actual capabilities

P1:

- workspace cockpit header and golden path reorder
- compact trust chips across workspace, signal, council, runtime, journal, and delivery
- watchlist as daily home
- end-of-day review surface
- notification explainability in the operator flow
- first-run onboarding and glossary
- browser smoke for key interactions

P2:

- provider anomaly analytics
- deeper quality drilldowns
- mobile polish
- dashboard module extraction beyond the first low-risk split

## Next Tranche

The next tranche is `Autonomous Delivery Stabilization`.

Goal:

- make future autonomous work safer, more measurable, and easier to verify.

Scope:

1. Reconcile product readiness docs with the current shipped state.
2. Add a release checklist and rollback checklist.
3. Add a performance baseline script or endpoint for core surfaces.
4. Add a backup restore drill.
5. Expand product-readiness with backup, scheduler, delivery, migration, and market-data policy checks.
6. Add one browser-level smoke path for workspace and runtime prompt governance.
7. Identify the first low-risk extraction from `dashboard.py` before major UI work.

Exit criteria:

- release readiness can be checked by one command
- restore can be proven on a fresh database path
- workspace and runtime have at least one browser-level smoke path
- the product-ready plan no longer contradicts implemented prompt governance and degraded-state work
- next UX work has measurable performance and release gates underneath it

## Parallel Work Rules

Until `dashboard.py` is split:

- only one implementation owner should edit it at a time
- Product and Systems Analyst should work mostly in docs and acceptance criteria
- QA and Release should work mostly in tests, scripts, and health gates
- Engineering should own service boundaries, migrations, performance, and extraction
- UI/UX should produce interaction specs before code changes to dense operator screens

## Decision

Proceed with stabilization before adding new major product surfaces.

The product is rich enough to be worth hardening. The fastest path to sale is now trust, recovery, performance, onboarding, and release discipline.
