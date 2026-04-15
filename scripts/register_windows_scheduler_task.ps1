$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

param(
    [string]$TaskName = "IMOEX Scheduler Tick",
    [string]$TaskPath = "\IMOEX\",
    [string]$WorkspacePath = (Split-Path -Parent $PSScriptRoot),
    [string]$ExecutionPolicy = "Bypass",
    [string]$TaskUser = $env:USERNAME,
    [switch]$RunAsSystem
)

$schedulerScript = Join-Path $WorkspacePath "scripts\run_scheduler_loop.ps1"
if (-not (Test-Path $schedulerScript)) {
    throw "Scheduler loop script not found: $schedulerScript"
}

$quotedScript = '"' + $schedulerScript + '"'
$arguments = "-NoProfile -ExecutionPolicy $ExecutionPolicy -File $quotedScript --iterations 1 --sleep-seconds 0"
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $arguments -WorkingDirectory $WorkspacePath

$trigger = New-ScheduledTaskTrigger -Once -At ((Get-Date).AddMinutes(1))
$trigger.Repetition = New-ScheduledTaskRepetitionSettingsSet -Interval (New-TimeSpan -Minutes 1) -Duration (New-TimeSpan -Days 3650)

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 5) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

if ($RunAsSystem) {
    $principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
} else {
    $principal = New-ScheduledTaskPrincipal -UserId $TaskUser -LogonType InteractiveToken -RunLevel Highest
}

$task = New-ScheduledTask -Action $action -Trigger $trigger -Settings $settings -Principal $principal
Register-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -InputObject $task -Force | Out-Null

Write-Host "Registered Windows scheduler task:"
Write-Host "  Path: $TaskPath$TaskName"
Write-Host "  Action: powershell.exe $arguments"
Write-Host "  Policy: every 1 minute, multiple instances = IgnoreNew, restart up to 3 times"
