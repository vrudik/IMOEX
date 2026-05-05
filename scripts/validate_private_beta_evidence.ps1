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
$dailyWorkflowEvidence = [ordered]@{
  morning_brief = [ordered]@{
    present = $false
    signals_only = $false
    market_status = ""
    telegram_status = ""
    top_attention_count = 0
    dont_chase_count = 0
    execution_language_clear = $false
  }
  todays_operating_queue = [ordered]@{
    present = $false
    signals_only = $false
    total_items = 0
    review_due_items = 0
    reviewed_today_items = 0
    signal_linked_items = 0
    root_level_items = 0
    watched_roots = @()
    first_due_watch_key = ""
    first_due_root_code = ""
    first_due_signal_id = ""
    next_step = ""
    watchlist_present = $false
    total_matches_watchlist = $false
    state_counts_match_watchlist = $false
    counts_reconcile = $false
    first_due_matches_watchlist = $false
    next_step_matches_state = $false
    execution_language_clear = $false
  }
}

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

function Test-NonNegativeInteger {
  param([object]$Value)

  if ($null -eq $Value) {
    return $false
  }
  $text = ([string]$Value).Trim()
  if ($text -notmatch "^\d+$") {
    return $false
  }
  return [int64]$text -ge 0
}

function Get-JsonPropertyValue {
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
  return $property.Value
}

$forbiddenExecutionLanguagePattern = "(?i)\b(order\s*-?\s*routing|autotrading|broker\s+execution)\b"
$forbiddenExecutionFlagNames = @(
  "order_routing_authorized",
  "autotrading_authorized",
  "autotrading_enabled",
  "broker_execution_enabled"
)

function Test-ForbiddenExecutionLanguage {
  param([object]$Value)

  if ($null -eq $Value) {
    return $false
  }
  if ($Value -is [string]) {
    return $Value -match $forbiddenExecutionLanguagePattern
  }
  if ($Value -is [ValueType]) {
    return $false
  }
  if ($Value -is [System.Collections.IDictionary]) {
    foreach ($entry in $Value.GetEnumerator()) {
      if (Test-ForbiddenExecutionLanguage -Value $entry.Value) {
        return $true
      }
    }
    return $false
  }
  if ($Value -is [System.Collections.IEnumerable]) {
    foreach ($item in $Value) {
      if (Test-ForbiddenExecutionLanguage -Value $item) {
        return $true
      }
    }
    return $false
  }

  foreach ($property in $Value.PSObject.Properties) {
    if (Test-ForbiddenExecutionLanguage -Value $property.Value) {
      return $true
    }
  }
  return $false
}

function Find-ForbiddenExecutionFlagPaths {
  param(
    [object]$Value,
    [string]$Path = "$"
  )

  $matches = @()
  if ($null -eq $Value -or $Value -is [string] -or $Value -is [ValueType]) {
    return @($matches)
  }

  if ($Value -is [System.Collections.IDictionary]) {
    foreach ($entry in $Value.GetEnumerator()) {
      $name = [string]$entry.Key
      $childPath = "$Path.$name"
      if ($forbiddenExecutionFlagNames -contains $name) {
        $matches += $childPath
      }
      $matches += Find-ForbiddenExecutionFlagPaths -Value $entry.Value -Path $childPath
    }
    return @($matches)
  }

  if ($Value -is [System.Collections.IEnumerable]) {
    $index = 0
    foreach ($item in $Value) {
      $matches += Find-ForbiddenExecutionFlagPaths -Value $item -Path "$Path[$index]"
      $index += 1
    }
    return @($matches)
  }

  foreach ($property in $Value.PSObject.Properties) {
    $name = [string]$property.Name
    $childPath = "$Path.$name"
    if ($forbiddenExecutionFlagNames -contains $name) {
      $matches += $childPath
    }
    $matches += Find-ForbiddenExecutionFlagPaths -Value $property.Value -Path $childPath
  }
  return @($matches)
}

function Add-ForbiddenExecutionFlagFailures {
  param(
    [string]$Code,
    [string]$ArtifactLabel,
    [object]$Value
  )

  foreach ($forbiddenFlagPath in @(Find-ForbiddenExecutionFlagPaths -Value $Value)) {
    Add-Failure $Code "$ArtifactLabel must not include forbidden execution flag '$forbiddenFlagPath'."
  }
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
  "workspace_snapshot",
  "telegram_preview",
  "telegram_ops_preview",
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
Test-ManifestFlag "autotrading_authorized" $false

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
  $releaseCheckGreen = $releaseCheckText -match "product readiness OK" -and $releaseCheckText -match "\[release-check\] OK"
  if (-not $releaseCheckGreen) {
    if ($AllowDraft) {
      Add-Warning "draft_release_check_not_green" "Draft release-check log does not include product readiness OK and [release-check] OK."
    } else {
      Add-Failure "release_check_not_green" "Release-check log must include product readiness OK and [release-check] OK."
    }
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

$workspaceSnapshotPath = Get-ArtifactPath "workspace_snapshot"
if (-not [string]::IsNullOrWhiteSpace($workspaceSnapshotPath)) {
  $workspaceSnapshot = Get-Content -Path $workspaceSnapshotPath -Raw | ConvertFrom-Json
  if (-not ($workspaceSnapshot.PSObject.Properties.Name -contains "morning_brief")) {
    Add-Failure "workspace_snapshot_morning_brief_missing" "Workspace snapshot JSON must include morning_brief."
  } else {
    $morningBrief = $workspaceSnapshot.morning_brief
    $morningBriefSignalsOnly = ($morningBrief.PSObject.Properties.Name -contains "signals_only") -and [bool]$morningBrief.signals_only -eq $true
    $morningBriefExecutionLanguageClear = -not (Test-ForbiddenExecutionLanguage -Value $morningBrief)
    $dailyWorkflowEvidence.morning_brief = [ordered]@{
      present = $true
      signals_only = $morningBriefSignalsOnly
      market_status = [string](Get-JsonPropertyValue $morningBrief "market_status" "")
      telegram_status = [string](Get-JsonPropertyValue $morningBrief "telegram_status" "")
      top_attention_count = @((Get-JsonPropertyValue $morningBrief "top_attention" @())).Count
      dont_chase_count = @((Get-JsonPropertyValue $morningBrief "dont_chase" @())).Count
      execution_language_clear = $morningBriefExecutionLanguageClear
    }
    if (-not ($morningBrief.PSObject.Properties.Name -contains "signals_only") -or [bool]$morningBrief.signals_only -ne $true) {
      Add-Failure "workspace_snapshot_morning_brief_not_signals_only" "Morning Command Brief must remain signals-only."
    }
    if (@("fresh", "aging", "stale", "degraded", "hidden", "unknown") -notcontains [string]$morningBrief.market_status) {
      Add-Failure "workspace_snapshot_morning_brief_market_status_invalid" "Morning Command Brief must report a truthful market_status."
    }
    if (-not ($morningBrief.PSObject.Properties.Name -contains "top_attention")) {
      Add-Failure "workspace_snapshot_morning_brief_attention_missing" "Morning Command Brief must include top_attention."
    }
    if (-not ($morningBrief.PSObject.Properties.Name -contains "dont_chase")) {
      Add-Failure "workspace_snapshot_morning_brief_dont_chase_missing" "Morning Command Brief must include dont_chase safeguards."
    }
    if (@("ready", "preview") -notcontains [string]$morningBrief.telegram_status) {
      Add-Failure "workspace_snapshot_morning_brief_telegram_status_invalid" "Morning Command Brief Telegram status must be ready or preview."
    }
    if (-not $morningBriefExecutionLanguageClear) {
      Add-Failure "workspace_snapshot_morning_brief_execution_language" "Morning Command Brief evidence must not include order routing, autotrading, or broker execution language."
    }
  }
  if (-not ($workspaceSnapshot.PSObject.Properties.Name -contains "watchlist_workbench")) {
    Add-Failure "workspace_snapshot_watchlist_workbench_missing" "Workspace snapshot JSON must include watchlist_workbench."
  } else {
    $workbench = $workspaceSnapshot.watchlist_workbench
    if ($null -eq $workbench) {
      Add-Failure "workspace_snapshot_watchlist_workbench_missing" "Workspace snapshot JSON must include watchlist_workbench."
    } else {
      $workbenchProps = $workbench.PSObject.Properties.Name
      $workbenchSignalsOnly = ($workbenchProps -contains "signals_only") -and [bool]$workbench.signals_only -eq $true
      $workbenchExecutionLanguageClear = -not (Test-ForbiddenExecutionLanguage -Value $workbench)
      $watchedRootsForEvidence = @()
      $watchedRootsPropertyForEvidence = $workbench.PSObject.Properties["watched_roots"]
      if ($null -ne $watchedRootsPropertyForEvidence -and $null -ne $watchedRootsPropertyForEvidence.Value -and $watchedRootsPropertyForEvidence.Value -is [System.Array]) {
        $watchedRootsForEvidence = @($watchedRootsPropertyForEvidence.Value | ForEach-Object { [string]$_ })
      }
      $dailyWorkflowEvidence.todays_operating_queue.present = $true
      $dailyWorkflowEvidence.todays_operating_queue.signals_only = $workbenchSignalsOnly
      $dailyWorkflowEvidence.todays_operating_queue.watched_roots = $watchedRootsForEvidence
      $dailyWorkflowEvidence.todays_operating_queue.first_due_watch_key = [string](Get-JsonPropertyValue $workbench "first_due_watch_key" "")
      $dailyWorkflowEvidence.todays_operating_queue.first_due_root_code = [string](Get-JsonPropertyValue $workbench "first_due_root_code" "")
      $dailyWorkflowEvidence.todays_operating_queue.first_due_signal_id = [string](Get-JsonPropertyValue $workbench "first_due_signal_id" "")
      $dailyWorkflowEvidence.todays_operating_queue.next_step = [string](Get-JsonPropertyValue $workbench "next_step" "")
      $dailyWorkflowEvidence.todays_operating_queue.execution_language_clear = $workbenchExecutionLanguageClear
      if (-not ($workbenchProps -contains "signals_only") -or [bool]$workbench.signals_only -ne $true) {
        Add-Failure "workspace_snapshot_watchlist_workbench_not_signals_only" "Today's Operating Queue must remain signals-only."
      }

      $numericFieldsValid = $true
      $numericValues = @{}
      foreach ($fieldName in @("total_items", "review_due_items", "reviewed_today_items", "signal_linked_items", "root_level_items")) {
        $field = $workbench.PSObject.Properties[$fieldName]
        if ($null -eq $field -or -not (Test-NonNegativeInteger $field.Value)) {
          $numericFieldsValid = $false
        } else {
          $numericValues[$fieldName] = [int64]$field.Value
        }
      }
      if (-not $numericFieldsValid) {
        Add-Failure "workspace_snapshot_watchlist_workbench_counts_invalid" "Today's Operating Queue counts must be non-negative integers."
      } else {
        $dailyWorkflowEvidence.todays_operating_queue.total_items = $numericValues["total_items"]
        $dailyWorkflowEvidence.todays_operating_queue.review_due_items = $numericValues["review_due_items"]
        $dailyWorkflowEvidence.todays_operating_queue.reviewed_today_items = $numericValues["reviewed_today_items"]
        $dailyWorkflowEvidence.todays_operating_queue.signal_linked_items = $numericValues["signal_linked_items"]
        $dailyWorkflowEvidence.todays_operating_queue.root_level_items = $numericValues["root_level_items"]
        $watchlistProperty = $workspaceSnapshot.PSObject.Properties["watchlist"]
        $watchlistItems = @()
        if ($null -eq $watchlistProperty -or $null -eq $watchlistProperty.Value -or -not ($watchlistProperty.Value -is [System.Array])) {
          Add-Failure "workspace_snapshot_watchlist_missing" "Workspace snapshot JSON must include watchlist as a JSON array."
        } else {
          $dailyWorkflowEvidence.todays_operating_queue.watchlist_present = $true
          $watchlistItems = @($watchlistProperty.Value)
          $totalMatchesWatchlist = $watchlistItems.Count -eq $numericValues["total_items"]
          $dailyWorkflowEvidence.todays_operating_queue.total_matches_watchlist = $totalMatchesWatchlist
          if (-not $totalMatchesWatchlist) {
            Add-Failure "workspace_snapshot_watchlist_workbench_total_mismatch" "Today's Operating Queue total_items must match the archived workspace watchlist length."
          }
          $reviewDueWatchlistItems = @($watchlistItems | Where-Object { [string](Get-JsonPropertyValue $_ "review_state" "") -eq "review_due" })
          $reviewedTodayWatchlistItems = @($watchlistItems | Where-Object { [string](Get-JsonPropertyValue $_ "review_state" "") -eq "reviewed_today" })
          $signalLinkedWatchlistItems = @($watchlistItems | Where-Object { -not [string]::IsNullOrWhiteSpace([string](Get-JsonPropertyValue $_ "signal_id" "")) })
          $rootLevelWatchlistItems = @($watchlistItems | Where-Object { [string]::IsNullOrWhiteSpace([string](Get-JsonPropertyValue $_ "signal_id" "")) })
          $stateCountsMatchWatchlist = -not (
            $reviewDueWatchlistItems.Count -ne $numericValues["review_due_items"] -or
            $reviewedTodayWatchlistItems.Count -ne $numericValues["reviewed_today_items"] -or
            $signalLinkedWatchlistItems.Count -ne $numericValues["signal_linked_items"] -or
            $rootLevelWatchlistItems.Count -ne $numericValues["root_level_items"]
          )
          $dailyWorkflowEvidence.todays_operating_queue.state_counts_match_watchlist = $stateCountsMatchWatchlist
          if (-not $stateCountsMatchWatchlist) {
            Add-Failure "workspace_snapshot_watchlist_workbench_watchlist_counts_mismatch" "Today's Operating Queue counts must match archived workspace watchlist item states."
          }
        }
        $countsReconcile = -not (
          $numericValues["review_due_items"] -gt $numericValues["total_items"] -or
          $numericValues["reviewed_today_items"] -gt $numericValues["total_items"] -or
          ($numericValues["signal_linked_items"] + $numericValues["root_level_items"]) -ne $numericValues["total_items"]
        )
        $dailyWorkflowEvidence.todays_operating_queue.counts_reconcile = $countsReconcile
        if (-not $countsReconcile) {
          Add-Failure "workspace_snapshot_watchlist_workbench_counts_inconsistent" "Today's Operating Queue counts must reconcile to total_items."
        }
        if ($numericValues["review_due_items"] -gt 0) {
          $firstDueMatchesWatchlist = $false
          $firstDueWatchKey = ""
          $firstDueRootCode = ""
          $firstDueSignalId = ""
          if ($workbenchProps -contains "first_due_watch_key") {
            $firstDueWatchKey = [string]$workbench.first_due_watch_key
          }
          if ($workbenchProps -contains "first_due_root_code") {
            $firstDueRootCode = [string]$workbench.first_due_root_code
          }
          if ($workbenchProps -contains "first_due_signal_id") {
            $firstDueSignalId = [string]$workbench.first_due_signal_id
          }
          if ([string]::IsNullOrWhiteSpace($firstDueWatchKey) -or [string]::IsNullOrWhiteSpace($firstDueRootCode)) {
            Add-Failure "workspace_snapshot_watchlist_workbench_first_due_missing" "Today's Operating Queue must identify the first due item when reviews are due."
          }
          if ($watchlistItems.Count -gt 0) {
            $firstDueWatchlistItem = @($watchlistItems | Where-Object { [string](Get-JsonPropertyValue $_ "review_state" "") -eq "review_due" } | Select-Object -First 1)
            if ($firstDueWatchlistItem.Count -eq 0) {
              Add-Failure "workspace_snapshot_watchlist_workbench_first_due_mismatch" "Today's Operating Queue first due item must match an archived review_due watchlist entry."
            } else {
              $expectedFirstDue = $firstDueWatchlistItem[0]
              $expectedWatchKey = [string](Get-JsonPropertyValue $expectedFirstDue "watch_key" "")
              $expectedRootCode = [string](Get-JsonPropertyValue $expectedFirstDue "root_code" "")
              $expectedSignalId = [string](Get-JsonPropertyValue $expectedFirstDue "signal_id" "")
              if (
                $firstDueWatchKey -ne $expectedWatchKey -or
                $firstDueRootCode -ne $expectedRootCode -or
                $firstDueSignalId -ne $expectedSignalId
              ) {
                Add-Failure "workspace_snapshot_watchlist_workbench_first_due_mismatch" "Today's Operating Queue first due item must match the first archived review_due watchlist entry."
              } else {
                $firstDueMatchesWatchlist = $true
              }
            }
          }
          $dailyWorkflowEvidence.todays_operating_queue.first_due_matches_watchlist = $firstDueMatchesWatchlist
        } else {
          $dailyWorkflowEvidence.todays_operating_queue.first_due_matches_watchlist = $true
        }
      }

      $watchedRoots = $workbench.PSObject.Properties["watched_roots"]
      if ($null -eq $watchedRoots -or $null -eq $watchedRoots.Value -or -not ($watchedRoots.Value -is [System.Array])) {
        Add-Failure "workspace_snapshot_watchlist_workbench_roots_invalid" "Today's Operating Queue must include watched_roots as a JSON array."
      }
      if (-not ($workbenchProps -contains "next_step") -or [string]::IsNullOrWhiteSpace([string]$workbench.next_step)) {
        Add-Failure "workspace_snapshot_watchlist_workbench_next_step_missing" "Today's Operating Queue must include an operator-readable next_step."
      } else {
        $nextStep = [string]$workbench.next_step
        $nextStepMatchesState = $true
        if ($numericFieldsValid) {
          if ($numericValues["review_due_items"] -gt 0) {
            $firstDueSignalIdForNextStep = [string](Get-JsonPropertyValue $workbench "first_due_signal_id" "")
            if (-not [string]::IsNullOrWhiteSpace($firstDueSignalIdForNextStep) -and $nextStep -notmatch "(?i)(linked signal|signal context)") {
              $nextStepMatchesState = $false
              Add-Failure "workspace_snapshot_watchlist_workbench_next_step_mismatch" "Today's Operating Queue next_step must direct signal-linked due items to signal context."
            }
            if ([string]::IsNullOrWhiteSpace($firstDueSignalIdForNextStep) -and $nextStep -notmatch "(?i)root lane") {
              $nextStepMatchesState = $false
              Add-Failure "workspace_snapshot_watchlist_workbench_next_step_mismatch" "Today's Operating Queue next_step must direct root-level due items to the root lane."
            }
          } elseif ($numericValues["total_items"] -gt 0 -and $nextStep -notmatch "(?i)(reviewed today|queued watchlist)") {
            $nextStepMatchesState = $false
            Add-Failure "workspace_snapshot_watchlist_workbench_next_step_mismatch" "Today's Operating Queue next_step must explain that queued items are already reviewed today."
          } elseif ($numericValues["total_items"] -eq 0 -and $nextStep -notmatch "(?i)(no watchlist items|queued)") {
            $nextStepMatchesState = $false
            Add-Failure "workspace_snapshot_watchlist_workbench_next_step_mismatch" "Today's Operating Queue next_step must explain when no watchlist items are queued."
          }
        }
        $dailyWorkflowEvidence.todays_operating_queue.next_step_matches_state = $nextStepMatchesState
      }
      if (-not $workbenchExecutionLanguageClear) {
        Add-Failure "workspace_snapshot_watchlist_workbench_execution_language" "Today's Operating Queue evidence must not include order routing, autotrading, or broker execution language."
      }
    }
  }
  Add-ForbiddenExecutionFlagFailures "workspace_snapshot_forbidden_execution_flag" "Workspace snapshot JSON" $workspaceSnapshot
}

$telegramPreviewPath = Get-ArtifactPath "telegram_preview"
if (-not [string]::IsNullOrWhiteSpace($telegramPreviewPath)) {
  $telegramPreview = Get-Content -Path $telegramPreviewPath -Raw | ConvertFrom-Json
  Add-ForbiddenExecutionFlagFailures "telegram_preview_forbidden_execution_flag" "Telegram preview JSON" $telegramPreview
  if ([string]::IsNullOrWhiteSpace([string]$telegramPreview.root)) {
    Add-Failure "telegram_preview_root_missing" "Telegram preview JSON must include a root."
  }
  if (@("digest", "signal_open", "resolution", "post_mortem") -notcontains [string]$telegramPreview.event_kind) {
    Add-Failure "telegram_preview_event_kind_invalid" "Telegram preview JSON must include a supported event_kind."
  }
  if (-not ($telegramPreview.PSObject.Properties.Name -contains "delivery_allowed")) {
    Add-Failure "telegram_preview_delivery_allowed_missing" "Telegram preview JSON must include delivery_allowed."
  }
  if (-not ($telegramPreview.PSObject.Properties.Name -contains "configured")) {
    Add-Failure "telegram_preview_configured_missing" "Telegram preview JSON must include configured."
  }
  if ([string]::IsNullOrWhiteSpace([string]$telegramPreview.message)) {
    Add-Failure "telegram_preview_message_missing" "Telegram preview JSON must include an operator-readable message."
  }
}

$telegramOpsPreviewPath = Get-ArtifactPath "telegram_ops_preview"
if (-not [string]::IsNullOrWhiteSpace($telegramOpsPreviewPath)) {
  $telegramOpsPreview = Get-Content -Path $telegramOpsPreviewPath -Raw | ConvertFrom-Json
  Add-ForbiddenExecutionFlagFailures "telegram_ops_preview_forbidden_execution_flag" "Telegram ops preview JSON" $telegramOpsPreview
  if (-not ($telegramOpsPreview.PSObject.Properties.Name -contains "enabled")) {
    Add-Failure "telegram_ops_preview_enabled_missing" "Telegram ops preview JSON must include enabled."
  }
  if (-not ($telegramOpsPreview.PSObject.Properties.Name -contains "configured")) {
    Add-Failure "telegram_ops_preview_configured_missing" "Telegram ops preview JSON must include configured."
  }
  if (-not ($telegramOpsPreview.PSObject.Properties.Name -contains "alert_items")) {
    Add-Failure "telegram_ops_preview_alert_items_missing" "Telegram ops preview JSON must include alert_items."
  } elseif ($null -ne $telegramOpsPreview.alert_items) {
    $opsAlertItems = @($telegramOpsPreview.alert_items)
    foreach ($alertItem in $opsAlertItems) {
      $missingAlertFields = @()
      foreach ($fieldName in @("kind", "severity", "title", "detail")) {
        if (-not ($alertItem.PSObject.Properties.Name -contains $fieldName) -or [string]::IsNullOrWhiteSpace([string]$alertItem.$fieldName)) {
          $missingAlertFields += $fieldName
        }
      }
      if ($missingAlertFields.Count -gt 0) {
        Add-Failure "telegram_ops_preview_alert_item_incomplete" "Telegram ops preview alert_items entries must include kind, severity, title, and detail."
        break
      }
    }
  }
  if ([string]::IsNullOrWhiteSpace([string]$telegramOpsPreview.message)) {
    Add-Failure "telegram_ops_preview_message_missing" "Telegram ops preview JSON must include an operator-readable message."
  }
}

$browserSmokePath = Get-ArtifactPath "browser_smoke"
if (-not [string]::IsNullOrWhiteSpace($browserSmokePath)) {
  $browserSmoke = Get-Content -Path $browserSmokePath -Raw | ConvertFrom-Json
  $browserStatus = [string](Get-JsonPropertyValue $browserSmoke "status" "")
  $browserFailureCode = [string](Get-JsonPropertyValue $browserSmoke "failure_code" "")
  if ($browserStatus -eq "fail" -or -not [string]::IsNullOrWhiteSpace($browserFailureCode)) {
    Add-Failure "browser_smoke_failed" "Browser-smoke JSON must be from a passing browser run, not a recorded failure."
  }
  $browserChecks = @($browserSmoke.checks | ForEach-Object { [string]$_ })
  $requiredBrowserChecks = @(
    "workspace_opened",
    "workspace_morning_brief_visible",
    "workspace_watchlist_workbench_visible",
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
  foreach ($requiredSafetyFlag in @(
      "Signals-only decision support: true",
      "Release decision authorized: false",
      "Production deployment authorized: false",
      "Pricing commitment authorized: false",
      "Order routing authorized: false",
      "Autotrading authorized: false"
    )) {
    if ($acceptanceChecklist -notmatch [regex]::Escape($requiredSafetyFlag)) {
      if ($AllowDraft) {
        Add-Warning "draft_acceptance_checklist_safety_flag_missing" "Draft acceptance checklist does not include '$requiredSafetyFlag'."
      } else {
        Add-Failure "acceptance_checklist_safety_flag_missing" "Candidate-local acceptance checklist must include '$requiredSafetyFlag'."
      }
    }
  }
}

$candidateSummaryPath = Get-ArtifactPath "candidate_summary"
if (-not [string]::IsNullOrWhiteSpace($candidateSummaryPath)) {
  $candidateSummary = Get-Content -Path $candidateSummaryPath -Raw
  foreach ($requiredSafetyFlag in @(
      "Signals-only decision support: true",
      "Release decision authorized by this wrapper: false",
      "Production deployment authorized by this wrapper: false",
      "Pricing commitment authorized by this wrapper: false",
      "Order routing authorized by this wrapper: false",
      "Autotrading authorized by this wrapper: false"
    )) {
    if ($candidateSummary -notmatch [regex]::Escape($requiredSafetyFlag)) {
      if ($AllowDraft) {
        Add-Warning "draft_candidate_summary_safety_flag_missing" "Draft candidate summary does not include '$requiredSafetyFlag'."
      } else {
        Add-Failure "candidate_summary_safety_flag_missing" "Operator-readable candidate summary must include '$requiredSafetyFlag'."
      }
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
  foreach ($workspaceEvidenceLabel in @("Workspace snapshot JSON", "Telegram preview JSON", "Telegram ops preview JSON")) {
    $workspaceEvidencePattern = "(?m)^\s*-\s*$([regex]::Escape($workspaceEvidenceLabel)):\s*(?<path>.+?)\s*$"
    $workspaceEvidenceMatch = [regex]::Match($releaseNotes, $workspaceEvidencePattern)
    $workspaceEvidencePath = if ($workspaceEvidenceMatch.Success) { $workspaceEvidenceMatch.Groups["path"].Value.Trim() } else { "" }
    $invalidWorkspaceEvidencePath = [string]::IsNullOrWhiteSpace($workspaceEvidencePath) -or $workspaceEvidencePath -match "<[^>`r`n]+>" -or $workspaceEvidencePath -match "^(?i:tbd|todo|unknown|none|n/a|na)$"
    if ($invalidWorkspaceEvidencePath) {
      $evidenceFailureCode = if ($workspaceEvidenceLabel -like "Telegram*") { "release_notes_telegram_evidence_link_missing" } else { "release_notes_workspace_evidence_link_missing" }
      $evidenceDraftCode = if ($workspaceEvidenceLabel -like "Telegram*") { "draft_release_notes_telegram_evidence_link_missing" } else { "draft_release_notes_workspace_evidence_link_missing" }
      if ($AllowDraft) {
        Add-Warning $evidenceDraftCode "Draft release notes do not record a concrete $workspaceEvidenceLabel evidence link."
      } else {
        Add-Failure $evidenceFailureCode "Full private-beta release notes must record a concrete $workspaceEvidenceLabel evidence link."
      }
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
    "Morning Command Brief checked",
    "Today's Operating Queue checked",
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
  daily_workflow_evidence = $dailyWorkflowEvidence
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
