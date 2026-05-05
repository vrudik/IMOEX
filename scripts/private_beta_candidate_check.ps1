param(
  [string]$Root = "Si",
  [string]$SecondaryRoot = "BR",
  [string]$OutputDir = "",
  [string]$BrowserChannel = "",
  [string]$PreparedReleaseNotes = "",
  [ValidateSet("disabled", "local-only-export", "approved-opt-in-telemetry")]
  [string]$AnalyticsMode = "disabled",
  [switch]$SkipReleaseCheck,
  [switch]$SkipFullPytest,
  [switch]$SkipDocker,
  [switch]$SkipBrowser,
  [switch]$SkipPerformance,
  [switch]$SkipRestore,
  [switch]$RequireCleanGit,
  [switch]$AllowDraftEvidence
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$python = if (Test-Path $venvPython) { $venvPython } else { "python" }
$runId = Get-Date -Format "yyyyMMddHHmmss"

if ([string]::IsNullOrWhiteSpace($OutputDir)) {
  $OutputDir = Join-Path $env:TEMP "imoex-private-beta-candidates\candidate-$runId"
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

$releaseCheckLog = Join-Path $OutputDir "release-check.log"
$browserSmokeJson = Join-Path $OutputDir "browser-smoke.json"
$productReadinessJson = Join-Path $OutputDir "product-readiness.json"
$adminHealthJson = Join-Path $OutputDir "admin-health.json"
$workspaceSnapshotJson = Join-Path $OutputDir "workspace-snapshot.json"
$telegramPreviewJson = Join-Path $OutputDir "telegram-preview.json"
$telegramOpsPreviewJson = Join-Path $OutputDir "telegram-ops-preview.json"
$restoreDrillSummary = Join-Path $OutputDir "restore-drill-summary.json"
$performanceBaselineJson = Join-Path $OutputDir "performance-baseline.json"
$releaseNotesDraft = Join-Path $OutputDir "release-notes-draft.md"
$acceptanceChecklistDraft = Join-Path $OutputDir "acceptance-checklist-draft.md"
$evidenceValidationJson = Join-Path $OutputDir "private-beta-evidence-validation.json"
$snapshotDb = Join-Path $OutputDir "candidate-snapshot.db"
$backupsDir = Join-Path $OutputDir "backups"
$evidenceDir = Join-Path $OutputDir "evidence-pack"
$gitStatusPath = Join-Path $OutputDir "git-status.txt"

New-Item -ItemType Directory -Force -Path $backupsDir | Out-Null

function Resolve-CandidateInputPath {
  param([string]$Path)

  if ([string]::IsNullOrWhiteSpace($Path)) {
    return ""
  }
  if ([System.IO.Path]::IsPathRooted($Path)) {
    return $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Path)
  }
  return $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath((Join-Path $repoRoot $Path))
}

$releaseNotesTemplatePath = Join-Path $repoRoot "docs\private_beta_release_notes_template.md"
$releaseNotesSource = $releaseNotesTemplatePath
$releaseNotesMode = "template_draft"
if (-not [string]::IsNullOrWhiteSpace($PreparedReleaseNotes)) {
  $preparedReleaseNotesResolved = Resolve-CandidateInputPath $PreparedReleaseNotes
  if (-not (Test-Path -LiteralPath $preparedReleaseNotesResolved)) {
    throw "Prepared release notes were not found: $preparedReleaseNotesResolved"
  }
  $releaseNotesSource = $preparedReleaseNotesResolved
  $releaseNotesMode = "prepared"
}

$fullCandidateAttempt = -not $AllowDraftEvidence -and -not $SkipReleaseCheck -and -not $SkipBrowser -and -not $SkipPerformance -and -not $SkipRestore
if ($fullCandidateAttempt -and $releaseNotesMode -ne "prepared") {
  throw "Full private-beta candidate generation requires completed release notes via -PreparedReleaseNotes. Use -AllowDraftEvidence for draft evidence only."
}

Copy-Item -LiteralPath $releaseNotesSource -Destination $releaseNotesDraft -Force
Copy-Item -LiteralPath (Join-Path $repoRoot "docs\private_beta_acceptance_checklist.md") -Destination $acceptanceChecklistDraft -Force

$candidateRevision = (& git -C $repoRoot rev-parse --short HEAD 2>$null)
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($candidateRevision)) {
  $candidateRevision = "unknown"
} else {
  $candidateRevision = $candidateRevision.Trim()
}

$gitStatusLines = @(& git -C $repoRoot status --short 2>$null)
if ($LASTEXITCODE -ne 0) {
  $gitStatusLines = @("git status unavailable")
}
$candidateWorktreeState = if ($gitStatusLines.Count -eq 0) {
  "clean"
} elseif ($gitStatusLines[0] -eq "git status unavailable") {
  "unknown"
} else {
  "dirty"
}
$candidateDirtyCount = if ($candidateWorktreeState -eq "dirty") { $gitStatusLines.Count } else { 0 }
if ($gitStatusLines.Count -eq 0) {
  "clean" | Set-Content -Path $gitStatusPath -Encoding UTF8
} else {
  $gitStatusLines | Set-Content -Path $gitStatusPath -Encoding UTF8
}

if ($RequireCleanGit -and $candidateWorktreeState -ne "clean") {
  throw "Private-beta candidate requires a clean git working tree. Current state: $candidateWorktreeState ($candidateDirtyCount entries). Review $gitStatusPath or rerun without -RequireCleanGit for draft evidence only."
}

function Assert-NativeSuccess {
  param([string]$Name)

  if ($LASTEXITCODE -ne 0) {
    throw "$Name failed with exit code $LASTEXITCODE"
  }
}

function Invoke-LoggedProcess {
  param(
    [string]$Name,
    [string]$LogPath,
    [string]$FilePath,
    [string[]]$ArgumentList
  )

  Write-Host "[private-beta-candidate] $Name"
  $rawOutput = @()
  $processError = $null
  $previousErrorActionPreference = $ErrorActionPreference
  try {
    $ErrorActionPreference = "Continue"
    $rawOutput = & $FilePath @ArgumentList 2>&1
    $exitCode = $LASTEXITCODE
  } catch {
    $processError = $_
    $exitCode = 1
    $rawOutput += $processError
  } finally {
    $ErrorActionPreference = $previousErrorActionPreference
  }

  $output = @(
    $rawOutput | ForEach-Object {
      if ($_ -is [System.Management.Automation.ErrorRecord]) {
        $_.ToString()
      } else {
        [string]$_
      }
    }
  )
  $output | Set-Content -Path $LogPath -Encoding UTF8
  $output | Out-Host

  if ($null -ne $processError) {
    throw "$Name failed to start: $($processError.ToString())"
  }
  if ($exitCode -ne 0) {
    throw "$Name failed with exit code $exitCode"
  }
}

function Get-ObjectPropertyValue {
  param(
    [object]$Object,
    [string]$Name,
    [object]$Default = $null
  )

  if ($null -eq $Object) {
    return $Default
  }
  $property = $Object.PSObject.Properties[$Name]
  if ($null -eq $property) {
    return $Default
  }
  if ($null -eq $property.Value) {
    return $Default
  }
  return $property.Value
}

function ConvertTo-SummaryInteger {
  param([object]$Value)

  if ($null -eq $Value -or [string]::IsNullOrWhiteSpace([string]$Value)) {
    return 0
  }
  return [int]$Value
}

function Get-SummaryArrayCount {
  param([object]$Value)

  if ($null -eq $Value) {
    return 0
  }
  return @($Value).Count
}

function ConvertTo-SummaryText {
  param([object]$Value)

  if ($null -eq $Value) {
    return ""
  }
  return (([string]$Value) -replace "\s+", " ").Trim()
}

function Assert-TextContainsAll {
  param(
    [string]$Name,
    [string]$Text,
    [string[]]$RequiredText
  )

  foreach ($required in $RequiredText) {
    if ($Text -notmatch [regex]::Escape($required)) {
      throw "$Name is missing required safety evidence: $required"
    }
  }
}

function Copy-RequiredEvidenceArtifact {
  param(
    [string]$Name,
    [string]$Source,
    [string]$Destination
  )

  if (-not (Test-Path -LiteralPath $Source)) {
    throw "$Name source file is missing: $Source"
  }
  if (-not (Test-Path -LiteralPath $Destination)) {
    throw "$Name archived evidence copy is missing from the manifest output: $Destination"
  }
  Copy-Item -LiteralPath $Source -Destination $Destination -Force
}

$acceptanceChecklistSafetyFlags = @(
  "Signals-only decision support: true",
  "Release decision authorized: false",
  "Production deployment authorized: false",
  "Pricing commitment authorized: false",
  "Order routing authorized: false",
  "Autotrading authorized: false"
)

$candidateSummarySafetyFlags = @(
  "Signals-only decision support: true",
  "Release decision authorized by this wrapper: false",
  "Production deployment authorized by this wrapper: false",
  "Pricing commitment authorized by this wrapper: false",
  "Order routing authorized by this wrapper: false",
  "Autotrading authorized by this wrapper: false"
)

Write-Host "[private-beta-candidate] output: $OutputDir"
Write-Host "[private-beta-candidate] python: $python"
Write-Host "[private-beta-candidate] root: $Root"

if (-not $SkipReleaseCheck) {
  $releaseArgs = @("-ExecutionPolicy", "Bypass", "-File", (Join-Path $repoRoot "scripts\release_check.ps1"), "-Root", $Root)
  if ($SkipFullPytest) {
    $releaseArgs += "-SkipFullPytest"
  }
  if ($SkipDocker) {
    $releaseArgs += "-SkipDocker"
  }
  if ($SkipPerformance) {
    $releaseArgs += "-SkipPerformance"
  }
  if ($SkipRestore) {
    $releaseArgs += "-SkipRestore"
  }
  if ($SkipBrowser) {
    $releaseArgs += "-SkipBrowser"
  }
  if (-not [string]::IsNullOrWhiteSpace($BrowserChannel)) {
    $releaseArgs += @("-BrowserChannel", $BrowserChannel)
  }

  Invoke-LoggedProcess "running release check" $releaseCheckLog "powershell" $releaseArgs
} else {
  "Skipped by -SkipReleaseCheck. This output directory is draft evidence only." | Set-Content -Path $releaseCheckLog -Encoding UTF8
}

$browserSmokeCommandStatus = if ($SkipBrowser) { "skipped" } else { "pending" }
$browserSmokeCommandFailure = ""
if (-not $SkipBrowser) {
  $browserArgs = @((Join-Path $repoRoot "scripts\browser_smoke.py"), "--root", $Root, "--secondary-root", $SecondaryRoot, "--output", $browserSmokeJson)
  if (-not [string]::IsNullOrWhiteSpace($BrowserChannel)) {
    $browserArgs += @("--channel", $BrowserChannel)
  }
  try {
    Invoke-LoggedProcess "running browser smoke" (Join-Path $OutputDir "browser-smoke.log") $python $browserArgs
    $browserSmokeCommandStatus = "passed"
  } catch {
    $browserSmokeCommandStatus = "failed"
    $browserSmokeCommandFailure = ConvertTo-SummaryText $_
    if (-not $AllowDraftEvidence) {
      throw
    }
    Write-Host "[private-beta-candidate] browser smoke failed; continuing as draft evidence only: $browserSmokeCommandFailure"
  }
}
$browserSmokeRecordedStatus = if ($SkipBrowser) { "skipped" } else { "" }
$browserSmokeFailureCode = ""
$browserSmokeFailureDetail = ""
$browserSmokeCompletedCheckCount = 0
$browserSmokePlannedCheckCount = 0
if (-not $SkipBrowser -and (Test-Path -LiteralPath $browserSmokeJson)) {
  try {
    $browserSmokePayload = Get-Content -Path $browserSmokeJson -Raw | ConvertFrom-Json
    $browserSmokeRecordedStatus = [string](Get-ObjectPropertyValue $browserSmokePayload "status" "")
    $browserSmokeFailureCode = [string](Get-ObjectPropertyValue $browserSmokePayload "failure_code" "")
    $browserSmokeFailureDetail = ConvertTo-SummaryText (Get-ObjectPropertyValue $browserSmokePayload "failure" "")
    $browserSmokeCompletedCheckCount = Get-SummaryArrayCount (Get-ObjectPropertyValue $browserSmokePayload "checks" @())
    $browserSmokePlannedCheckCount = Get-SummaryArrayCount (Get-ObjectPropertyValue $browserSmokePayload "planned_checks" @())
  } catch {
    $browserSmokeFailureCode = "browser_smoke_json_unreadable"
    $browserSmokeFailureDetail = ConvertTo-SummaryText $_
  }
}

Write-Host "[private-beta-candidate] priming candidate snapshot"
$env:PYTHONPATH = "$repoRoot\.vendor;$repoRoot"
$env:DATABASE_URL = "sqlite:///$($snapshotDb.Replace('\', '/'))"
$env:BACKUPS_DIR = $backupsDir
$env:APP_ENVIRONMENT = "local"
$env:MARKET_DATA_LIVE_ENABLED = "false"
$env:MOEX_REFERENCE_AUTO_SYNC_ENABLED = "false"
$env:PRODUCT_READINESS_REQUIRE_LIVE_MARKET_DATA = "false"
$env:LOG_JSON = "false"
$env:IMOEX_CANDIDATE_ROOT = $Root
$env:IMOEX_CANDIDATE_OUTPUT_DIR = $OutputDir
$env:IMOEX_CANDIDATE_PRODUCT_READINESS = $productReadinessJson
$env:IMOEX_CANDIDATE_ADMIN_HEALTH = $adminHealthJson
$env:IMOEX_CANDIDATE_WORKSPACE_SNAPSHOT = $workspaceSnapshotJson
$env:IMOEX_CANDIDATE_TELEGRAM_PREVIEW = $telegramPreviewJson
$env:IMOEX_CANDIDATE_TELEGRAM_OPS_PREVIEW = $telegramOpsPreviewJson

& $python -m apps.worker.runner recalculate --root $Root | Out-Host
Assert-NativeSuccess "candidate snapshot recalculate"

@'
from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi.testclient import TestClient

from apps.api.main import app

root = os.environ.get("IMOEX_CANDIDATE_ROOT", "Si")

with TestClient(app) as client:
    readiness = client.get("/api/v1/health/product-readiness", params={"root": root})
    readiness.raise_for_status()
    readiness_payload = readiness.json()

    admin_health = client.get("/api/v1/admin/health")
    admin_health.raise_for_status()
    admin_payload = admin_health.json()

    workspace = client.get("/api/v1/workspace", params={"root": root})
    workspace.raise_for_status()
    workspace_payload = workspace.json()

    preview = client.get("/api/v1/notifications/telegram/preview", params={"root": root})
    preview.raise_for_status()
    preview_payload = preview.json()

    ops_preview = client.get("/api/v1/notifications/telegram/ops-preview")
    ops_preview.raise_for_status()
    ops_preview_payload = ops_preview.json()

Path(os.environ["IMOEX_CANDIDATE_PRODUCT_READINESS"]).write_text(
    json.dumps(readiness_payload, indent=2),
    encoding="utf-8",
)
Path(os.environ["IMOEX_CANDIDATE_ADMIN_HEALTH"]).write_text(
    json.dumps(admin_payload, indent=2),
    encoding="utf-8",
)
Path(os.environ["IMOEX_CANDIDATE_WORKSPACE_SNAPSHOT"]).write_text(
    json.dumps(workspace_payload, indent=2),
    encoding="utf-8",
)
Path(os.environ["IMOEX_CANDIDATE_TELEGRAM_PREVIEW"]).write_text(
    json.dumps(preview_payload, indent=2),
    encoding="utf-8",
)
Path(os.environ["IMOEX_CANDIDATE_TELEGRAM_OPS_PREVIEW"]).write_text(
    json.dumps(ops_preview_payload, indent=2),
    encoding="utf-8",
)

assert readiness_payload["release_gate"] == "pass", readiness_payload
assert admin_payload["status"] in {"ok", "degraded"}, admin_payload
assert workspace_payload["morning_brief"]["signals_only"] is True, workspace_payload
assert workspace_payload["watchlist_workbench"]["signals_only"] is True, workspace_payload
assert workspace_payload["watchlist_workbench"]["total_items"] == len(workspace_payload["watchlist"]), workspace_payload
assert workspace_payload["watchlist_workbench"]["next_step"], workspace_payload
assert preview_payload["root"] == root, preview_payload
assert isinstance(ops_preview_payload["alert_items"], list), ops_preview_payload
print("[private-beta-candidate] API snapshots OK")
'@ | & $python -
Assert-NativeSuccess "candidate API snapshots"

if (-not $SkipPerformance) {
  Invoke-LoggedProcess "capturing performance baseline" (Join-Path $OutputDir "performance-baseline.log") "powershell" @(
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    (Join-Path $repoRoot "scripts\performance_baseline.ps1"),
    "-Root",
    $Root,
    "-OutputPath",
    $performanceBaselineJson
  )
}

if (-not $SkipRestore) {
  Invoke-LoggedProcess "running restore drill" (Join-Path $OutputDir "restore-drill.log") "powershell" @(
    "-ExecutionPolicy",
    "Bypass",
    "-File",
    (Join-Path $repoRoot "scripts\restore_drill.ps1"),
    "-Root",
    $Root,
    "-OutputPath",
    $restoreDrillSummary
  )
}

$skippedGates = @()
if ($SkipReleaseCheck) {
  $skippedGates += "release_check"
}
if ($SkipBrowser) {
  $skippedGates += "browser_smoke"
}
if ($SkipPerformance) {
  $skippedGates += "performance_baseline"
}
if ($SkipRestore) {
  $skippedGates += "restore_drill"
}
$usesDraftReleaseNotes = $releaseNotesMode -ne "prepared"

$summaryPath = Join-Path $OutputDir "candidate-summary.json"
$summaryMarkdownPath = Join-Path $OutputDir "candidate-summary.md"

$workspaceSummaryPayload = Get-Content -Path $workspaceSnapshotJson -Raw | ConvertFrom-Json
$morningBriefPayload = Get-ObjectPropertyValue $workspaceSummaryPayload "morning_brief"
$watchlistWorkbenchPayload = Get-ObjectPropertyValue $workspaceSummaryPayload "watchlist_workbench"
$watchedRootsValue = Get-ObjectPropertyValue $watchlistWorkbenchPayload "watched_roots" @()
$watchedRoots = @($watchedRootsValue | ForEach-Object { [string]$_ } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
$firstDueWatchKey = [string](Get-ObjectPropertyValue $watchlistWorkbenchPayload "first_due_watch_key" "")
$firstDueRootCode = [string](Get-ObjectPropertyValue $watchlistWorkbenchPayload "first_due_root_code" "")
$firstDueSignalId = [string](Get-ObjectPropertyValue $watchlistWorkbenchPayload "first_due_signal_id" "")
$firstDueLabel = if (-not [string]::IsNullOrWhiteSpace($firstDueSignalId)) {
  "$firstDueSignalId ($firstDueRootCode)"
} elseif (-not [string]::IsNullOrWhiteSpace($firstDueWatchKey)) {
  "$firstDueWatchKey ($firstDueRootCode)"
} else {
  "none"
}
$dailyWorkflowSummary = [ordered]@{
  morning_brief = [ordered]@{
    signals_only = [bool](Get-ObjectPropertyValue $morningBriefPayload "signals_only" $false)
    market_status = [string](Get-ObjectPropertyValue $morningBriefPayload "market_status" "unknown")
    telegram_status = [string](Get-ObjectPropertyValue $morningBriefPayload "telegram_status" "unknown")
    top_attention_count = Get-SummaryArrayCount (Get-ObjectPropertyValue $morningBriefPayload "top_attention" @())
    dont_chase_count = Get-SummaryArrayCount (Get-ObjectPropertyValue $morningBriefPayload "dont_chase" @())
  }
  todays_operating_queue = [ordered]@{
    signals_only = [bool](Get-ObjectPropertyValue $watchlistWorkbenchPayload "signals_only" $false)
    total_items = ConvertTo-SummaryInteger (Get-ObjectPropertyValue $watchlistWorkbenchPayload "total_items" 0)
    review_due_items = ConvertTo-SummaryInteger (Get-ObjectPropertyValue $watchlistWorkbenchPayload "review_due_items" 0)
    reviewed_today_items = ConvertTo-SummaryInteger (Get-ObjectPropertyValue $watchlistWorkbenchPayload "reviewed_today_items" 0)
    signal_linked_items = ConvertTo-SummaryInteger (Get-ObjectPropertyValue $watchlistWorkbenchPayload "signal_linked_items" 0)
    root_level_items = ConvertTo-SummaryInteger (Get-ObjectPropertyValue $watchlistWorkbenchPayload "root_level_items" 0)
    watched_roots = $watchedRoots
    first_due_watch_key = $firstDueWatchKey
    first_due_root_code = $firstDueRootCode
    first_due_signal_id = $firstDueSignalId
    first_due_label = $firstDueLabel
    next_step = [string](Get-ObjectPropertyValue $watchlistWorkbenchPayload "next_step" "")
  }
}

$dailyWorkflowLines = @(
  "## Daily Workflow Evidence",
  "",
  "- Morning Brief signals-only: $($dailyWorkflowSummary.morning_brief.signals_only)",
  "- Morning Brief market status: $($dailyWorkflowSummary.morning_brief.market_status)",
  "- Morning Brief Telegram status: $($dailyWorkflowSummary.morning_brief.telegram_status)",
  "- Morning Brief top attention count: $($dailyWorkflowSummary.morning_brief.top_attention_count)",
  "- Morning Brief do-not-chase count: $($dailyWorkflowSummary.morning_brief.dont_chase_count)",
  "- Today's Operating Queue signals-only: $($dailyWorkflowSummary.todays_operating_queue.signals_only)",
  "- Today's Operating Queue total items: $($dailyWorkflowSummary.todays_operating_queue.total_items)",
  "- Today's Operating Queue review due: $($dailyWorkflowSummary.todays_operating_queue.review_due_items)",
  "- Today's Operating Queue reviewed today: $($dailyWorkflowSummary.todays_operating_queue.reviewed_today_items)",
  "- Today's Operating Queue watched roots: $(if ($watchedRoots.Count -gt 0) { $watchedRoots -join ', ' } else { 'none' })",
  "- Today's Operating Queue first due: $firstDueLabel",
  "- Today's Operating Queue next step: $($dailyWorkflowSummary.todays_operating_queue.next_step)"
)

$initialAcceptancePrefillLines = @(
  "",
  "## Candidate Output Prefill",
  "",
  "- Candidate revision: $candidateRevision",
  "- Candidate review status: pending_validation",
  "- Working tree state: $candidateWorktreeState",
  "- Dirty/untracked entry count: $candidateDirtyCount",
  "- Clean git required: $([bool]$RequireCleanGit)",
  "- Release notes mode: $releaseNotesMode",
  "- Release notes source: $releaseNotesSource",
  "- Skipped gates: $(if ($skippedGates.Count -gt 0) { $skippedGates -join ', ' } else { 'none' })",
  "- Browser-smoke command status: $browserSmokeCommandStatus",
  "- Browser-smoke command failure: $(if ([string]::IsNullOrWhiteSpace($browserSmokeCommandFailure)) { 'none' } else { $browserSmokeCommandFailure })",
  "- Browser-smoke recorded status: $(if ([string]::IsNullOrWhiteSpace($browserSmokeRecordedStatus)) { 'none' } else { $browserSmokeRecordedStatus })",
  "- Browser-smoke failure code: $(if ([string]::IsNullOrWhiteSpace($browserSmokeFailureCode)) { 'none' } else { $browserSmokeFailureCode })",
  "- Browser-smoke failure detail: $(if ([string]::IsNullOrWhiteSpace($browserSmokeFailureDetail)) { 'none' } else { $browserSmokeFailureDetail })",
  "- Browser-smoke completed/planned checks: $browserSmokeCompletedCheckCount/$browserSmokePlannedCheckCount",
  "- Validation status: pending",
  "- Validation warnings: pending",
  "- Validation failures: pending",
  "- Signals-only decision support: true",
  "- Release decision authorized: false",
  "- Production deployment authorized: false",
  "- Pricing commitment authorized: false",
  "- Order routing authorized: false",
  "- Autotrading authorized: false",
  "- Morning Brief evidence: signals_only=$($dailyWorkflowSummary.morning_brief.signals_only); market_status=$($dailyWorkflowSummary.morning_brief.market_status); telegram_status=$($dailyWorkflowSummary.morning_brief.telegram_status); top_attention=$($dailyWorkflowSummary.morning_brief.top_attention_count); dont_chase=$($dailyWorkflowSummary.morning_brief.dont_chase_count)",
  "- Today's Operating Queue evidence: signals_only=$($dailyWorkflowSummary.todays_operating_queue.signals_only); total=$($dailyWorkflowSummary.todays_operating_queue.total_items); review_due=$($dailyWorkflowSummary.todays_operating_queue.review_due_items); reviewed_today=$($dailyWorkflowSummary.todays_operating_queue.reviewed_today_items); watched_roots=$(if ($watchedRoots.Count -gt 0) { $watchedRoots -join ', ' } else { 'none' }); first_due=$firstDueLabel; next_step=$($dailyWorkflowSummary.todays_operating_queue.next_step)",
  "- Candidate summary Markdown: $summaryMarkdownPath",
  "- Candidate summary JSON: $summaryPath",
  "- Git status snapshot: $gitStatusPath",
  "- Evidence manifest: $(Join-Path $evidenceDir 'private-beta-evidence-manifest.json')",
  "- Evidence validation JSON: $evidenceValidationJson",
  "- Product-readiness JSON: $productReadinessJson",
  "- Admin-health JSON: $adminHealthJson",
  "- Workspace snapshot JSON: $workspaceSnapshotJson",
  "- Telegram preview JSON: $telegramPreviewJson",
  "- Telegram ops preview JSON: $telegramOpsPreviewJson",
  "- Release-check log: $releaseCheckLog",
  "- Browser-smoke JSON: $(if ($SkipBrowser) { 'skipped' } else { $browserSmokeJson })",
  "- Restore-drill summary: $(if ($SkipRestore) { 'skipped' } else { $restoreDrillSummary })",
  "- Performance baseline JSON: $(if ($SkipPerformance) { 'skipped' } else { $performanceBaselineJson })",
  "- Release notes draft: $releaseNotesDraft",
  "",
  "This prefill is generated by the local candidate wrapper. It does not authorize private beta, production deployment, pricing, broker execution, order routing, or autotrading."
)
Assert-TextContainsAll "candidate acceptance checklist prefill" ($initialAcceptancePrefillLines -join "`n") $acceptanceChecklistSafetyFlags
$initialAcceptancePrefillLines | Add-Content -Path $acceptanceChecklistDraft -Encoding UTF8

$initialSummaryMarkdown = @(
  "# Private-Beta Candidate Summary",
  "",
  "- Output directory: $OutputDir",
  "- Candidate revision: $candidateRevision",
  "- Candidate review status: pending_validation",
  "- Working tree state: $candidateWorktreeState",
  "- Dirty/untracked entry count: $candidateDirtyCount",
  "- Clean git required: $([bool]$RequireCleanGit)",
  "- Release notes mode: $releaseNotesMode",
  "- Release notes source: $releaseNotesSource",
  "- Git status snapshot: $gitStatusPath",
  "- Evidence validation JSON: $evidenceValidationJson",
  "",
  "## Safety Flags",
  "",
  "- Signals-only decision support: true",
  "- Release decision authorized by this wrapper: false",
  "- Production deployment authorized by this wrapper: false",
  "- Pricing commitment authorized by this wrapper: false",
  "- Order routing authorized by this wrapper: false",
  "- Autotrading authorized by this wrapper: false",
  "",
  "This initial summary is generated by the local candidate wrapper before evidence validation. It does not authorize production deployment, pricing, broker execution, order routing, autotrading, or private-beta launch."
)
Assert-TextContainsAll "initial candidate summary" ($initialSummaryMarkdown -join "`n") $candidateSummarySafetyFlags
$initialSummaryMarkdown | Set-Content -Path $summaryMarkdownPath -Encoding UTF8

$evidenceArgs = @(
  "-ExecutionPolicy", "Bypass",
  "-File", (Join-Path $repoRoot "scripts\private_beta_evidence_pack.ps1"),
  "-OutputDir", $evidenceDir,
  "-CandidateRevision", $candidateRevision,
  "-ReleaseCheckLog", $releaseCheckLog,
  "-ProductReadinessJson", $productReadinessJson,
  "-AdminHealthJson", $adminHealthJson,
  "-WorkspaceSnapshotJson", $workspaceSnapshotJson,
  "-TelegramPreviewJson", $telegramPreviewJson,
  "-TelegramOpsPreviewJson", $telegramOpsPreviewJson,
  "-AcceptanceChecklist", $acceptanceChecklistDraft,
  "-CandidateSummary", $summaryMarkdownPath,
  "-ReleaseNotes", $releaseNotesDraft,
  "-AnalyticsMode", $AnalyticsMode
)

if (-not $SkipBrowser) {
  $evidenceArgs += @("-BrowserSmokeJson", $browserSmokeJson)
}
if (-not $SkipPerformance) {
  $evidenceArgs += @("-PerformanceBaselineJson", $performanceBaselineJson)
}
if (-not $SkipRestore) {
  $evidenceArgs += @("-RestoreDrillSummary", $restoreDrillSummary)
}
if ($AllowDraftEvidence -or $SkipReleaseCheck -or $SkipBrowser -or $SkipPerformance -or $SkipRestore) {
  $evidenceArgs += "-AllowMissingArtifacts"
}

Write-Host "[private-beta-candidate] generating evidence manifest"
powershell @evidenceArgs
Assert-NativeSuccess "private-beta evidence manifest"

$validationArgs = @(
  "-ExecutionPolicy", "Bypass",
  "-File", (Join-Path $repoRoot "scripts\validate_private_beta_evidence.ps1"),
  "-ManifestPath", (Join-Path $evidenceDir "private-beta-evidence-manifest.json"),
  "-OutputPath", $evidenceValidationJson
)
$draftValidation = $AllowDraftEvidence -or $SkipReleaseCheck -or $SkipBrowser -or $SkipPerformance -or $SkipRestore -or $usesDraftReleaseNotes
if ($draftValidation) {
  $validationArgs += "-AllowDraft"
}

Write-Host "[private-beta-candidate] validating evidence manifest"
powershell @validationArgs
$validationExitCode = $LASTEXITCODE
if ($validationExitCode -ne 0) {
  $validationFailureForSummary = "private-beta evidence validation failed with exit code $validationExitCode"
  if (-not $AllowDraftEvidence -or -not (Test-Path -LiteralPath $evidenceValidationJson)) {
    throw $validationFailureForSummary
  }
  Write-Host "[private-beta-candidate] evidence validation failed; continuing to blocked draft summary: $validationFailureForSummary"
}

$validationPayload = Get-Content -Path $evidenceValidationJson -Raw | ConvertFrom-Json
$validationStatus = [string]$validationPayload.status
$validationWarnings = @()
if ($null -ne $validationPayload.warnings) {
  foreach ($warning in $validationPayload.warnings) {
    $validationWarnings += $warning
  }
}
$validationFailures = @()
if ($null -ne $validationPayload.failures) {
  foreach ($failure in $validationPayload.failures) {
    $validationFailures += $failure
  }
}

$dailyWorkflowValidationPayload = Get-ObjectPropertyValue $validationPayload "daily_workflow_evidence"
$morningBriefValidationPayload = Get-ObjectPropertyValue $dailyWorkflowValidationPayload "morning_brief"
$watchlistValidationPayload = Get-ObjectPropertyValue $dailyWorkflowValidationPayload "todays_operating_queue"
$dailyWorkflowValidation = [ordered]@{
  morning_brief = [ordered]@{
    present = [bool](Get-ObjectPropertyValue $morningBriefValidationPayload "present" $false)
    signals_only = [bool](Get-ObjectPropertyValue $morningBriefValidationPayload "signals_only" $false)
    execution_language_clear = [bool](Get-ObjectPropertyValue $morningBriefValidationPayload "execution_language_clear" $false)
  }
  todays_operating_queue = [ordered]@{
    present = [bool](Get-ObjectPropertyValue $watchlistValidationPayload "present" $false)
    signals_only = [bool](Get-ObjectPropertyValue $watchlistValidationPayload "signals_only" $false)
    watchlist_present = [bool](Get-ObjectPropertyValue $watchlistValidationPayload "watchlist_present" $false)
    total_matches_watchlist = [bool](Get-ObjectPropertyValue $watchlistValidationPayload "total_matches_watchlist" $false)
    state_counts_match_watchlist = [bool](Get-ObjectPropertyValue $watchlistValidationPayload "state_counts_match_watchlist" $false)
    counts_reconcile = [bool](Get-ObjectPropertyValue $watchlistValidationPayload "counts_reconcile" $false)
    first_due_matches_watchlist = [bool](Get-ObjectPropertyValue $watchlistValidationPayload "first_due_matches_watchlist" $false)
    next_step_matches_state = [bool](Get-ObjectPropertyValue $watchlistValidationPayload "next_step_matches_state" $false)
    execution_language_clear = [bool](Get-ObjectPropertyValue $watchlistValidationPayload "execution_language_clear" $false)
  }
}

$dailyWorkflowValidationLines = @(
  "## Daily Workflow Validation",
  "",
  "- Morning Brief present: $($dailyWorkflowValidation.morning_brief.present)",
  "- Morning Brief signals-only validated: $($dailyWorkflowValidation.morning_brief.signals_only)",
  "- Morning Brief execution language clear: $($dailyWorkflowValidation.morning_brief.execution_language_clear)",
  "- Today's Operating Queue present: $($dailyWorkflowValidation.todays_operating_queue.present)",
  "- Today's Operating Queue signals-only validated: $($dailyWorkflowValidation.todays_operating_queue.signals_only)",
  "- Today's Operating Queue archived watchlist present: $($dailyWorkflowValidation.todays_operating_queue.watchlist_present)",
  "- Today's Operating Queue total matches watchlist: $($dailyWorkflowValidation.todays_operating_queue.total_matches_watchlist)",
  "- Today's Operating Queue state counts match watchlist: $($dailyWorkflowValidation.todays_operating_queue.state_counts_match_watchlist)",
  "- Today's Operating Queue counts reconcile: $($dailyWorkflowValidation.todays_operating_queue.counts_reconcile)",
  "- Today's Operating Queue first due matches watchlist: $($dailyWorkflowValidation.todays_operating_queue.first_due_matches_watchlist)",
  "- Today's Operating Queue next step matches state: $($dailyWorkflowValidation.todays_operating_queue.next_step_matches_state)",
  "- Today's Operating Queue execution language clear: $($dailyWorkflowValidation.todays_operating_queue.execution_language_clear)"
)

$candidateReviewStatus = if ($validationFailures.Count -gt 0) {
  "blocked"
} elseif ($AllowDraftEvidence -or $skippedGates.Count -gt 0) {
  "draft_evidence_only"
} elseif ($usesDraftReleaseNotes) {
  "draft_evidence_only"
} elseif ($candidateWorktreeState -ne "clean") {
  "needs_clean_git_review"
} elseif ($validationWarnings.Count -gt 0) {
  "needs_warning_review"
} else {
  "operator_acceptance_ready"
}

$nextActions = @()
if ($candidateWorktreeState -ne "clean") {
  $nextActions += "Review git-status.txt and regenerate the final candidate from a clean tree, or document an accepted dirty-tree exception in release notes."
}
if ($skippedGates.Count -gt 0) {
  $nextActions += "Run the full candidate wrapper without skipped gates before final acceptance: powershell -ExecutionPolicy Bypass -File .\scripts\private_beta_candidate_check.ps1 -Root $Root -SkipDocker -RequireCleanGit"
}
if ($browserSmokeCommandStatus -eq "failed") {
  $nextActions += "Resolve the browser-smoke failure recorded in browser-smoke.log and browser-smoke.json, then rerun without -AllowDraftEvidence before final acceptance."
}
if ($usesDraftReleaseNotes) {
  $nextActions += "Replace release-notes-draft.md placeholders or rerun with -PreparedReleaseNotes <completed-release-notes.md> before final acceptance."
}
if ($validationWarnings.Count -gt 0) {
  $nextActions += "Review validation warnings and record any accepted warnings in release notes."
}
if ($validationFailures.Count -gt 0) {
  $nextActions += "Fix validation failures, regenerate the evidence pack, and rerun validation."
}
if ($nextActions.Count -eq 0) {
  $nextActions += "Complete the private-beta acceptance checklist and record the decision owner; this wrapper still does not authorize launch."
}
$nextActions += "Complete acceptance-checklist-draft.md in this candidate directory before any private-beta decision."

$summary = [ordered]@{
  output_dir = $OutputDir
  candidate_revision = $candidateRevision
  candidate_worktree_state = $candidateWorktreeState
  candidate_dirty_count = $candidateDirtyCount
  require_clean_git = [bool]$RequireCleanGit
  candidate_review_status = $candidateReviewStatus
  release_notes_mode = $releaseNotesMode
  release_notes_source = $releaseNotesSource
  skipped_gates = $skippedGates
  next_actions = $nextActions
  browser_smoke_command_status = $browserSmokeCommandStatus
  browser_smoke_command_failure = $browserSmokeCommandFailure
  browser_smoke_recorded_status = $browserSmokeRecordedStatus
  browser_smoke_failure_code = $browserSmokeFailureCode
  browser_smoke_failure_detail = $browserSmokeFailureDetail
  browser_smoke_completed_check_count = $browserSmokeCompletedCheckCount
  browser_smoke_planned_check_count = $browserSmokePlannedCheckCount
  daily_workflow_summary = $dailyWorkflowSummary
  daily_workflow_validation = $dailyWorkflowValidation
  git_status_path = $gitStatusPath
  release_check_log = $releaseCheckLog
  browser_smoke_json = if ($SkipBrowser) { "" } else { $browserSmokeJson }
  product_readiness_json = $productReadinessJson
  admin_health_json = $adminHealthJson
  workspace_snapshot_json = $workspaceSnapshotJson
  telegram_preview_json = $telegramPreviewJson
  telegram_ops_preview_json = $telegramOpsPreviewJson
  restore_drill_summary = if ($SkipRestore) { "" } else { $restoreDrillSummary }
  performance_baseline_json = if ($SkipPerformance) { "" } else { $performanceBaselineJson }
  release_notes_draft = $releaseNotesDraft
  acceptance_checklist_draft = $acceptanceChecklistDraft
  evidence_manifest = (Join-Path $evidenceDir "private-beta-evidence-manifest.json")
  evidence_validation = $evidenceValidationJson
  evidence_validation_status = $validationStatus
  evidence_validation_warnings = $validationWarnings
  evidence_validation_failures = $validationFailures
  signals_only_decision_support = $true
  release_decision_authorized = $false
  production_deployment_authorized = $false
  pricing_commitment_authorized = $false
  order_routing_authorized = $false
  autotrading_authorized = $false
}

$summary | ConvertTo-Json -Depth 5 | Set-Content -Path $summaryPath -Encoding UTF8

$acceptanceFinalStatusLines = @(
  "",
  "## Candidate Output Final Status",
  "",
  "- Candidate revision: $candidateRevision",
  "- Candidate review status: $candidateReviewStatus",
  "- Working tree state: $candidateWorktreeState",
  "- Dirty/untracked entry count: $candidateDirtyCount",
  "- Clean git required: $([bool]$RequireCleanGit)",
  "- Release notes mode: $releaseNotesMode",
  "- Release notes source: $releaseNotesSource",
  "- Skipped gates: $(if ($skippedGates.Count -gt 0) { $skippedGates -join ', ' } else { 'none' })",
  "- Browser-smoke command status: $browserSmokeCommandStatus",
  "- Browser-smoke command failure: $(if ([string]::IsNullOrWhiteSpace($browserSmokeCommandFailure)) { 'none' } else { $browserSmokeCommandFailure })",
  "- Browser-smoke recorded status: $(if ([string]::IsNullOrWhiteSpace($browserSmokeRecordedStatus)) { 'none' } else { $browserSmokeRecordedStatus })",
  "- Browser-smoke failure code: $(if ([string]::IsNullOrWhiteSpace($browserSmokeFailureCode)) { 'none' } else { $browserSmokeFailureCode })",
  "- Browser-smoke failure detail: $(if ([string]::IsNullOrWhiteSpace($browserSmokeFailureDetail)) { 'none' } else { $browserSmokeFailureDetail })",
  "- Browser-smoke completed/planned checks: $browserSmokeCompletedCheckCount/$browserSmokePlannedCheckCount",
  "- Validation status: $validationStatus",
  "- Validation warnings: $($validationWarnings.Count)",
  "- Validation failures: $($validationFailures.Count)",
  "- Morning Brief evidence: signals_only=$($dailyWorkflowSummary.morning_brief.signals_only); market_status=$($dailyWorkflowSummary.morning_brief.market_status); telegram_status=$($dailyWorkflowSummary.morning_brief.telegram_status); top_attention=$($dailyWorkflowSummary.morning_brief.top_attention_count); dont_chase=$($dailyWorkflowSummary.morning_brief.dont_chase_count)",
  "- Today's Operating Queue evidence: signals_only=$($dailyWorkflowSummary.todays_operating_queue.signals_only); total=$($dailyWorkflowSummary.todays_operating_queue.total_items); review_due=$($dailyWorkflowSummary.todays_operating_queue.review_due_items); reviewed_today=$($dailyWorkflowSummary.todays_operating_queue.reviewed_today_items); watched_roots=$(if ($watchedRoots.Count -gt 0) { $watchedRoots -join ', ' } else { 'none' }); first_due=$firstDueLabel; next_step=$($dailyWorkflowSummary.todays_operating_queue.next_step)",
  "- Candidate summary Markdown: $summaryMarkdownPath",
  "- Candidate summary JSON: $summaryPath",
  "- Git status snapshot: $gitStatusPath",
  "- Evidence manifest: $(Join-Path $evidenceDir 'private-beta-evidence-manifest.json')",
  "- Evidence validation JSON: $evidenceValidationJson",
  "- Product-readiness JSON: $productReadinessJson",
  "- Admin-health JSON: $adminHealthJson",
  "- Workspace snapshot JSON: $workspaceSnapshotJson",
  "- Telegram preview JSON: $telegramPreviewJson",
  "- Telegram ops preview JSON: $telegramOpsPreviewJson",
  "- Release-check log: $releaseCheckLog",
  "- Browser-smoke JSON: $(if ($SkipBrowser) { 'skipped' } else { $browserSmokeJson })",
  "- Restore-drill summary: $(if ($SkipRestore) { 'skipped' } else { $restoreDrillSummary })",
  "- Performance baseline JSON: $(if ($SkipPerformance) { 'skipped' } else { $performanceBaselineJson })",
  "- Release notes draft: $releaseNotesDraft",
  "",
  "This final status is generated by the local candidate wrapper. It does not authorize private beta, production deployment, pricing, broker execution, order routing, or autotrading."
)
$acceptanceFinalStatusLines | Add-Content -Path $acceptanceChecklistDraft -Encoding UTF8
$acceptanceChecklistEvidenceCopy = Join-Path $evidenceDir "acceptance_checklist-$(Split-Path -Leaf $acceptanceChecklistDraft)"
Assert-TextContainsAll "candidate acceptance checklist" (Get-Content -Path $acceptanceChecklistDraft -Raw) $acceptanceChecklistSafetyFlags
Copy-RequiredEvidenceArtifact "candidate acceptance checklist" $acceptanceChecklistDraft $acceptanceChecklistEvidenceCopy

$validationLines = @(
  "## Evidence Validation",
  "",
  "- Status: $validationStatus",
  "- Warnings: $($validationWarnings.Count)",
  "- Failures: $($validationFailures.Count)"
)
if ($validationWarnings.Count -gt 0) {
  $validationLines += ""
  $validationLines += "### Warnings"
  foreach ($warning in $validationWarnings) {
    $validationLines += "- $($warning.code): $($warning.message)"
  }
}
if ($validationFailures.Count -gt 0) {
  $validationLines += ""
  $validationLines += "### Failures"
  foreach ($failure in $validationFailures) {
    $validationLines += "- $($failure.code): $($failure.message)"
  }
}

$nextActionLines = @(
  "## Next Actions",
  "",
  "- Candidate review status: $candidateReviewStatus",
  "- Skipped gates: $(if ($skippedGates.Count -gt 0) { $skippedGates -join ', ' } else { 'none' })"
)
foreach ($action in $nextActions) {
  $nextActionLines += "- $action"
}

$summaryMarkdown = @(
  "# Private-Beta Candidate Summary",
  "",
  "- Output directory: $OutputDir",
  "- Candidate revision: $candidateRevision",
  "- Working tree state: $candidateWorktreeState",
  "- Dirty/untracked entry count: $candidateDirtyCount",
  "- Clean git required: $([bool]$RequireCleanGit)",
  "- Release notes mode: $releaseNotesMode",
  "- Release notes source: $releaseNotesSource",
  "- Git status snapshot: $gitStatusPath",
  "- Release-check log: $releaseCheckLog",
  "- Browser-smoke command status: $browserSmokeCommandStatus",
  "- Browser-smoke command failure: $(if ([string]::IsNullOrWhiteSpace($browserSmokeCommandFailure)) { 'none' } else { $browserSmokeCommandFailure })",
  "- Browser-smoke recorded status: $(if ([string]::IsNullOrWhiteSpace($browserSmokeRecordedStatus)) { 'none' } else { $browserSmokeRecordedStatus })",
  "- Browser-smoke failure code: $(if ([string]::IsNullOrWhiteSpace($browserSmokeFailureCode)) { 'none' } else { $browserSmokeFailureCode })",
  "- Browser-smoke failure detail: $(if ([string]::IsNullOrWhiteSpace($browserSmokeFailureDetail)) { 'none' } else { $browserSmokeFailureDetail })",
  "- Browser-smoke completed/planned checks: $browserSmokeCompletedCheckCount/$browserSmokePlannedCheckCount",
  "- Browser-smoke JSON: $(if ($SkipBrowser) { 'skipped' } else { $browserSmokeJson })",
  "- Product-readiness JSON: $productReadinessJson",
  "- Admin-health JSON: $adminHealthJson",
  "- Workspace snapshot JSON: $workspaceSnapshotJson",
  "- Telegram preview JSON: $telegramPreviewJson",
  "- Telegram ops preview JSON: $telegramOpsPreviewJson",
  "- Restore-drill summary: $(if ($SkipRestore) { 'skipped' } else { $restoreDrillSummary })",
  "- Performance baseline JSON: $(if ($SkipPerformance) { 'skipped' } else { $performanceBaselineJson })",
  "- Release notes draft: $releaseNotesDraft",
  "- Acceptance checklist draft: $acceptanceChecklistDraft",
  "- Evidence manifest: $(Join-Path $evidenceDir 'private-beta-evidence-manifest.json')",
  "- Evidence validation JSON: $evidenceValidationJson",
  ""
) + $dailyWorkflowLines + @(
  ""
) + $dailyWorkflowValidationLines + @(
  ""
) + $validationLines + @(
  ""
) + $nextActionLines + @(
  "",
  "## Safety Flags",
  "",
  "- Signals-only decision support: true",
  "- Release decision authorized by this wrapper: false",
  "- Production deployment authorized by this wrapper: false",
  "- Pricing commitment authorized by this wrapper: false",
  "- Order routing authorized by this wrapper: false",
  "- Autotrading authorized by this wrapper: false",
  "",
  "This summary is an operator-readable index only. It does not authorize production deployment, pricing, broker execution, order routing, autotrading, or private-beta launch."
)
Assert-TextContainsAll "final candidate summary" ($summaryMarkdown -join "`n") $candidateSummarySafetyFlags
$summaryMarkdown | Set-Content -Path $summaryMarkdownPath -Encoding UTF8
$candidateSummaryEvidenceCopy = Join-Path $evidenceDir "candidate_summary-$(Split-Path -Leaf $summaryMarkdownPath)"
Copy-RequiredEvidenceArtifact "candidate summary" $summaryMarkdownPath $candidateSummaryEvidenceCopy

Write-Host "[private-beta-candidate] summary: $summaryPath"
Write-Host "[private-beta-candidate] summary markdown: $summaryMarkdownPath"
Write-Host "[private-beta-candidate] OK"
