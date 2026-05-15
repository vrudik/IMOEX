# Private-Beta Sales Readiness

Updated: 2026-04-27

This document defines the safe sales-readiness package for a private-beta IMOEX decision-support build. It is not a pricing sheet, production deployment approval, investment promise, broker integration plan, or order-routing scope. The app remains signals-only decision support.

## Positioning

IMOEX is a trader-first decision cockpit for a single operator who needs to review futures signals, current market context, trust state, journal notes, council prompts, and delivery outcomes in one repeatable daily loop.

The private-beta promise is:

- See whether prices and charts are real, traceable, fresh, stale, or unavailable.
- Move from `scan -> compare -> focus -> journal -> review` without hopping between disconnected tools.
- Understand why a signal deserves attention, what changed, which council roles disagreed, and why notifications were sent, skipped, or suppressed.
- Preserve operator control: prompts, runtime settings, journal entries, and reviews stay auditable.
- Stay explicitly signals-only: no broker execution, no autotrading, no order placement, and no trade instruction guarantees.

## Ideal Private-Beta Operator

The first credible beta user is:

- A solo discretionary trader or analyst watching IMOEX/FORTS instruments.
- Comfortable with local or private deployment evidence packs.
- Willing to judge the system on workflow clarity, freshness honesty, signal explanation, and review discipline.
- Able to supply market-data credentials or accept an explicitly degraded local/demo mode.
- Not expecting managed accounts, financial advice, brokerage execution, or production SLA guarantees.

## Demo Narrative

Use this path for a private-beta walkthrough:

1. Open `/workspace` and start with the trust ribbon, current price, and day/week/month charts.
2. Switch roots and show that the selected instrument, market panel, watchlist, and decision pack stay in sync.
3. Use comparison and focus surfaces to explain `why now`, score changes, stale warnings, and confidence decomposition.
4. Open `/workspace/council` and show the role prompts, disagreement, skeptic pressure, and prompt governance boundaries.
5. Add or review a journal note with tags, then filter `/workspace/journal` by that tag.
6. Open delivery activity and explain reason trails for sent, dry-run, skipped, or suppressed notifications.
7. Finish with product-readiness evidence: release gate, browser smoke artifact, restore drill, alerting map, and accepted warnings.

## Support Boundaries

Included for private beta:

- Setup walkthrough for a non-production or explicitly beta environment.
- Evidence-pack review for release checks, browser smoke, product-readiness, admin health, restore drill, and alerting map.
- Prompt governance guidance for editing, previewing, dismissing, restoring, and auditing prompts.
- Market-data troubleshooting when the UI reports unavailable, stale, degraded, or hidden state.
- Feedback triage for workflow, explanation quality, review loops, and operator trust.

Not included without a separate explicit decision:

- Pricing, billing, subscription terms, refunds, or paid service commitments.
- Production deployment, uptime SLA, pager coverage, or managed operations.
- Broker connection, order routing, autotrading, account management, or execution advice.
- Guaranteed signal outcomes, profit claims, or investment recommendations.
- Handling secrets through screenshots, chat logs, issue comments, or demo recordings.

## Onboarding Checklist

Before a beta walkthrough:

- Prefer `scripts/private_beta_candidate_check.ps1` when a local workstation needs one command to collect candidate evidence into a single directory.
- Generate a private-beta evidence manifest with `scripts/private_beta_evidence_pack.ps1` or record why the walkthrough is still only a draft.
- Validate the evidence manifest with `scripts/validate_private_beta_evidence.ps1`; use `-AllowDraft` only when the walkthrough is explicitly not a launch candidate.
- Prepare candidate release notes from `docs/private_beta_release_notes_template.md`.
- Confirm `docs/private_beta_acceptance_checklist.md` has a candidate evidence pack.
- Confirm market-data policy is known: live, local fixture, hidden, stale, or degraded.
- Confirm admin/runtime security posture and local admin-key handling are understood.
- Confirm Telegram is preview or dry-run unless credentials and destination were intentionally configured.
- Confirm backup and restore drill evidence matches the target database class.
- Confirm analytics mode is disabled, local-only export, or explicitly approved opt-in.
- Confirm accepted warnings and rollback steps are written down before any environment change.

During the first operator session:

- Walk through the golden path: `scan -> compare -> focus -> journal -> review`.
- Ask the operator to identify one watched root, one ignored signal, one journal tag, and one notification reason trail.
- Capture confusion as product feedback, not as support failure.
- Stop immediately if the operator asks for brokerage execution, pricing commitments, production deployment, or investment advice.

## Qualification Questions

Use these questions to decide whether a candidate is a good private-beta fit:

- Which IMOEX/FORTS roots and horizons do you actively review?
- Do you need live market data in the first session, or is a truthful degraded/demo mode acceptable?
- What makes a signal explanation trustworthy enough to review?
- How do you currently journal invalidation, ignored signals, and post-resolution outcomes?
- Who owns backup, restore, secrets, and alerting evidence in the target environment?
- Are you evaluating decision support only, with no expectation of broker execution or guaranteed outcomes?

## Readiness Exit Criteria

The sales-readiness package is usable when:

- Positioning can be explained without mentioning pricing, brokerage, or profit promises.
- Demo flow maps only to existing product surfaces.
- Support boundaries are explicit before the first walkthrough.
- Onboarding requires evidence, market-data truth, security posture, backup/restore, alerting, and analytics-mode decisions.
- A candidate can be rejected or deferred without changing product scope.
