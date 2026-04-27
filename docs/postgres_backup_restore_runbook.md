# Postgres Backup And Restore Runbook

Updated: 2026-04-24

This runbook is for production-like deployments that use `postgresql` or `postgresql+psycopg` as `DATABASE_URL`.

## Required Tools

- `pg_dump` available on `PATH`, or set `POSTGRES_PG_DUMP_PATH`.
- `pg_restore` available on `PATH`, or set `POSTGRES_PG_RESTORE_PATH`.
- A fresh disposable target database for every restore drill.
- `ADMIN_API_KEY` set when the target environment requires protected admin endpoints.

## Backup Contract

The app creates Postgres backups through `pg_dump --format=custom --no-owner --no-privileges`.

Passwords from `DATABASE_URL` are passed through `PGPASSWORD`, not as command-line arguments.

Backup artifacts use:

```text
imoex-backup-YYYYMMDD-HHMMSS-<label>.pg.dump
```

## Restore Drill

Run against a fresh target database only:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\postgres_restore_drill.ps1 `
  -SourceDatabaseUrl "postgresql+psycopg://imoex:***@source-host:5432/imoex_prod" `
  -RestoredDatabaseUrl "postgresql+psycopg://imoex:***@restore-host:5432/imoex_restore_drill" `
  -Root Si `
  -AllowDestructiveRestore
```

The drill:

- creates a `.pg.dump` backup when `-BackupPath` is not provided
- restores it with `pg_restore --clean --if-exists --no-owner --no-privileges`
- validates restored signal/root counts
- calls product-readiness and admin health on the restored app database
- writes a JSON summary under `%TEMP%\imoex-postgres-restore-drill`

## Restore From Existing Backup

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\postgres_restore_drill.ps1 `
  -SourceDatabaseUrl "postgresql+psycopg://imoex:***@source-host:5432/imoex_prod" `
  -RestoredDatabaseUrl "postgresql+psycopg://imoex:***@restore-host:5432/imoex_restore_drill" `
  -BackupPath "C:\backups\imoex-backup-20260424-120000-prod.pg.dump" `
  -Root Si `
  -AllowDestructiveRestore
```

## Release Rule

For production-like releases, do not ship unless one of these is true:

- the SQLite `restore_drill.ps1` passed for a SQLite deployment
- the Postgres `postgres_restore_drill.ps1` passed for a Postgres deployment

The restore path must be shorter than the expected incident response window.
