param(
  [string]$OutputDir = "",
  [string]$CandidateRevision = "",
  [string]$ReleaseCheckLog = "",
  [string]$BrowserSmokeJson = "",
  [string]$ProductReadinessJson = "",
  [string]$AdminHealthJson = "",
  [string]$WorkspaceSnapshotJson = "",
  [string]$TelegramPreviewJson = "",
  [string]$TelegramOpsPreviewJson = "",
  [string]$RestoreDrillSummary = "",
  [string]$PerformanceBaselineJson = "",
  [string]$AcceptanceChecklist = "",
  [string]$CandidateSummary = "",
  [string]$ReleaseNotes = "",
  [ValidateSet("disabled", "local-only-export", "approved-opt-in-telemetry")]
  [string]$AnalyticsMode = "disabled",
  [switch]$AllowMissingArtifacts
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $PSScriptRoot
$runId = Get-Date -Format "yyyyMMddHHmmss"
if ([string]::IsNullOrWhiteSpace($OutputDir)) {
  $OutputDir = Join-Path $env:TEMP "imoex-private-beta-evidence\evidence-$runId"
}

New-Item -ItemType Directory -Force -Path $OutputDir | Out-Null

if ([string]::IsNullOrWhiteSpace($CandidateRevision)) {
  $CandidateRevision = (& git -C $repoRoot rev-parse --short HEAD 2>$null)
  if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($CandidateRevision)) {
    $CandidateRevision = "unknown"
  }
}

if ([string]::IsNullOrWhiteSpace($AcceptanceChecklist)) {
  $AcceptanceChecklist = "docs\private_beta_acceptance_checklist.md"
}

function Resolve-EvidencePath {
  param([string]$Path)

  if ([string]::IsNullOrWhiteSpace($Path)) {
    return ""
  }
  if ([System.IO.Path]::IsPathRooted($Path)) {
    return $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Path)
  }
  return $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath((Join-Path $repoRoot $Path))
}

function New-EvidenceItem {
  param(
    [string]$Key,
    [string]$Label,
    [string]$Path,
    [string]$RequiredEvidence
  )

  $resolved = Resolve-EvidencePath $Path
  $present = -not [string]::IsNullOrWhiteSpace($resolved) -and (Test-Path -LiteralPath $resolved)
  $copiedTo = ""
  if ($present) {
    $copyName = "$Key-$((Split-Path -Leaf $resolved))"
    $copiedTo = Join-Path $OutputDir $copyName
    Copy-Item -LiteralPath $resolved -Destination $copiedTo -Force
  }

  return [ordered]@{
    key = $Key
    label = $Label
    path = $resolved
    present = $present
    copied_to = $copiedTo
    required_evidence = $RequiredEvidence
  }
}

$artifacts = @(
  New-EvidenceItem "release_check" "release_check.ps1 output" $ReleaseCheckLog "Log includes product readiness OK and final OK."
  New-EvidenceItem "browser_smoke" "Browser smoke JSON" $BrowserSmokeJson "JSON covers workspace, runtime prompt governance, root switch, charts, mobile, and no horizontal overflow."
  New-EvidenceItem "product_readiness" "Product-readiness JSON" $ProductReadinessJson "JSON includes backup, restore, scheduler, delivery, migration, market-data policy, and admin/runtime security checks."
  New-EvidenceItem "admin_health" "Admin health JSON" $AdminHealthJson "JSON confirms admin health is ok or intentionally degraded with roots visible."
  New-EvidenceItem "workspace_snapshot" "Workspace snapshot JSON" $WorkspaceSnapshotJson "JSON includes the Morning Command Brief, Today's Operating Queue, and Readiness Next Steps API contracts with signals-only and truthful market-data state."
  New-EvidenceItem "telegram_preview" "Telegram preview JSON" $TelegramPreviewJson "JSON confirms preview/dry-run readiness without authorizing unintended sends."
  New-EvidenceItem "telegram_ops_preview" "Telegram ops preview JSON" $TelegramOpsPreviewJson "JSON confirms ops alert preview readiness without authorizing alert sends."
  New-EvidenceItem "restore_drill" "Restore-drill summary" $RestoreDrillSummary "Summary matches the target database class and reports release_gate=pass."
  New-EvidenceItem "performance_baseline" "Performance baseline JSON" $PerformanceBaselineJson "JSON covers dashboard, workspace, signal detail, runtime, council, journal, and product-readiness surfaces."
  New-EvidenceItem "alerting_expectations" "External alerting map" "docs\alerting_expectations.md" "Destinations are mapped or explicitly deferred for non-production only."
  New-EvidenceItem "analytics_catalog" "Product analytics mode/catalog" "docs\product_analytics_events.md" "Analytics mode is disabled, local-only export, or explicitly approved opt-in telemetry."
  New-EvidenceItem "sales_readiness" "Private-beta sales-readiness pack" "docs\private_beta_sales_readiness.md" "Positioning, demo path, support boundaries, and onboarding checklist are available."
  New-EvidenceItem "acceptance_checklist" "Private-beta acceptance checklist" $AcceptanceChecklist "Checklist records accepted warnings, rollback owner, and signals-only confirmation."
  New-EvidenceItem "release_notes_template" "Private-beta release notes template" "docs\private_beta_release_notes_template.md" "Template captures evidence links, accepted warnings, non-goals, support boundaries, rollback, and decision."
  New-EvidenceItem "release_notes" "Release notes" $ReleaseNotes "Notes list accepted warnings and explicit non-goals."
)

if (-not [string]::IsNullOrWhiteSpace($CandidateSummary)) {
  $artifacts += New-EvidenceItem "candidate_summary" "Operator-readable candidate summary" $CandidateSummary "Summary includes validation status, next actions, and explicit signals-only/no-execution safety flags."
}

$missingRequired = @($artifacts | Where-Object { -not $_.present })
$manifestPath = Join-Path $OutputDir "private-beta-evidence-manifest.json"
$summaryPath = Join-Path $OutputDir "private-beta-evidence-summary.md"

$manifest = [ordered]@{
  generated_at = (Get-Date).ToUniversalTime().ToString("o")
  candidate_revision = $CandidateRevision.Trim()
  analytics_mode = $AnalyticsMode
  signals_only_decision_support = $true
  release_decision_authorized = $false
  production_deployment_authorized = $false
  pricing_commitment_authorized = $false
  order_routing_authorized = $false
  autotrading_authorized = $false
  missing_required_artifacts = @($missingRequired | ForEach-Object { $_.key })
  artifacts = $artifacts
}

$manifest | ConvertTo-Json -Depth 8 | Set-Content -Path $manifestPath -Encoding UTF8

$lines = @(
  "# Private-Beta Evidence Summary",
  "",
  "- Candidate revision: $($manifest.candidate_revision)",
  "- Analytics mode: $AnalyticsMode",
  "- Signals-only decision support: true",
  "- Release decision authorized by this script: false",
  "- Production deployment authorized by this script: false",
  "- Pricing commitment authorized by this script: false",
  "- Order routing authorized by this script: false",
  "- Autotrading authorized by this script: false",
  "",
  "## Artifacts"
)

foreach ($artifact in $artifacts) {
  $status = if ($artifact.present) { "present" } else { "missing" }
  $lines += "- $($artifact.key): $status - $($artifact.label)"
}

if ($missingRequired.Count -gt 0) {
  $lines += ""
  $lines += "## Missing Required Artifacts"
  foreach ($artifact in $missingRequired) {
    $lines += "- $($artifact.key): $($artifact.required_evidence)"
  }
}

$lines | Set-Content -Path $summaryPath -Encoding UTF8

Write-Host "[private-beta-evidence] output: $OutputDir"
Write-Host "[private-beta-evidence] manifest: $manifestPath"
Write-Host "[private-beta-evidence] summary: $summaryPath"

if ($missingRequired.Count -gt 0 -and -not $AllowMissingArtifacts) {
  $missingKeys = ($missingRequired | ForEach-Object { $_.key }) -join ", "
  throw "Private-beta evidence pack is incomplete: $missingKeys. Re-run with -AllowMissingArtifacts to create a draft manifest."
}

Write-Host "[private-beta-evidence] OK"
