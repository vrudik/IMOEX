param(
  [Parameter(Mandatory = $true)]
  [string]$ManifestPath,
  [string]$OutputPath = "",
  [switch]$AllowDraft
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $PSScriptRoot

function Resolve-RepoPath {
  param([string]$Path)

  if ([string]::IsNullOrWhiteSpace($Path)) {
    return ""
  }
  if ([System.IO.Path]::IsPathRooted($Path)) {
    return $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($Path)
  }
  return $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath((Join-Path $repoRoot $Path))
}

$manifestPathResolved = Resolve-RepoPath $ManifestPath
if (-not (Test-Path -LiteralPath $manifestPathResolved)) {
  throw "Private-beta evidence manifest was not found: $manifestPathResolved"
}

if ([string]::IsNullOrWhiteSpace($OutputPath)) {
  $OutputPath = Join-Path (Split-Path -Parent $manifestPathResolved) "private-beta-evidence-validation.json"
}

$manifest = Get-Content -Path $manifestPathResolved -Raw | ConvertFrom-Json
$failures = New-Object System.Collections.Generic.List[object]
$warnings = New-Object System.Collections.Generic.List[object]

function Add-Failure {
  param(
    [string]$Code,
    [string]$Message
  )

  $failures.Add([ordered]@{ code = $Code; message = $Message }) | Out-Null
}

function Add-Warning {
  param(
    [string]$Code,
    [string]$Message
  )

  $warnings.Add([ordered]@{ code = $Code; message = $Message }) | Out-Null
}

function Test-ManifestFlag {
  param(
    [string]$Name,
    [bool]$Expected
  )

  $property = $manifest.PSObject.Properties[$Name]
  if ($null -eq $property) {
    Add-Failure "missing_flag" "Manifest is missing '$Name'."
    return
  }

  if ([bool]$property.Value -ne $Expected) {
    Add-Failure "invalid_flag" "Manifest flag '$Name' must be '$Expected'."
  }
}

$artifacts = @($manifest.artifacts)

function Get-Artifact {
  param([string]$Key)

  $matches = @($artifacts | Where-Object { [string]$_.key -eq $Key })
  if ($matches.Count -eq 0) {
    return $null
  }
  return $matches[0]
}

function Get-ArtifactPath {
  param([string]$Key)

  $artifact = Get-Artifact $Key
  if ($null -eq $artifact -or -not [bool]$artifact.present) {
    return ""
  }

  $copiedTo = [string]$artifact.copied_to
  if (-not [string]::IsNullOrWhiteSpace($copiedTo) -and (Test-Path -LiteralPath $copiedTo)) {
    return $copiedTo
  }

  $originalPath = [string]$artifact.path
  if (-not [string]::IsNullOrWhiteSpace($originalPath) -and (Test-Path -LiteralPath $originalPath)) {
    return $originalPath
  }

  return ""
}

$allowedAnalyticsModes = @("disabled", "local-only-export", "approved-opt-in-telemetry")
$requiredArtifactKeys = @(
  "release_check",
  "browser_smoke",
  "product_readiness",
  "admin_health",
  "restore_drill",
  "performance_baseline",
  "alerting_expectations",
  "analytics_catalog",
  "sales_readiness",
  "acceptance_checklist",
  "release_notes_template",
  "release_notes"
)

Test-ManifestFlag "signals_only_decision_support" $true
Test-ManifestFlag "release_decision_authorized" $false
Test-ManifestFlag "production_deployment_authorized" $false
Test-ManifestFlag "pricing_commitment_authorized" $false
Test-ManifestFlag "order_routing_authorized" $false

if ($allowedAnalyticsModes -notcontains [string]$manifest.analytics_mode) {
  Add-Failure "invalid_analytics_mode" "Analytics mode must be one of: $($allowedAnalyticsModes -join ', ')."
}

$candidateRevision = ([string]$manifest.candidate_revision).Trim()
if ([string]::IsNullOrWhiteSpace($candidateRevision) -or $candidateRevision -eq "unknown") {
  if ($AllowDraft) {
    Add-Warning "draft_candidate_revision_unknown" "Draft evidence does not include a known candidate git revision."
  } else {
    Add-Failure "candidate_revision_unknown" "Full private-beta evidence must include a known candidate git revision."
  }
}

$artifactKeys = @($artifacts | ForEach-Object { [string]$_.key })
foreach ($key in $requiredArtifactKeys) {
  if ($artifactKeys -notcontains $key) {
    Add-Failure "missing_artifact_key" "Manifest is missing required artifact key '$key'."
  }
}

$missingArtifacts = @($manifest.missing_required_artifacts | ForEach-Object { [string]$_ })
if ($missingArtifacts.Count -gt 0) {
  if ($AllowDraft) {
    Add-Warning "draft_missing_artifacts" "Draft evidence is missing: $($missingArtifacts -join ', ')."
  } else {
    Add-Failure "missing_required_artifacts" "Evidence is missing required artifacts: $($missingArtifacts -join ', ')."
  }
}

foreach ($artifact in $artifacts) {
  $key = [string]$artifact.key
  if ([bool]$artifact.present) {
    $path = Get-ArtifactPath $key
    if ([string]::IsNullOrWhiteSpace($path)) {
      Add-Failure "missing_present_artifact_file" "Artifact '$key' is marked present but no copied or source file exists."
    }
  }
}

$releaseCheckPath = Get-ArtifactPath "release_check"
if (-not [string]::IsNullOrWhiteSpace($releaseCheckPath)) {
  $releaseCheckText = Get-Content -Path $releaseCheckPath -Raw
  if (-not $AllowDraft -and ($releaseCheckText -notmatch "product readiness OK" -or $releaseCheckText -notmatch "\[release-check\] OK")) {
    Add-Failure "release_check_not_green" "Release-check log must include product readiness OK and [release-check] OK."
  }
}

$productReadinessPath = Get-ArtifactPath "product_readiness"
if (-not [string]::IsNullOrWhiteSpace($productReadinessPath)) {
  $productReadiness = Get-Content -Path $productReadinessPath -Raw | ConvertFrom-Json
  if ([string]$productReadiness.release_gate -ne "pass") {
    Add-Failure "product_readiness_not_pass" "Product-readiness JSON must report release_gate=pass."
  }
}

$adminHealthPath = Get-ArtifactPath "admin_health"
if (-not [string]::IsNullOrWhiteSpace($adminHealthPath)) {
  $adminHealth = Get-Content -Path $adminHealthPath -Raw | ConvertFrom-Json
  if (@("ok", "degraded") -notcontains [string]$adminHealth.status) {
    Add-Failure "admin_health_invalid_status" "Admin-health JSON must report status ok or degraded."
  }
}

$browserSmokePath = Get-ArtifactPath "browser_smoke"
if (-not [string]::IsNullOrWhiteSpace($browserSmokePath)) {
  $browserSmoke = Get-Content -Path $browserSmokePath -Raw | ConvertFrom-Json
  $browserChecks = @($browserSmoke.checks | ForEach-Object { [string]$_ })
  $requiredBrowserChecks = @(
    "workspace_opened",
    "runtime_admin_key_save_clear",
    "runtime_prompt_diff",
    "runtime_prompt_draft_saved",
    "runtime_prompt_draft_dismissed",
    "workspace_root_switch",
    "market_fixture_current_price_visible",
    "market_fixture_day_week_month_charts_visible",
    "market_fixture_chart_measurement",
    "market_fixture_multi_root_switch",
    "market_fixture_mobile_charts_visible",
    "market_fixture_mobile_no_horizontal_overflow"
  )
  foreach ($check in $requiredBrowserChecks) {
    if ($browserChecks -notcontains $check) {
      Add-Failure "browser_smoke_missing_check" "Browser-smoke JSON must include check '$check'."
    }
  }
}

$restoreDrillPath = Get-ArtifactPath "restore_drill"
if (-not [string]::IsNullOrWhiteSpace($restoreDrillPath)) {
  $restoreDrill = Get-Content -Path $restoreDrillPath -Raw | ConvertFrom-Json
  if ([string]$restoreDrill.release_gate -ne "pass") {
    Add-Failure "restore_drill_not_pass" "Restore-drill summary must report release_gate=pass."
  }
  if ([string]$restoreDrill.integrity_check -ne "ok") {
    Add-Failure "restore_drill_integrity_not_ok" "Restore-drill summary must report integrity_check=ok."
  }
  if ([int]$restoreDrill.roots -le 0) {
    Add-Failure "restore_drill_missing_roots" "Restore-drill summary must report roots > 0."
  }
  if ([int]$restoreDrill.final_signals -le 0) {
    Add-Failure "restore_drill_missing_signals" "Restore-drill summary must report final_signals > 0."
  }
}

$performanceBaselinePath = Get-ArtifactPath "performance_baseline"
if (-not [string]::IsNullOrWhiteSpace($performanceBaselinePath)) {
  $performanceBaseline = Get-Content -Path $performanceBaselinePath -Raw | ConvertFrom-Json
  $performanceLabels = @($performanceBaseline.results | ForEach-Object { [string]$_.label })
  $requiredPerformanceLabels = @(
    "api_dashboard",
    "api_workspace",
    "page_workspace",
    "api_signal_detail",
    "page_signal_detail",
    "page_runtime",
    "page_council",
    "api_journal",
    "page_journal",
    "api_product_readiness"
  )
  foreach ($label in $requiredPerformanceLabels) {
    if ($performanceLabels -notcontains $label) {
      Add-Failure "performance_baseline_missing_label" "Performance baseline JSON must include label '$label'."
    }
  }
}

$acceptanceChecklistPath = Get-ArtifactPath "acceptance_checklist"
if (-not [string]::IsNullOrWhiteSpace($acceptanceChecklistPath)) {
  $acceptanceChecklist = Get-Content -Path $acceptanceChecklistPath -Raw
  if ($acceptanceChecklist -notmatch "(?m)^## Candidate Output Prefill\s*$") {
    if ($AllowDraft) {
      Add-Warning "draft_acceptance_checklist_prefill_missing" "Draft acceptance checklist does not include a Candidate Output Prefill section."
    } else {
      Add-Failure "acceptance_checklist_prefill_missing" "Full private-beta evidence must include a candidate-local acceptance checklist with Candidate Output Prefill."
    }
  }
  if ($acceptanceChecklist -notmatch "does not authorize private beta") {
    if ($AllowDraft) {
      Add-Warning "draft_acceptance_checklist_safety_phrase_missing" "Draft acceptance checklist does not include the no-authorization safety phrase."
    } else {
      Add-Failure "acceptance_checklist_safety_phrase_missing" "Candidate-local acceptance checklist must confirm it does not authorize private beta."
    }
  }
}

$releaseNotesPath = Get-ArtifactPath "release_notes"
if (-not [string]::IsNullOrWhiteSpace($releaseNotesPath)) {
  $releaseNotes = Get-Content -Path $releaseNotesPath -Raw
  foreach ($requiredPhrase in @("Explicit Non-Goals", "Support Boundary Confirmation", "Rollback Record", "signals-only decision support", "does not authorize production deployment")) {
    if ($releaseNotes -notmatch [regex]::Escape($requiredPhrase)) {
      Add-Failure "release_notes_missing_safety_phrase" "Release notes must include '$requiredPhrase'."
    }
  }
  $unresolvedPlaceholders = @(
    [regex]::Matches($releaseNotes, "<[^>`r`n]+>") |
      ForEach-Object { [string]$_.Value } |
      Select-Object -Unique
  )
  if ($unresolvedPlaceholders.Count -gt 0) {
    $placeholderSample = ($unresolvedPlaceholders | Select-Object -First 5) -join ", "
    if ($AllowDraft) {
      Add-Warning "draft_release_notes_placeholders_present" "Draft release notes still contain unresolved placeholders: $placeholderSample."
    } else {
      Add-Failure "release_notes_placeholders_present" "Full private-beta release notes must replace unresolved placeholders before acceptance: $placeholderSample."
    }
  }
  $releaseNotesCandidateMatch = [regex]::Match($releaseNotes, "(?m)^\s*Candidate:\s*(?<candidate>.+?)\s*$")
  $releaseNotesCandidate = if ($releaseNotesCandidateMatch.Success) { $releaseNotesCandidateMatch.Groups["candidate"].Value.Trim() } else { "" }
  if ([string]::IsNullOrWhiteSpace($releaseNotesCandidate)) {
    if ($AllowDraft) {
      Add-Warning "draft_release_notes_candidate_revision_missing" "Draft release notes do not record the candidate revision from the evidence manifest."
    } else {
      Add-Failure "release_notes_candidate_revision_missing" "Full private-beta release notes must record the candidate revision from the evidence manifest."
    }
  } elseif (-not [string]::IsNullOrWhiteSpace($candidateRevision) -and $candidateRevision -ne "unknown" -and $releaseNotesCandidate.IndexOf($candidateRevision, [StringComparison]::OrdinalIgnoreCase) -lt 0) {
    if ($AllowDraft) {
      Add-Warning "draft_release_notes_candidate_revision_mismatch" "Draft release notes candidate '$releaseNotesCandidate' does not include manifest revision '$candidateRevision'."
    } else {
      Add-Failure "release_notes_candidate_revision_mismatch" "Full private-beta release notes candidate '$releaseNotesCandidate' must include manifest revision '$candidateRevision'."
    }
  }
  $releaseNotesAnalyticsModeMatch = [regex]::Match($releaseNotes, "(?m)^\s*-\s*Analytics mode:\s*(?<mode>.+?)\s*$")
  $releaseNotesAnalyticsMode = if ($releaseNotesAnalyticsModeMatch.Success) { $releaseNotesAnalyticsModeMatch.Groups["mode"].Value.Trim() } else { "" }
  if ($allowedAnalyticsModes -notcontains $releaseNotesAnalyticsMode) {
    if ($AllowDraft) {
      Add-Warning "draft_release_notes_analytics_mode_invalid" "Draft release notes must record analytics mode as disabled, local-only-export, or approved-opt-in-telemetry."
    } else {
      Add-Failure "release_notes_analytics_mode_invalid" "Full private-beta release notes must record analytics mode as disabled, local-only-export, or approved-opt-in-telemetry."
    }
  } elseif ($releaseNotesAnalyticsMode -ne [string]$manifest.analytics_mode) {
    if ($AllowDraft) {
      Add-Warning "draft_release_notes_analytics_mode_mismatch" "Draft release notes analytics mode '$releaseNotesAnalyticsMode' does not match manifest analytics_mode '$($manifest.analytics_mode)'."
    } else {
      Add-Failure "release_notes_analytics_mode_mismatch" "Full private-beta release notes analytics mode '$releaseNotesAnalyticsMode' must match manifest analytics_mode '$($manifest.analytics_mode)'."
    }
  }
  $releaseNotesTelegramModeMatch = [regex]::Match($releaseNotes, "(?m)^\s*-\s*Telegram mode:\s*(?<mode>.+?)\s*$")
  $allowedReleaseNoteTelegramModes = @("disabled", "preview", "dry-run", "configured")
  $telegramMode = if ($releaseNotesTelegramModeMatch.Success) { $releaseNotesTelegramModeMatch.Groups["mode"].Value.Trim() } else { "" }
  if ($allowedReleaseNoteTelegramModes -notcontains $telegramMode) {
    if ($AllowDraft) {
      Add-Warning "draft_release_notes_telegram_mode_invalid" "Draft release notes must record Telegram mode as disabled, preview, dry-run, or configured."
    } else {
      Add-Failure "release_notes_telegram_mode_invalid" "Full private-beta release notes must record Telegram mode as disabled, preview, dry-run, or configured."
    }
  }
  $acceptedWarningsMatch = [regex]::Match($releaseNotes, "(?ms)^## Accepted Warnings\s*(?<body>.*?)(?:\r?\n## |\z)")
  $acceptedWarningsBody = if ($acceptedWarningsMatch.Success) { $acceptedWarningsMatch.Groups["body"].Value } else { "" }
  $acceptedWarningBullets = @(
    [regex]::Matches($acceptedWarningsBody, "(?m)^\s*-\s*(?<item>.+?)\s*$") |
      ForEach-Object { $_.Groups["item"].Value.Trim() } |
      Where-Object { -not [string]::IsNullOrWhiteSpace($_) }
  )
  $hasAcceptedWarningsDecision = $acceptedWarningBullets.Count -gt 0
  $invalidAcceptedWarningDetails = New-Object System.Collections.Generic.List[string]
  if ($hasAcceptedWarningsDecision) {
    $hasAcceptedWarningsDecision = $false
    foreach ($acceptedWarning in $acceptedWarningBullets) {
      if ($acceptedWarning -ieq "None") {
        $hasAcceptedWarningsDecision = $true
        break
      }
      $acceptedWarningParts = @($acceptedWarning -split "," | ForEach-Object { $_.Trim() } | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
      $acceptedWarningHasConcreteParts = $acceptedWarning -notmatch "<[^>`r`n]+>" -and $acceptedWarning -notmatch "^(?i:tbd|todo|unknown|n/a|na)$" -and $acceptedWarningParts.Count -ge 3
      if ($acceptedWarningHasConcreteParts) {
        $hasAcceptedWarningsDecision = $true
      } else {
        $invalidAcceptedWarningDetails.Add($acceptedWarning) | Out-Null
      }
    }
  }
  if (-not $hasAcceptedWarningsDecision) {
    if ($AllowDraft) {
      Add-Warning "draft_release_notes_accepted_warnings_missing" "Draft release notes do not record accepted warnings as None or concrete entries."
    } else {
      Add-Failure "release_notes_accepted_warnings_missing" "Full private-beta release notes must record accepted warnings as None or concrete entries."
    }
  } elseif ($invalidAcceptedWarningDetails.Count -gt 0) {
    $invalidWarningSample = ($invalidAcceptedWarningDetails | Select-Object -First 3) -join "; "
    if ($AllowDraft) {
      Add-Warning "draft_release_notes_accepted_warning_detail_incomplete" "Draft accepted-warning entries need warning, owner, and expiry or follow-up: $invalidWarningSample."
    } else {
      Add-Failure "release_notes_accepted_warning_detail_incomplete" "Accepted-warning entries must include warning, owner, and expiry or follow-up: $invalidWarningSample."
    }
  }
  $marketDataModeMatch = [regex]::Match($releaseNotes, "(?m)^\s*-\s*Market-data mode:\s*(?<mode>.+?)\s*$")
  $allowedReleaseNoteMarketDataModes = @("live", "hidden", "degraded", "fixture for browser smoke only")
  $marketDataMode = if ($marketDataModeMatch.Success) { $marketDataModeMatch.Groups["mode"].Value.Trim() } else { "" }
  if ($allowedReleaseNoteMarketDataModes -notcontains $marketDataMode) {
    if ($AllowDraft) {
      Add-Warning "draft_release_notes_market_data_mode_invalid" "Draft release notes must record market-data mode as live, hidden, degraded, or fixture for browser smoke only."
    } else {
      Add-Failure "release_notes_market_data_mode_invalid" "Full private-beta release notes must record market-data mode as live, hidden, degraded, or fixture for browser smoke only."
    }
  }
  $requiredSupportConfirmations = @(
    "Candidate understands this is decision support only",
    "Candidate accepts support boundaries before walkthrough",
    "Candidate understands market-data truthfulness policy",
    "Candidate understands secrets must not be pasted into screenshots, logs, or issue comments"
  )
  foreach ($confirmation in $requiredSupportConfirmations) {
    $confirmationPattern = "(?m)^\s*-\s*$([regex]::Escape($confirmation)):\s*yes\s*$"
    if ($releaseNotes -notmatch $confirmationPattern) {
      if ($AllowDraft) {
        Add-Warning "draft_release_notes_support_boundary_unconfirmed" "Draft release notes do not confirm support boundary item as yes: $confirmation."
      } else {
        Add-Failure "release_notes_support_boundary_unconfirmed" "Full private-beta release notes must confirm support boundary item as yes: $confirmation."
      }
    }
  }
  $requiredWalkthroughChecks = @(
    "Workspace trust ribbon checked",
    "Current price and day/week/month charts checked",
    "Root switch checked",
    "Signal detail checked",
    "Council prompts checked",
    "Runtime prompt diff/dismiss/restore checked",
    "Journal tags and filters checked",
    "Delivery reason trails checked",
    "Telegram preview/dry-run checked",
    "Backup/restore evidence checked"
  )
  foreach ($walkthroughCheck in $requiredWalkthroughChecks) {
    $walkthroughPattern = "(?m)^\s*-\s*$([regex]::Escape($walkthroughCheck)):\s*pass\s*$"
    if ($releaseNotes -notmatch $walkthroughPattern) {
      if ($AllowDraft) {
        Add-Warning "draft_release_notes_walkthrough_check_not_pass" "Draft release notes do not mark walkthrough check as pass: $walkthroughCheck."
      } else {
        Add-Failure "release_notes_walkthrough_check_not_pass" "Full private-beta release notes must mark walkthrough check as pass: $walkthroughCheck."
      }
    }
  }
  $decisionAcceptedMatch = [regex]::Match($releaseNotes, "(?m)^\s*-\s*Private-beta candidate accepted:\s*(yes|no|deferred)\s*$", [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
  if (-not $decisionAcceptedMatch.Success) {
    if ($AllowDraft) {
      Add-Warning "draft_release_notes_decision_status_missing" "Draft release notes do not record Private-beta candidate accepted as yes, no, or deferred."
    } else {
      Add-Failure "release_notes_decision_status_missing" "Full private-beta release notes must record Private-beta candidate accepted as yes, no, or deferred."
    }
  } elseif ($AllowDraft -and [string]$decisionAcceptedMatch.Groups[1].Value -ieq "yes") {
    Add-Failure "draft_release_notes_accepts_candidate" "Draft evidence cannot record Private-beta candidate accepted as yes; complete final evidence without -AllowDraft first."
  }
  $decisionOwnerMatch = [regex]::Match($releaseNotes, "(?m)^\s*-\s*Decision owner:\s*(?<owner>.+?)\s*$")
  $invalidDecisionOwner = -not $decisionOwnerMatch.Success
  if (-not $invalidDecisionOwner) {
    $decisionOwner = $decisionOwnerMatch.Groups["owner"].Value.Trim()
    $invalidDecisionOwner = [string]::IsNullOrWhiteSpace($decisionOwner) -or $decisionOwner -match "^(?i:tbd|todo|unknown|none|n/a|na)$"
  }
  if ($invalidDecisionOwner) {
    if ($AllowDraft) {
      Add-Warning "draft_release_notes_decision_owner_missing" "Draft release notes do not record a concrete decision owner."
    } else {
      Add-Failure "release_notes_decision_owner_missing" "Full private-beta release notes must record a concrete decision owner."
    }
  }
  $decisionTimestampMatch = [regex]::Match($releaseNotes, "(?m)^\s*-\s*Decision timestamp:\s*(?<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)\s*$")
  if (-not $decisionTimestampMatch.Success) {
    if ($AllowDraft) {
      Add-Warning "draft_release_notes_decision_timestamp_missing" "Draft release notes do not record an ISO-8601 UTC decision timestamp."
    } else {
      Add-Failure "release_notes_decision_timestamp_missing" "Full private-beta release notes must record an ISO-8601 UTC decision timestamp."
    }
  }
  $rollbackFields = @(
    [ordered]@{
      label = "Rollback owner"
      failure_code = "release_notes_rollback_owner_missing"
      draft_code = "draft_release_notes_rollback_owner_missing"
      message = "rollback owner"
    },
    [ordered]@{
      label = "Previous application revision"
      failure_code = "release_notes_rollback_revision_missing"
      draft_code = "draft_release_notes_rollback_revision_missing"
      message = "previous application revision"
    },
    [ordered]@{
      label = "Backup or restore artifact"
      failure_code = "release_notes_rollback_artifact_missing"
      draft_code = "draft_release_notes_rollback_artifact_missing"
      message = "backup or restore artifact"
    },
    [ordered]@{
      label = "Stop command or process owner"
      failure_code = "release_notes_rollback_stop_owner_missing"
      draft_code = "draft_release_notes_rollback_stop_owner_missing"
      message = "stop command or process owner"
    }
  )
  foreach ($field in $rollbackFields) {
    $fieldMatch = [regex]::Match($releaseNotes, "(?m)^\s*-\s*$([regex]::Escape([string]$field.label)):\s*(?<value>.+?)\s*$")
    $invalidRollbackField = -not $fieldMatch.Success
    if (-not $invalidRollbackField) {
      $fieldValue = $fieldMatch.Groups["value"].Value.Trim()
      $invalidRollbackField = [string]::IsNullOrWhiteSpace($fieldValue) -or $fieldValue -match "^(?i:tbd|todo|unknown|none|n/a|na)$"
    }
    if ($invalidRollbackField) {
      if ($AllowDraft) {
        Add-Warning ([string]$field.draft_code) "Draft release notes do not record a concrete $($field.message)."
      } else {
        Add-Failure ([string]$field.failure_code) "Full private-beta release notes must record a concrete $($field.message)."
      }
    }
  }
  $rollbackVerificationMatch = [regex]::Match($releaseNotes, "(?m)^\s*-\s*Verification after rollback:\s*(?<value>.+?)\s*$")
  $rollbackVerificationValue = if ($rollbackVerificationMatch.Success) { $rollbackVerificationMatch.Groups["value"].Value } else { "" }
  foreach ($requiredVerification in @("product-readiness", "admin health", "local smoke", "Telegram preview/dry-run")) {
    if ($rollbackVerificationValue -notmatch [regex]::Escape($requiredVerification)) {
      if ($AllowDraft) {
        Add-Warning "draft_release_notes_rollback_verification_missing" "Draft release notes rollback verification does not include '$requiredVerification'."
      } else {
        Add-Failure "release_notes_rollback_verification_missing" "Full private-beta release notes rollback verification must include '$requiredVerification'."
      }
    }
  }
}

$validationStatus = if ($failures.Count -eq 0) { "pass" } else { "fail" }
$failureItems = @()
foreach ($failure in $failures) {
  $failureItems += $failure
}
$warningItems = @()
foreach ($warning in $warnings) {
  $warningItems += $warning
}

$payload = [ordered]@{
  generated_at = (Get-Date).ToUniversalTime().ToString("o")
  manifest_path = $manifestPathResolved
  allow_draft = [bool]$AllowDraft
  status = $validationStatus
  failures = $failureItems
  warnings = $warningItems
}

$payloadJson = $payload | ConvertTo-Json -Depth 8
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($OutputPath, $payloadJson, $utf8NoBom)

Write-Host "[private-beta-evidence-validation] output: $OutputPath"
if ($failures.Count -gt 0) {
  foreach ($failure in $failures) {
    Write-Host "[private-beta-evidence-validation] failure: $($failure.code) - $($failure.message)"
  }
  throw "Private-beta evidence validation failed."
}

Write-Host "[private-beta-evidence-validation] OK"
