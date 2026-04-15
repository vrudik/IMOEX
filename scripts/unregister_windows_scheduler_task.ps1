$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

param(
    [string]$TaskName = "IMOEX Scheduler Tick",
    [string]$TaskPath = "\IMOEX\"
)

Unregister-ScheduledTask -TaskName $TaskName -TaskPath $TaskPath -Confirm:$false
Write-Host "Removed Windows scheduler task: $TaskPath$TaskName"
