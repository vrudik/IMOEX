# Local runbook

## Prerequisites

- Python 3.12
- Docker (optional, for Postgres/Redis/Prefect)

## Quick start (no Docker)

```bash
pip install -e .[dev]
copy .env.example .env
uvicorn apps.api.main:app --reload
```

Note: without DB migrations, the API will use demo in-memory seeds.

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

If `docker build` fails on Windows due to inaccessible `pytest-cache-files-*` folders in the repo root,
build using a clean context first:

```powershell
.\scripts\docker_build.ps1
docker compose -f infra/docker/docker-compose.yml up --no-build
```

Note: docker compose uses `.env.docker.example` (service hostnames, not `localhost`).

Then apply migrations (inside or outside container):

```bash
alembic upgrade head
```

## One-command smoke run (Docker)

From repo root (PowerShell):

```powershell
.\scripts\smoke_docker.ps1
```

## Integration test (Docker compose)

Runs the docker-based pipeline smoke test (opt-in):

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

- Reference sync (also backfills bars, refreshes features, generates signals best-effort):

```bash
python -m apps.worker.runner reference-sync
```

- Run the full Prefect daily pipeline (reference → resolve → metrics → notifications; optional MOEX vs Finam shadow if `FINAM_API_KEY` + `FINAM_SYMBOL_MAP_JSON`):

```bash
python -m apps.worker.runner prefect-daily --metrics-days 14 --shadow-minutes 60
```

- Compare MOEX vs Finam bars (shadow check):

```bash
python -m apps.worker.runner compare-bars --provider-b finam --contract SiM6 --minutes 60
python -m apps.worker.runner compare-bars --provider-b finam --contracts SiM6,BRM6 --minutes 60
python -m apps.worker.runner compare-bars --provider-b bcs --contracts SiM6,BRM6 --minutes 60
```

- Run Prefect shadow-quality flow (independent):

```bash
python -m apps.worker.runner shadow-quality --provider-b finam --minutes 60
python -m apps.worker.runner shadow-quality --provider-b bcs --minutes 60
```

- Cleanup old quality checks (DB retention):

```bash
python -m apps.worker.runner quality-cleanup --days 30
```

- Resolve eligible signals:

```bash
python -m apps.worker.runner resolve-signals --limit 200
```

- Compute evaluation metrics:

```bash
python -m apps.worker.runner compute-metrics --from 2026-03-01 --to 2026-03-31 --horizon H3S
```

