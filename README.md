# IMOEX trading system (signals-only)

This repo contains a **signals-only** MOEX futures research/ops stack.

## Invariants

- **No autotrading**: no order placement/cancel/replace.
- **Broker-agnostic contracts**: adapters live under `libs/adapters/*`.

## Quick start

```powershell
pip install -e ".[dev]"
alembic upgrade head
uvicorn apps.api.main:app --reload
```

## User surfaces

The primary user-facing interface is now:

- browser workspace: `/workspace`
- signal detail page: `/workspace/signals/{signal_id}`
- journal workspace: `/workspace/journal`
- notification preferences center: `/workspace/preferences`
- Telegram brief: `/api/v1/notifications/telegram/preview` and Telegram bot delivery with event-aware rules and quiet-hours suppression
- scheduler-driven Telegram jobs: `signal_open`, `digest`, `resolution`, `post_mortem`
- delivery calendar visible in `/workspace` and `/workspace/preferences`
- user delivery actions in the browser: `Send now` and one-shot `Skip next` for each Telegram window
- advanced delivery actions in the browser: `Undo skip` and `Send now ignoring quiet hours`
- delivery activity feed in `/workspace` and `/workspace/preferences` showing sends, suppressions and manual actions
- delivery activity feed also supports filtering and grouped summaries by event kind, root scope and status
- delivery activity feed supports pagination and quick export to `csv` / `jsonl`
- dedicated delivery history page: `/workspace/delivery-history`

Signal and workspace pages now also include:

- probability/risk visual bands
- lifecycle timeline from signal issue to journal/resolution events
- horizon pulse view across the same root

The operations console remains available at:

- `/dashboard`

## Worker

```powershell
python -m apps.worker.runner schedule-plan
python -m apps.worker.runner schedule-leader
python -m apps.worker.runner run-schedule --dry-run
python -m apps.worker.runner export-schedule-runs --export-format jsonl
python -m apps.worker.runner notify-telegram --root Si --event-kind resolution --dry-run
python -m apps.worker.runner notify-telegram-alerts --dry-run
python -m apps.worker.runner run-schedule-loop --iterations 2 --sleep-seconds 0 --dry-run
.\scripts\smoke_local.ps1
.\scripts\run_integration.ps1
.\scripts\run_scheduler_once.ps1
.\scripts\run_scheduler_loop.ps1 --iterations 2 --sleep-seconds 0 --dry-run
.\scripts\register_windows_scheduler_task.ps1
```

Deployment recipes:

- [deployment_recipes.md](/C:/IMOEX%20trading%20system/docs/deployment_recipes.md)

