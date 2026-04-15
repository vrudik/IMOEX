@echo off
setlocal

set "PORT=%~1"
if "%PORT%"=="" set "PORT=8011"

set "REPO_ROOT=%~dp0.."
for %%I in ("%REPO_ROOT%") do set "REPO_ROOT=%%~fI"

set "PREVIEW_ROOT=%TEMP%\imoex-preview-%PORT%"
set "DATABASE_PATH=%PREVIEW_ROOT%\preview.db"
set "BACKUPS_PATH=%PREVIEW_ROOT%\backups"

if not exist "%PREVIEW_ROOT%" mkdir "%PREVIEW_ROOT%"
if not exist "%BACKUPS_PATH%" mkdir "%BACKUPS_PATH%"

set "PYTHON=%REPO_ROOT%\.venv\Scripts\python.exe"
if not exist "%PYTHON%" set "PYTHON=python"

set "PYTHONPATH=%REPO_ROOT%\.vendor;%REPO_ROOT%"
set "DATABASE_URL=sqlite:///%DATABASE_PATH:\=/%"
set "BACKUPS_DIR=%BACKUPS_PATH%"

pushd "%REPO_ROOT%"
start "imoex-preview-%PORT%" /min "%PYTHON%" -m uvicorn apps.api.main:app --host 127.0.0.1 --port %PORT%
popd

echo Preview starting on http://127.0.0.1:%PORT%/workspace
echo Database: %DATABASE_PATH%
