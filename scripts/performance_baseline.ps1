param(
  [string]$Root = "Si",
  [string]$OutputPath = "",
  [switch]$FailOnBudget
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$python = if (Test-Path $venvPython) { $venvPython } else { "python" }
$baselineRoot = Join-Path $env:TEMP "imoex-performance-baseline"
$runId = Get-Date -Format "yyyyMMddHHmmss"
$databasePath = Join-Path $baselineRoot "baseline-$runId.db"
$backupsPath = Join-Path $baselineRoot "backups-$runId"

New-Item -ItemType Directory -Force -Path $baselineRoot | Out-Null
New-Item -ItemType Directory -Force -Path $backupsPath | Out-Null

if ([string]::IsNullOrWhiteSpace($OutputPath)) {
  $OutputPath = Join-Path $baselineRoot "baseline-$runId.json"
}

$env:PYTHONPATH = "$repoRoot\.vendor;$repoRoot"
$env:DATABASE_URL = "sqlite:///$($databasePath.Replace('\', '/'))"
$env:BACKUPS_DIR = $backupsPath
$env:IMOEX_PERF_ROOT = $Root
$env:IMOEX_PERF_OUTPUT = $OutputPath
$env:IMOEX_PERF_FAIL_ON_BUDGET = if ($FailOnBudget) { "1" } else { "0" }

Write-Host "[performance-baseline] python: $python"
Write-Host "[performance-baseline] database: $databasePath"
Write-Host "[performance-baseline] output: $OutputPath"

Write-Host "[performance-baseline] priming signals"
& $python -m apps.worker.runner recalculate --root $Root | Out-Host

@'
from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.main import app


ROOT = os.environ.get("IMOEX_PERF_ROOT", "Si")
OUTPUT = Path(os.environ["IMOEX_PERF_OUTPUT"])
FAIL_ON_BUDGET = os.environ.get("IMOEX_PERF_FAIL_ON_BUDGET") == "1"

BUDGETS_MS = {
    "api_dashboard": 3000,
    "api_workspace": 5000,
    "page_workspace": 5000,
    "api_signal_detail": 3500,
    "page_signal_detail": 3500,
    "page_runtime": 5000,
    "page_council": 5000,
    "api_journal": 3500,
    "page_journal": 5000,
    "api_product_readiness": 5000,
}


def measure(client: TestClient, label: str, path: str, *, params: dict[str, str] | None = None) -> dict[str, object]:
    started = time.perf_counter()
    response = client.get(path, params=params or {})
    elapsed_ms = (time.perf_counter() - started) * 1000
    response.raise_for_status()
    budget_ms = BUDGETS_MS.get(label)
    return {
        "label": label,
        "path": path,
        "status_code": response.status_code,
        "elapsed_ms": round(elapsed_ms, 2),
        "budget_ms": budget_ms,
        "within_budget": True if budget_ms is None else elapsed_ms <= budget_ms,
        "response_bytes": len(response.content or b""),
    }


with TestClient(app) as client:
    signals_response = client.get("/api/v1/signals", params={"root": ROOT})
    signals_response.raise_for_status()
    signals = signals_response.json()
    signal_id = signals[0]["signal_id"] if signals else None

    checks: list[tuple[str, str, dict[str, str]]] = [
        ("api_dashboard", "/api/v1/dashboard", {"root": ROOT}),
        ("api_workspace", "/api/v1/workspace", {"root": ROOT}),
        ("page_workspace", "/workspace", {"root": ROOT}),
        ("page_runtime", "/workspace/runtime", {"root": ROOT}),
        ("page_council", "/workspace/council", {"root": ROOT}),
        ("api_journal", "/api/v1/workspace/journal", {"root": ROOT}),
        ("page_journal", "/workspace/journal", {"root": ROOT}),
        ("api_product_readiness", "/api/v1/health/product-readiness", {"root": ROOT}),
    ]
    if signal_id:
        checks.extend(
            [
                ("api_signal_detail", f"/api/v1/workspace/signals/{signal_id}", {}),
                ("page_signal_detail", f"/workspace/signals/{signal_id}", {}),
            ]
        )

    results = [measure(client, label, path, params=params) for label, path, params in checks]

payload = {
    "generated_at": datetime.now(UTC).isoformat(),
    "root": ROOT,
    "budgets_ms": BUDGETS_MS,
    "results": results,
    "failed_budgets": [item for item in results if item["within_budget"] is False],
}
OUTPUT.write_text(json.dumps(payload, indent=2), encoding="utf-8")

print("[performance-baseline] results")
for item in results:
    budget = item["budget_ms"] if item["budget_ms"] is not None else "-"
    status = "ok" if item["within_budget"] else "over"
    print(f"{item['label']:24} {item['elapsed_ms']:9.2f} ms budget={budget} status={status} bytes={item['response_bytes']}")

if payload["failed_budgets"] and FAIL_ON_BUDGET:
    labels = ", ".join(item["label"] for item in payload["failed_budgets"])
    raise SystemExit(f"Performance budgets exceeded: {labels}")
'@ | & $python -

Write-Host "[performance-baseline] OK"
