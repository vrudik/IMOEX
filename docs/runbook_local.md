# Local runbook

## Prerequisites

- Python 3.11+
- Docker (optional, for Postgres/Redis/Prefect)

## Quick start (no Docker)

```bash
pip install -e .[dev]
copy .env.example .env
alembic upgrade head
uvicorn apps.api.main:app --reload
```

The application still supports best-effort local sqlite bootstrap, but the recommended path is now
to apply Alembic migrations before startup. When `DATABASE_URL` and `BACKUPS_DIR` are not set, the
local default state lives in a writable per-user directory under `LOCALAPPDATA` (or `TEMP` fallback on Windows).

## Runtime observability and flags

The API now includes baseline structured logging, runtime metrics and feature flags.

Environment:

```bash
LOG_LEVEL=INFO
LOG_JSON=true
FEATURE_FLAGS_JSON={"dashboard_ui":true,"telegram_delivery":true}
SCHEDULER_ENABLED=true
SCHEDULER_TIMEZONE=Europe/Moscow
SCHEDULER_JOBS_JSON=[]
SCHEDULER_POLL_INTERVAL_SECONDS=30
SCHEDULER_LEADER_LEASE_SECONDS=90
SCHEDULER_LEADER_LOCK_KEY=scheduler:leader
SCHEDULER_ALERT_STALE_AFTER_MINUTES=10
SCHEDULER_ALERT_FAILED_RUNS_LIMIT=5
```

Runtime endpoints:

```bash
curl http://127.0.0.1:8000/api/v1/health/runtime-metrics
curl http://127.0.0.1:8000/api/v1/health/feature-flags
curl http://127.0.0.1:8000/api/v1/health/modules
curl http://127.0.0.1:8000/api/v1/health/schedules
curl http://127.0.0.1:8000/api/v1/health/schedule-runs
curl http://127.0.0.1:8000/api/v1/health/schedule-runs/export
curl http://127.0.0.1:8000/api/v1/health/scheduler-leader
```

When `LOG_JSON=true`, request middleware writes structured JSON logs including request id, method,
path, status code and duration.

The module catalog endpoint exposes the current modular-monolith skeleton and its bounded-module map.
The schedules endpoint exposes the current recurring worker plan and next-run timestamps.

## Admin maintenance endpoints

With the API running locally, the current maintenance loop is available through admin endpoints:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/admin/backup -H "Content-Type: application/json" -d "{}"
curl -X POST http://127.0.0.1:8000/api/v1/admin/cleanup -H "Content-Type: application/json" -d "{\"retention_days\":30}"
curl http://127.0.0.1:8000/api/v1/admin/health
```

Backups are written to `settings.backups_dir` (default per-user local state directory).

## Adapter health endpoints

The baseline adapter layer also exposes capability and source-registry snapshots:

```bash
curl http://127.0.0.1:8000/api/v1/health/sources
curl http://127.0.0.1:8000/api/v1/health/capabilities
curl http://127.0.0.1:8000/api/v1/health/registry
```

These endpoints currently describe the normalized adapter contracts and graceful-degradation posture, not live credentialed connectivity.

## Dashboard

The project now includes a built-in delivery dashboard over the current signal pipeline.

Primary user workspace:

```bash
http://127.0.0.1:8000/workspace
```

Structured workspace snapshot:

```bash
curl http://127.0.0.1:8000/api/v1/workspace?root=Si
```

The workspace is the main human-facing screen and includes:
- root lane with current attention candidates
- signal lane with focus-signal selection
- decision pack with drivers, objections and invalidation
- visual pulse with compact chart bands and timeline
- quick journal capture directly from the page
- Telegram brief preview next to the browser workflow
- delivery calendar showing the next scheduler-driven Telegram windows
- user actions on each window: `Send now` and one-shot `Skip next`
- advanced actions on each window: `Undo skip` and `Send now ignoring quiet hours`
- delivery activity feed showing recent sends, suppressions, skips and overrides
- activity feed filters let you narrow history by event kind, root scope and delivery status
- activity feed also supports paging through history and exporting the current filtered slice as `csv` or `jsonl`
- dedicated delivery history page: `/workspace/delivery-history`

Dedicated signal page:

```bash
http://127.0.0.1:8000/workspace/signals/<signal_id>
curl http://127.0.0.1:8000/api/v1/workspace/signals/<signal_id>
```

The signal page is the focused user surface for one setup and includes:
- probability map and risk fields
- visual band chart for probabilities and risks
- lifecycle timeline from issue to journal/resolution events
- horizon pulse across the same root
- drivers, objections, invalidation and data sources
- resolution block when the signal is already closed
- journal history plus quick capture on the same page

Dedicated journal workspace:

```bash
http://127.0.0.1:8000/workspace/journal
curl http://127.0.0.1:8000/api/v1/workspace/journal
```

The journal workspace is the cross-signal memory surface and includes:
- filters by `root`, `status` and `kind`
- tape of thesis/risk/execution/post-mortem entries
- quick jump back into `/workspace` and `/workspace/signals/{signal_id}`
- raw JSON snapshot for external UI/API clients

Preferences center:

```bash
http://127.0.0.1:8000/workspace/preferences
curl http://127.0.0.1:8000/api/v1/workspace/preferences
curl -X POST http://127.0.0.1:8000/api/v1/workspace/preferences -H "Content-Type: application/json" -d "{\"default_root\":\"Si\",\"subscribed_roots\":[\"Si\",\"BR\"],\"subscribed_horizons\":[\"H4W\"],\"min_priority_score\":2,\"quiet_hours_start\":\"22:00\",\"quiet_hours_end\":\"07:00\",\"digest_limit\":3}"
```

The preferences center controls the single local user profile and includes:
- default root for `/workspace` and Telegram preview when root is omitted
- subscribed roots and horizons
- subscribed Telegram event kinds: `digest`, `signal_open`, `resolution`, `post_mortem`
- minimum priority threshold
- quiet hours window
- policy toggle for suppressing sends during quiet hours
- digest size for the brief
- delivery calendar for the next `signal_open`, `digest`, `resolution` and `post_mortem` windows
- `Send now` dispatches the selected Telegram brief immediately from the browser
- `Skip next` mutes only the next scheduler-driven run for that event type
- activity feed shows the latest delivery results and manual calendar actions
- grouped summaries in the activity feed show quick counts by event kind, root and status
- export uses the current activity filters through `GET /api/v1/workspace/delivery/activity/export`
- full-screen audit trail is available at `GET /api/v1/workspace/delivery-history` and `/workspace/delivery-history`

Operations console:

Open in browser:

```bash
http://127.0.0.1:8000/dashboard
```

Structured snapshot:

```bash
curl http://127.0.0.1:8000/api/v1/dashboard?root=Si
```

The dashboard aggregates:
- root universe and deep-dive state
- active and recent signals
- evaluation summary
- admin health
- source quality pair summaries

## Telegram notifications

Baseline Telegram delivery is now available through preview/send API endpoints.

Configure in `.env`:

```bash
TELEGRAM_ENABLED=true
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...
```

Preview a message without delivery:

```bash
curl http://127.0.0.1:8000/api/v1/notifications/telegram/preview?root=Si
curl "http://127.0.0.1:8000/api/v1/notifications/telegram/preview?root=Si&event_kind=resolution"
```

Send the message:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/notifications/telegram/send -H "Content-Type: application/json" -d "{\"root\":\"Si\",\"limit\":3}"
```

Dry-run send:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/notifications/telegram/send -H "Content-Type: application/json" -d "{\"root\":\"Si\",\"limit\":3,\"dry_run\":true}"
curl -X POST http://127.0.0.1:8000/api/v1/notifications/telegram/send -H "Content-Type: application/json" -d "{\"root\":\"Si\",\"event_kind\":\"resolution\",\"ignore_quiet_hours\":true,\"dry_run\":true}"
```

Telegram readiness is also visible through:
- `GET /api/v1/health/sources`
- `GET /api/v1/admin/health`

Ops alert preview/send:

```bash
curl http://127.0.0.1:8000/api/v1/notifications/telegram/ops-preview
curl -X POST http://127.0.0.1:8000/api/v1/notifications/telegram/ops-send -H "Content-Type: application/json" -d "{\"dry_run\":true}"
```

## MOEX reference/calendar layer

The current project snapshot now includes a baseline MOEX reference/calendar service that:
- resolves `calendar_day -> trading_day`
- selects versioned session rules by effective date
- provides contract metadata for active/next contracts
- syncs `expiry_date` and `last_trade_date` into the local contract master

The layer remains local-first and deterministic by default, but it now also supports an optional
live-capable MOEX ISS sync path through the admin API.

Manual sync example:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/admin/moex-reference-sync \
  -H "Content-Type: application/json" \
  -d "{\"sync_calendar\":true,\"sync_contracts\":true,\"from_date\":\"2026-04-01\",\"to_date\":\"2026-04-07\"}"
```

This flow refreshes the in-memory MOEX reference snapshot and then persists the updated contract/session
reference state into the local contract master repository.

## T-Bank adapter setup

The first credential-ready broker adapter is `T-Bank`.

1. Copy `.env.example` to `.env`.
2. Fill `TBANK_TOKEN`.
3. Keep `TBANK_USE_SANDBOX=true` for the first local runs.
4. Optionally set `TBANK_ACCOUNT_ID` and `TBANK_SYMBOL_MAP_JSON`.

After startup, inspect:

```bash
curl http://127.0.0.1:8000/api/v1/health/registry
```

The `tbank` entry will reflect whether the token is configured and whether the adapter is in `sandbox` or `live` mode.

## ALOR adapter setup

The second credential-ready broker adapter is `ALOR`.

1. Fill `ALOR_REFRESH_TOKEN` or `ALOR_ACCESS_TOKEN` in `.env`.
2. Keep `ALOR_USE_TEST_ENV=true` for the first validation pass.
3. Optionally set `ALOR_PORTFOLIO` and `ALOR_SYMBOL_MAP_JSON`.

The adapter uses the official ALOR prod/test split:
- prod REST/WebSocket base: `https://api.alor.ru`
- test REST/WebSocket base: `https://apidev.alor.ru`
- prod refresh endpoint: `https://oauth.alor.ru/refresh`
- test refresh endpoint: `https://oauthdev.alor.ru/refresh`

After startup, inspect:

```bash
curl http://127.0.0.1:8000/api/v1/health/registry
```

The `alor` entry will reflect whether credentials are configured and whether the adapter is in `test` or `prod` mode.

## Finam adapter setup

The third credential-ready broker adapter is `Finam`.

1. Fill `FINAM_SECRET_TOKEN` or `FINAM_JWT_TOKEN` in `.env`.
2. Optionally enable `FINAM_USE_DEMO=true` for a demo-account setup.
3. Optionally set `FINAM_ACCOUNT_ID` and `FINAM_SYMBOL_MAP_JSON`.

The current adapter wiring assumes the official Finam transport surface:
- REST base: `https://trade-api.finam.ru`
- gRPC target: `trade-api.finam.ru:443`
- WebSocket base: `wss://trade-api.finam.ru`

The reconnect manager is already modeled around the documented async-session constraints, including bounded stream lifetime and expected morning maintenance window handling.

After startup, inspect:

```bash
curl http://127.0.0.1:8000/api/v1/health/registry
```

The `finam` entry will reflect whether credentials are configured and will continue to advertise reconnect-managed stream constraints through the source registry.

## BCS adapter setup

The fourth credential-ready broker adapter is `BCS`.

1. Fill `BCS_API_TOKEN` in `.env`.
2. Optionally set `BCS_CLIENT_ID`.
3. Override WebSocket URLs only if your BCS setup differs from the default values in `.env.example`.
4. Optionally set `BCS_SYMBOL_MAP_JSON`.

The current adapter wiring keeps BCS transport URLs config-driven:
- market data stream: `BCS_MARKET_DATA_WS_URL`
- order book stream: `BCS_ORDER_BOOK_WS_URL`
- futures limits stream: `BCS_LIMITS_WS_URL`

After startup, inspect:

```bash
curl http://127.0.0.1:8000/api/v1/health/registry
```

The `bcs` entry will reflect whether the token is configured and expose the stream-first market-data posture.

## Shadow comparison

Baseline shadow comparison is now available through the quality API:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/quality/shadow-compare -H "Content-Type: application/json" -d "{...}"
curl http://127.0.0.1:8000/api/v1/quality/summary?provider_a=moex&provider_b=finam
curl http://127.0.0.1:8000/api/v1/quality/source-checks-latest?provider_a=moex&provider_b=finam
```

The current compare endpoint accepts normalized bar payloads, computes overlap/mismatch metrics and persists them into the `source_quality_check` table.

## One-command smoke run (no Docker)

From repo root (PowerShell):

```powershell
.\scripts\smoke_local.ps1
```

## Docker compose

From `infra/docker`:

```bash
docker compose -f infra/docker/docker-compose.yml up --build
```

The current compose snapshot is intentionally minimal and aligned with the shipped code:
- `api`
- `worker` one-shot container for pipeline smoke
- `postgres`

Once the stack is up, apply migrations inside the API container or from your local environment:

```bash
alembic upgrade head
```

## One-command smoke run (Docker)

From repo root (PowerShell):

```powershell
.\scripts\smoke_docker.ps1
```

## Integration test (local)

Runs the integration-marked smoke tests against the local app/container wiring used by `TestClient`
and the worker CLI. Docker is not required for this check.

```powershell
.\scripts\run_integration.ps1
```

## Integration test (Finam live, opt-in)

Requires env vars: `FINAM_API_KEY`, `FINAM_SYMBOL_MAP_JSON`.

```powershell
.\scripts\run_finam_integration.ps1
```

## Integration test (BCS live, opt-in)

Requires env vars: `BCS_API_TOKEN`, `BCS_SYMBOL_MAP_JSON`.

```powershell
.\scripts\run_bcs_integration.ps1
```

## Worker commands

The worker CLI is now available through `python -m apps.worker.runner`.

- Reference sync:

```bash
python -m apps.worker.runner reference-sync
```

- Recalculate signals:

```bash
python -m apps.worker.runner recalculate --root Si
python -m apps.worker.runner recalculate --root Si --as-of 2026-04-07T12:00:00Z
```

- Replay and evaluation report:

```bash
python -m apps.worker.runner replay --root Si --as-of 2026-04-07T12:00:00Z --top-k 3 --limit 200
```

- Telegram notification send / dry-run:

```bash
python -m apps.worker.runner notify-telegram --root Si --dry-run
python -m apps.worker.runner notify-telegram --root Si --limit 3
python -m apps.worker.runner notify-telegram --root Si --event-kind resolution --ignore-quiet-hours --dry-run
```

- Create backup:

```bash
python -m apps.worker.runner backup --label manual
```

- Cleanup old operational data:

```bash
python -m apps.worker.runner cleanup --days 30
```

- Inspect and execute recurring schedule jobs:

```bash
python -m apps.worker.runner schedule-plan
python -m apps.worker.runner schedule-plan --as-of 2026-04-07T06:12:00Z
python -m apps.worker.runner schedule-leader
python -m apps.worker.runner run-schedule --dry-run
python -m apps.worker.runner run-schedule --as-of 2026-04-07T06:12:00Z
python -m apps.worker.runner run-schedule --job-id recalculate-open
python -m apps.worker.runner export-schedule-runs --export-format csv
python -m apps.worker.runner notify-telegram-alerts --dry-run
python -m apps.worker.runner run-schedule-loop --iterations 2 --sleep-seconds 0 --dry-run
.\scripts\run_scheduler_once.ps1
.\scripts\run_scheduler_loop.ps1 --iterations 2 --sleep-seconds 0 --dry-run
.\scripts\register_windows_scheduler_task.ps1
```

At this stage the worker intentionally wraps the already-implemented reference, pipeline, maintenance,
Telegram delivery and recurring schedule services. The current scheduler is config-driven and now persists
run history, idempotency keys and DB-backed locks, and it also exposes a DB-backed leader lease for
single-active-instance scheduling. It still remains a lightweight worker loop rather than a full external orchestrator.
Default scheduler jobs now include Telegram delivery lanes for `signal_open`, `digest`, `resolution` and
`post_mortem`, and those jobs honor the saved user notification preferences when `root` is omitted.

## Deployment recipes

Production-oriented launch recipes are documented in:

- [deployment_recipes.md](/C:/IMOEX%20trading%20system/docs/deployment_recipes.md)

That document now includes:

- Windows Task Scheduler registration
- cron templates
- Docker Compose scheduler daemon profile
- basic recovery policy

