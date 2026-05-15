param(
  [string]$Root = "Si",
  [string]$SecondaryRoot = "BR",
  [string]$Channel = "",
  [switch]$Headed,
  [switch]$AllowMissingDependency
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$python = if (Test-Path $venvPython) { $venvPython } else { "python" }

$argsList = @((Join-Path $repoRoot "scripts\browser_smoke.py"), "--root", $Root, "--secondary-root", $SecondaryRoot)
if (-not [string]::IsNullOrWhiteSpace($Channel)) {
  $argsList += @("--channel", $Channel)
}
if ($Headed) {
  $argsList += "--headed"
}
if ($AllowMissingDependency) {
  $argsList += "--allow-missing-dependency"
}

& $python @argsList
if ($LASTEXITCODE -ne 0) {
  throw "Browser smoke failed with exit code $LASTEXITCODE"
}
