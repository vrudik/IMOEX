Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function New-EmptyDir([string]$Path) {
  if (Test-Path -LiteralPath $Path) {
    Remove-Item -LiteralPath $Path -Recurse -Force
  }
  New-Item -ItemType Directory -Path $Path | Out-Null
}

function Find-RepoRoot([string]$StartDir) {
  $p = (Resolve-Path -LiteralPath $StartDir).Path
  for ($i = 0; $i -lt 10; $i++) {
    if (Test-Path -LiteralPath (Join-Path $p "pyproject.toml")) {
      return $p
    }
    $parent = Split-Path -Parent $p
    if ($parent -eq $p -or $parent -eq "") {
      break
    }
    $p = $parent
  }
  throw "Could not find repo root (pyproject.toml not found). StartDir=$StartDir"
}

$repoRoot = Find-RepoRoot (Join-Path $PSScriptRoot "..")
$ctx = Join-Path $repoRoot ".docker-context"

Write-Host "Preparing docker build context at $ctx"
New-EmptyDir $ctx

# Copy minimal root files
Copy-Item -LiteralPath (Join-Path $repoRoot "pyproject.toml") -Destination $ctx
Copy-Item -LiteralPath (Join-Path $repoRoot "README.md") -Destination $ctx
Copy-Item -LiteralPath (Join-Path $repoRoot "alembic.ini") -Destination $ctx

# Copy directories we need. Robocopy avoids traversing unrelated/locked folders in repo root.
$dirs = @("apps", "libs", "infra", "tests", "docs", "scripts")
foreach ($d in $dirs) {
  $src = Join-Path $repoRoot $d
  $dst = Join-Path $ctx $d
  Write-Host "Copying $d ..."
  robocopy $src $dst /MIR /NFL /NDL /NJH /NJS /NP | Out-Null
}

Write-Host "Building python image..."
docker build -f infra/docker/python.Dockerfile -t imoex-signals-python:local $ctx

Write-Host "Building ui image..."
docker build -f infra/docker/ui.Dockerfile -t imoex-signals-ui:local $ctx

Write-Host "Done."
