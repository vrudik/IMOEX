# Deployment Recipes

## Windows Task Scheduler

The simplest Windows deployment is a once-per-minute task that runs one leader-aware scheduler iteration.

Register the task:

```powershell
.\scripts\register_windows_scheduler_task.ps1
```

Run under `SYSTEM` instead of the current user:

```powershell
.\scripts\register_windows_scheduler_task.ps1 -RunAsSystem
```

Remove the task:

```powershell
.\scripts\unregister_windows_scheduler_task.ps1
```

Recommended policy:

- run every 1 minute
- `MultipleInstances = IgnoreNew`
- restart on failure up to 3 times with 1 minute interval
- execution time limit 5 minutes
- keep scheduler logic leader-aware, not OS-task aware

## Cron

Use the checked-in template:

- [imoex_scheduler.cron](/C:/IMOEX%20trading%20system/infra/deploy/cron/imoex_scheduler.cron)

Recommended Linux policy:

- one cron line every minute for `run-schedule-loop --iterations 1 --sleep-seconds 0`
- optional separate nightly backup line
- redirect stdout/stderr to log files or systemd journal
- rely on DB leader lease if multiple hosts may hit the same database

## Docker Compose

The repository now exposes two scheduler-oriented compose profiles in [docker-compose.yml](/C:/IMOEX%20trading%20system/infra/docker/docker-compose.yml):

- `scheduler`: one-shot loop iteration, useful for manual smoke runs
- `scheduler-daemon`: long-running loop with `restart: unless-stopped`

Example:

```bash
docker compose -f infra/docker/docker-compose.yml --profile scheduler-daemon up --build scheduler_daemon
```

Recommended policy:

- keep `SCHEDULER_POLL_INTERVAL_SECONDS` below the leader lease duration
- keep leader lease at least 2-3x larger than the poll interval
- use Postgres in shared environments
- treat the database leader lease as the source of truth for active scheduler ownership

## Recovery

Operational recovery checklist:

1. Check `GET /api/v1/health/scheduler-leader`.
2. Check `GET /api/v1/health/schedule-runs`.
3. Export scheduler history if needed through `GET /api/v1/health/schedule-runs/export` or `python -m apps.worker.runner export-schedule-runs`.
4. Preview or send ops alerts through `GET /api/v1/notifications/telegram/ops-preview` or `python -m apps.worker.runner notify-telegram-alerts --dry-run`.
5. If the leader is stale, wait for lease expiry before forcing a new instance.
6. If a host is unhealthy, restart only the scheduler process or task, not the database first.
7. If jobs repeat unexpectedly, inspect `idempotency_key` collisions in scheduler history before changing cadence.
