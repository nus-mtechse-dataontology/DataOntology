@echo off
:: Run e2e golden question tests against a local Postgres instance and real LLM.
::
:: Fill in your credentials in scripts\local.env before running.
:: Required services: PostgreSQL on localhost:5432 with seed data from resources/seed_local.sql

setlocal

:: --- resolve project root ---
set "SCRIPT_DIR=%~dp0"
set "ROOT=%SCRIPT_DIR%.."
pushd "%ROOT%"
set "ROOT=%CD%"

:: --- load credentials ---
if not exist "%SCRIPT_DIR%local.env" (
    echo [ERROR] %SCRIPT_DIR%local.env not found. Copy scripts\local.env.example to scripts\local.env and fill in your credentials.
    exit /b 1
)
for /f "usebackq tokens=1,* delims==" %%a in ("%SCRIPT_DIR%local.env") do (
    if not "%%a"=="" if not "%%a:~0,1%"=="#" set "%%a=%%b"
)

:: --- check required env vars ---
if "%GEMINI_API_KEY%"=="" (
    echo [ERROR] GEMINI_API_KEY is not set.
    exit /b 1
)

:: --- check postgres is reachable ---
echo [INFO] Checking PostgreSQL connection...
uv run python -c "import socket; s=socket.socket(); s.settimeout(2); s.connect(('localhost',5432)); s.close()" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] PostgreSQL is not running on localhost:5432. Start it before running e2e tests.
    exit /b 1
)

set "PROJECT_PATH=%ROOT%"
echo [INFO] PROJECT_PATH=%PROJECT_PATH%

echo [INFO] Running e2e tests...
uv run pytest -m e2e -v %*
