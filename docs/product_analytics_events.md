# Product Analytics Event Catalog

Updated: 2026-04-27

This catalog defines which operator actions are useful product metrics before any telemetry is implemented. It is intentionally a planning artifact: it does not add tracking code, destinations, identifiers, pricing logic, broker connectivity, or production analytics.

## Analytics Principles

- Measure operator workflow quality, not trading performance promises.
- Keep the app signals-only: no event should imply order routing, execution, portfolio advice, or brokerage integration.
- Prefer local, aggregated, opt-in analytics for private beta.
- Do not collect secrets, prompt contents, Telegram credentials, raw journal note text, API keys, or personally identifying account data.
- Treat market-data freshness and degraded state as product-trust signals, not as trade recommendations.

## Candidate Events

### Workspace Triage

- `workspace_opened`
- `root_selected`
- `root_switched`
- `focus_signal_opened`
- `compare_board_viewed`
- `market_panel_viewed`
- `market_unavailable_seen`
- `trust_ribbon_degraded_seen`

Useful dimensions:

- environment
- root
- selected horizon
- market-data status
- workspace mode
- degraded reason category

### Price And Chart Confidence

- `current_price_seen`
- `chart_timeframe_viewed`
- `chart_measurement_used`
- `chart_overlay_selected`
- `chart_unavailable_seen`

Useful dimensions:

- root
- timeframe: `1D`, `1W`, `1M`
- provider
- freshness state
- unavailable reason

### Watchlist Workflow

- `watchlist_item_added`
- `watchlist_item_reviewed`
- `watchlist_visible_items_bulk_reviewed`
- `watchlist_item_removed`
- `watchlist_visible_items_bulk_removed`
- `watchlist_filter_used`

Useful dimensions:

- root
- linked type: root or signal
- review state
- filter type
- item count bucket

### Journal And Review Loop

- `journal_note_created`
- `journal_tag_selected`
- `journal_tag_filter_used`
- `journal_tag_drilldown_viewed`
- `decision_log_viewed`
- `review_bundle_viewed`

Useful dimensions:

- note kind
- tag category
- root
- workflow state
- signal horizon

Never collect:

- raw journal title
- raw journal note
- free-form prompt text

### Council And Prompt Governance

- `council_page_viewed`
- `council_role_prompt_viewed`
- `runtime_prompt_diff_viewed`
- `runtime_prompt_draft_saved`
- `runtime_prompt_draft_approved`
- `runtime_prompt_draft_dismissed`
- `runtime_prompt_restored`

Useful dimensions:

- role key
- approval state
- validation outcome
- prompt version lifecycle state

Never collect:

- rendered prompt body
- operator secrets
- model credential values

### Delivery Explainability

- `delivery_window_viewed`
- `delivery_send_now_clicked`
- `delivery_skip_next_clicked`
- `delivery_reason_trail_viewed`
- `delivery_activity_exported`
- `telegram_preview_opened`

Useful dimensions:

- event kind
- delivery status
- root scope
- reason category
- export format

### Release And Trust Gates

- `product_readiness_viewed`
- `product_readiness_failed`
- `admin_health_viewed`
- `browser_smoke_completed`
- `release_check_completed`
- `acceptance_checklist_completed`

Useful dimensions:

- environment
- release gate status
- failing check category
- evidence artifact type

## Private-Beta Success Metrics

Use these metrics to evaluate whether the product is ready for a broader beta:

- A new operator can complete `scan -> compare -> focus -> journal -> review` without support.
- Operators use watchlist review actions instead of re-scanning from scratch every cycle.
- Journal notes contain tags often enough to make tag drill-down useful.
- Delivery skips/suppressions are explainable without reading logs.
- Runtime prompt drafts are previewed or dismissed before approval.
- Market-data unavailable states are seen and understood instead of being mistaken for live prices.
- Release evidence is attached before private-beta acceptance.

## Instrumentation Guardrails

Before adding telemetry code:

- Make analytics opt-in for private beta.
- Keep a local/offline export path for operators who do not want hosted analytics.
- Define retention and deletion behavior.
- Add tests proving secrets, prompt bodies, journal text, Telegram credentials, and API keys are not emitted.
- Add a runtime setting to disable analytics completely.
- Update `docs/private_beta_acceptance_checklist.md` with the selected telemetry mode.

## Deferred Until Explicit Approval

- Hosted analytics service selection.
- Pricing, billing, subscription, or sales funnel tracking.
- User identity beyond local operator/session labels.
- Any deployment telemetry destination.
- Any analytics event tied to order execution or brokerage behavior.
