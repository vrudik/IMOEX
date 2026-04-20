param(
    [int]$Port = 8011,
    [string]$Root = "Si",
    [int]$ReadyTimeoutSeconds = 30,
    [switch]$WaitUntilReady,
    [switch]$SkipWarmup,
    [switch]$ForceRestart
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$python = if (Test-Path $venvPython) { $venvPython } else { "python" }

$previewRoot = Join-Path $env:TEMP "imoex-preview-$Port"
$databasePath = Join-Path $previewRoot "preview.db"
$backupsPath = Join-Path $previewRoot "backups"
$pidPath = Join-Path $previewRoot "preview.pid"
$serverPidPath = Join-Path $previewRoot "server.pid"
$metadataPath = Join-Path $previewRoot "preview.json"
$stdoutPath = Join-Path $previewRoot "preview.stdout.log"
$stderrPath = Join-Path $previewRoot "preview.stderr.log"

function Get-PreviewPortListenerPid {
    param([int]$Port)

    $listenerLines = netstat -ano -p TCP |
        Select-String -Pattern "LISTENING" |
        Where-Object { $_.Line -match "[:.]$Port\s" }

    foreach ($match in $listenerLines) {
        if ($match.Line -match "LISTENING\s+(\d+)\s*$") {
            return [int]$Matches[1]
        }
    }

    return $null
}

function Get-PreviewProcessLabel {
    param([int]$ProcessId)

    $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if ($process) {
        return "$($process.ProcessName) (PID $ProcessId)"
    }
    return "PID $ProcessId"
}

function Stop-ManagedPreviewProcess {
    param([int]$ProcessId)

    $process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if ($process) {
        Stop-Process -Id $ProcessId -ErrorAction Stop
        Start-Sleep -Milliseconds 800
    }
}

function Get-StoredPreviewPid {
    param([string]$Path)

    if (-not (Test-Path $Path)) {
        return $null
    }

    $rawPid = Get-Content -Path $Path -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($rawPid -and $rawPid -match '^\d+$') {
        return [int]$rawPid
    }

    return $null
}

New-Item -ItemType Directory -Force -Path $previewRoot | Out-Null
New-Item -ItemType Directory -Force -Path $backupsPath | Out-Null

$storedPreviewPid = Get-StoredPreviewPid -Path $pidPath
$storedServerPid = Get-StoredPreviewPid -Path $serverPidPath

$listenerPid = Get-PreviewPortListenerPid -Port $Port
if ($null -ne $listenerPid) {
    $managedListener = ($storedPreviewPid -and $listenerPid -eq $storedPreviewPid) -or (
        $storedServerPid -and $listenerPid -eq $storedServerPid
    )
    if ($managedListener) {
        if (-not $ForceRestart) {
            Write-Host "[preview] already running on port $Port with listener PID $listenerPid"
            if (Test-Path $metadataPath) {
                Get-Content -Path $metadataPath
            }
            exit 0
        }

        foreach ($managedPid in @($storedPreviewPid, $storedServerPid) | Where-Object { $_ } | Select-Object -Unique) {
            Stop-ManagedPreviewProcess -ProcessId $managedPid
        }
        $listenerPid = Get-PreviewPortListenerPid -Port $Port
    }

    if ($null -ne $listenerPid) {
        throw "Port $Port is already occupied by $(Get-PreviewProcessLabel -ProcessId $listenerPid). Refusing to reuse an unmanaged listener."
    }
}

if ($storedPreviewPid) {
    $storedProcess = Get-Process -Id $storedPreviewPid -ErrorAction SilentlyContinue
    if (-not $storedProcess) {
        Remove-Item -LiteralPath $pidPath -ErrorAction SilentlyContinue
    } elseif ($ForceRestart) {
        Stop-ManagedPreviewProcess -ProcessId $storedPreviewPid
    }
}

if ($storedServerPid) {
    $serverProcess = Get-Process -Id $storedServerPid -ErrorAction SilentlyContinue
    if (-not $serverProcess) {
        Remove-Item -LiteralPath $serverPidPath -ErrorAction SilentlyContinue
    } elseif ($ForceRestart -and (-not $storedPreviewPid -or $storedServerPid -ne $storedPreviewPid)) {
        Stop-ManagedPreviewProcess -ProcessId $storedServerPid
    }
}

if ($ForceRestart) {
    Remove-Item -LiteralPath $pidPath -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $serverPidPath -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $metadataPath -ErrorAction SilentlyContinue
}

$argumentList = @("-m", "apps.preview_runner", "--port", "$Port", "--root", $Root)
if ($SkipWarmup) {
    $argumentList += "--skip-warmup"
}
$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $python
$psi.Arguments = [string]::Join(" ", ($argumentList | ForEach-Object {
    if ($_ -match "\s") { '"{0}"' -f $_ } else { $_ }
}))
$psi.WorkingDirectory = $repoRoot
$psi.UseShellExecute = $true
$psi.WindowStyle = [System.Diagnostics.ProcessWindowStyle]::Hidden

$process = [System.Diagnostics.Process]::Start($psi)
if ($null -eq $process) {
    throw "Failed to start preview process."
}

Set-Content -Path $pidPath -Value $process.Id

$workspaceUrl = "http://127.0.0.1:$Port/workspace?root=$Root"
$dashboardUrl = "http://127.0.0.1:$Port/dashboard?root=$Root"
$metadata = [ordered]@{
    pid = $process.Id
    port = $Port
    root = $Root
    database_path = $databasePath
    backups_path = $backupsPath
    workspace_url = $workspaceUrl
    dashboard_url = $dashboardUrl
    stdout_log = $stdoutPath
    stderr_log = $stderrPath
    started_at = (Get-Date).ToString("s")
}

if (-not $WaitUntilReady) {
    Start-Sleep -Milliseconds 700
    if ($process.HasExited) {
        $stdoutTail = Get-Content -Path $stdoutPath -ErrorAction SilentlyContinue | Out-String
        $stderrTail = Get-Content -Path $stderrPath -ErrorAction SilentlyContinue | Out-String
        throw "Preview process exited immediately. STDERR: $stderrTail STDOUT: $stdoutTail"
    }
    $metadata.server_pid = Get-StoredPreviewPid -Path $serverPidPath
    $metadata.listener_pid = Get-PreviewPortListenerPid -Port $Port
    $metadata | ConvertTo-Json | Set-Content -Path $metadataPath
    $metadata | ConvertTo-Json
    exit 0
}

$ready = $false
$processExitedEarly = $false
$deadline = (Get-Date).AddSeconds($ReadyTimeoutSeconds)

while ((Get-Date) -lt $deadline) {
    if ($process.HasExited) {
        $processExitedEarly = $true
    }
    try {
        $response = Invoke-WebRequest -UseBasicParsing $workspaceUrl -TimeoutSec 2
        if ($response.StatusCode -eq 200) {
            $ready = $true
            break
        }
    } catch {
        Start-Sleep -Milliseconds 500
    }
}

if (-not $ready) {
    $stdoutTail = Get-Content -Path $stdoutPath -ErrorAction SilentlyContinue | Out-String
    $stderrTail = Get-Content -Path $stderrPath -ErrorAction SilentlyContinue | Out-String
    try {
        if (-not $process.HasExited) {
            Stop-Process -Id $process.Id
        }
    } catch {
    }
    if ($processExitedEarly) {
        throw "Preview process exited before readiness on port $Port. STDERR: $stderrTail STDOUT: $stdoutTail"
    }
    throw "Preview did not become ready on port $Port within $ReadyTimeoutSeconds seconds."
}

$metadata.server_pid = Get-StoredPreviewPid -Path $serverPidPath
$metadata.listener_pid = Get-PreviewPortListenerPid -Port $Port
$metadata | ConvertTo-Json | Set-Content -Path $metadataPath
$metadata | ConvertTo-Json
