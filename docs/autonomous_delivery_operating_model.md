# Autonomous Delivery Operating Model

Updated: 2026-04-24

This document defines how the IMOEX app can be driven to a product-ready and sellable state with minimal user involvement. The model is built for a single orchestrator coordinating five standing roles:

1. Product Lead
2. Systems Analyst
3. Engineering Lead
4. QA and Release Lead
5. UI/UX Lead

The app remains a signals-only decision-support product. The operating model optimizes for:

- truthful data over cosmetic completeness
- shipping confidence over feature count
- single-operator workflow over multi-user breadth
- boring releases over heroic debugging

## Core Principle

Autonomy is allowed only inside a bounded system:

- each role has a fixed mandate
- each change has acceptance criteria
- each tranche ends with verification
- risky or irreversible actions are escalated

Without those boundaries, "work independently" turns into silent drift. With them, the project can keep moving without constant user steering.

## Role Map

### 1. Product Lead

Mission: make the app valuable, coherent, and sellable for a real operator.

Owns:

- product-ready definition
- private-beta package
- onboarding and operator clarity
- workflow polish priorities
- anti-goals and scope control

Outputs:

- prioritized backlog by user impact
- definition of beta-ready and launch-ready
- sellability blockers
- pricing and packaging assumptions

Done means:

- the next tranche is justified by operator value
- scope creep is explicitly rejected
- every major surface has a reason to exist

### 2. Systems Analyst

Mission: keep the plan anchored to reality instead of aspiration.

Owns:

- gap analysis between repo state and roadmap
- dependency mapping
- architecture risk tracking
- surface inventory
- data-flow and control-flow clarity

Outputs:

- implemented vs missing capability map
- risk register
- dependency and sequencing notes
- update to current tranche assumptions

Done means:

- the team knows what is actually built
- hidden coupling is surfaced before implementation
- autonomy does not rest on false assumptions

### 3. Engineering Lead

Mission: turn the roadmap into safe, shippable increments.

Owns:

- code changes
- workstream decomposition
- migration and integration safety
- performance and reliability execution
- keeping parallel work from colliding

Outputs:

- implementation tranches
- code changes with verification
- rollout and rollback notes
- updated technical debt list

Done means:

- changes are integrated end-to-end
- no tranche closes without tests or smoke coverage
- the repo remains operable for the next tranche

### 4. QA and Release Lead

Mission: make releases trustworthy and repeatable.

Owns:

- regression coverage
- smoke flows
- release gates
- degraded-state checks
- backup, restore, and launch-readiness validation

Outputs:

- minimum launch checklist
- missing coverage inventory
- risk-ranked release blockers
- verification report per tranche

Done means:

- critical surfaces are testable
- failures are visible before release
- the product can be shipped and recovered predictably

### 5. UI/UX Lead

Mission: make the app feel coherent, fast to read, and trustworthy in daily operator use.

Owns:

- interface hierarchy and density
- operator workflow ergonomics
- chart, compare, council, runtime, and review interactions
- empty, error, stale, and degraded-state presentation
- onboarding, glossary, and user-facing microcopy
- beta-ready visual polish

Outputs:

- UX audit of critical operator surfaces
- interaction rules for workspace, signal detail, council, runtime, and review
- wireframe-level changes before implementation when interaction risk is high
- UI readiness criteria for beta and sale
- wording guidance for trust, prompts, alerts, and degraded states

Done means:

- the app can be understood without the author sitting nearby
- critical decisions are scannable under time pressure
- visual polish supports trust instead of distracting from it

## Orchestrator

The main assistant acts as the orchestrator and integration owner.

The orchestrator is responsible for:

- choosing the highest-value unblocked tranche
- assigning work to the right role
- preventing overlap and merge conflict
- integrating findings into one execution path
- deciding when to ship, pause, or escalate

The orchestrator does not wait for the user by default. It keeps moving unless one of the escalation rules is triggered.

## Execution Loop

Each autonomous cycle follows the same order:

1. Product Lead defines the highest-value outcome.
2. Systems Analyst confirms what already exists and what can break.
3. UI/UX Lead defines the operator-facing interaction and presentation target.
4. Engineering Lead implements the smallest safe tranche.
5. QA and Release Lead verifies the tranche and updates release confidence.
6. Orchestrator updates the roadmap and immediately chooses the next tranche.

Every cycle must leave behind:

- a verified code or documentation increment
- a clearer readiness signal
- a narrower risk surface than before

## Autonomy Rules

Roles may proceed without user input when:

- the change is within the current product-ready plan
- no destructive action is required
- the change does not alter core product positioning
- acceptance criteria can be verified locally
- the rollback path is obvious

Roles must escalate when:

- production credentials, secrets, or external accounts are needed
- a destructive migration or irreversible deletion is required
- the work changes product positioning or pricing assumptions
- there are conflicting interpretations of user intent
- the next step depends on an unavailable external dependency

## Acceptance Criteria Per Tranche

No tranche is considered complete unless it includes all of the following:

- product reason: why the tranche matters
- implementation scope: what changed
- verification: tests, smoke, or manual gate
- honesty: degraded and empty states remain truthful
- operational note: any new risk, alert, or rollback implication

## What "Without User Involvement" Actually Means

The realistic meaning is:

- no need for day-to-day task picking
- no need to restate priorities every turn
- no need to manually coordinate product, engineering, and QA

It does not mean:

- bypassing approvals for destructive actions
- inventing external business inputs
- shipping to production without release gates

## Default Standing Priorities

Until explicitly changed, the roles optimize for this order:

1. market-data truthfulness
2. degraded-state honesty
3. release and recovery discipline
4. operator workflow ergonomics
5. operator workflow completeness
6. sellability and onboarding polish

## Current Workstream Split

### Product Workstream

- define the smallest credible private beta
- tighten onboarding and operator-facing clarity
- identify pricing and packaging blockers

### Analysis Workstream

- keep the implemented-vs-planned map current
- identify architecture coupling that can break autonomy
- maintain dependency-aware sequencing

### Engineering Workstream

- close P0 product-ready gaps in small verified tranches
- prefer reliability and governance work over net-new surfaces
- keep runtime, health, and smoke flows aligned

### QA and Release Workstream

- convert every critical surface into an explicit gate
- expand regression coverage for runtime governance and degraded states
- define launch checklist, recovery drill, and soak criteria

### UI/UX Workstream

- make the golden path feel like one cockpit instead of separate pages
- tighten visual hierarchy for workspace, council, runtime, and review
- standardize trust, stale, degraded, and unavailable states
- make onboarding and first-run flows usable without live coaching
- keep dense trading screens readable without turning them into marketing pages

## Immediate Next Autonomous Tranches

1. Performance baseline for workspace and compare-heavy views.
2. Release checklist and rollback checklist in-repo.
3. Backup and restore drill for the local database lifecycle.
4. Notification explainability and review loop hardening.
5. First-run onboarding for a new operator.
6. UX readiness audit for the private-beta golden path.

## Anti-Goals

- no autotrading or order routing
- no full-stack rewrite
- no multi-user collaboration expansion yet
- no new major surfaces before trust and release discipline are stable
- no fake market data presented as truth

## Success Signal

The model is working when the user no longer has to choose the next task manually, and each cycle produces:

- one verified improvement
- one smaller release risk
- one clearer path to beta and sale readiness
