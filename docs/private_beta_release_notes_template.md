# Private-Beta Release Notes Template

Candidate: `<git revision from evidence manifest or build label containing it>`
Prepared by: `<owner>`
Prepared at: `<UTC timestamp>`

This release-note record does not authorize production deployment, pricing, brokerage connectivity, order routing, autotrading, or investment recommendations. The app remains signals-only decision support.

## Candidate Summary

- Target environment: `<local / beta / staging-like>`
- Database class: `<sqlite / postgres>`
- Primary root tested: `<root>`
- Secondary root tested: `<root>`
- Analytics mode: `<disabled / local-only-export / approved-opt-in-telemetry>`
- Telegram mode: `<disabled / preview / dry-run / configured>`
- Market-data mode: `<live / hidden / degraded / fixture for browser smoke only>`

## Evidence Links

- Private-beta evidence manifest: `<path>`
- Release-check log: `<path>`
- Browser-smoke JSON: `<path>`
- Product-readiness JSON: `<path>`
- Admin-health JSON: `<path>`
- Workspace snapshot JSON: `<path>`
- Telegram preview JSON: `<path>`
- Telegram ops preview JSON: `<path>`
- Restore-drill summary: `<path>`
- Performance baseline JSON: `<path>`
- External alerting map: `docs/alerting_expectations.md` or `<target-specific path>`
- Sales-readiness pack: `docs/private_beta_sales_readiness.md`

## Accepted Warnings

List every warning that is acceptable for this candidate. If there are no accepted warnings, write `None`.

- `<warning, owner, expiry or follow-up>`

## Explicit Non-Goals

These are not part of this candidate unless a separate explicit decision exists:

- Pricing, billing, subscription terms, refunds, or paid support commitments.
- Production deployment, uptime SLA, pager coverage, or managed operations.
- Broker connection, order routing, autotrading, account management, or execution advice.
- Guaranteed signal outcomes, profit claims, or investment recommendations.
- Collection of secrets, prompt bodies, raw journal notes, credentials, or API keys through analytics.

## Operator Walkthrough Result

- Workspace trust ribbon checked: `<pass/fail/not run>`
- Morning Command Brief checked: `<pass/fail/not run>`
- Current price and day/week/month charts checked: `<pass/fail/not run>`
- Root switch checked: `<pass/fail/not run>`
- Signal detail checked: `<pass/fail/not run>`
- Council prompts checked: `<pass/fail/not run>`
- Runtime prompt diff/dismiss/restore checked: `<pass/fail/not run>`
- Journal tags and filters checked: `<pass/fail/not run>`
- Delivery reason trails checked: `<pass/fail/not run>`
- Telegram preview/dry-run checked: `<pass/fail/not run>`
- Backup/restore evidence checked: `<pass/fail/not run>`

## Support Boundary Confirmation

- Candidate understands this is decision support only: `<yes/no>`
- Candidate accepts support boundaries before walkthrough: `<yes/no>`
- Candidate understands market-data truthfulness policy: `<yes/no>`
- Candidate understands secrets must not be pasted into screenshots, logs, or issue comments: `<yes/no>`

## Rollback Record

- Rollback owner: `<owner>`
- Previous application revision: `<revision>`
- Backup or restore artifact: `<path>`
- Stop command or process owner: `<command/owner>`
- Verification after rollback: `product-readiness`, `admin health`, `local smoke`, `Telegram preview/dry-run`

## Decision

- Private-beta candidate accepted: `<yes/no/deferred>`
- Decision owner: `<owner>`
- Decision timestamp: `<UTC timestamp>`
- Follow-up issues: `<links or list>`
