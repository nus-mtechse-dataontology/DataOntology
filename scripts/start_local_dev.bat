@echo off
:: Start local dev environment: FastAPI server + ngrok tunnel + Telegram webhook registration.
::
:: Fill in your credentials in scripts\local.env before running.

setlocal enabledelayedexpansion

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
if "%TELEGRAM_BOT_TOKEN%"=="" (
    echo [ERROR] TELEGRAM_BOT_TOKEN is not set.
    exit /b 1
)

:: --- check ngrok is installed ---
where ngrok >nul 2>&1
if errorlevel 1 (
    echo [ERROR] ngrok is not installed. Install it from https://ngrok.com/download
    exit /b 1
)

set "PROJECT_PATH=%ROOT%"
echo [INFO] PROJECT_PATH=%PROJECT_PATH%

:: --- start FastAPI ---
echo [INFO] Starting FastAPI server on port 8000...
start /b uv run python src\main.py

:: --- start ngrok ---
echo [INFO] Starting ngrok tunnel on port 8000...
start /b ngrok http 8000 --log=stdout

:: --- wait for ngrok API to be ready ---
echo [INFO] Waiting for ngrok...
set READY=0
for /l %%i in (1,1,15) do (
    if !READY!==0 (
        curl -s http://localhost:4040/api/tunnels >nul 2>&1
        if not errorlevel 1 set READY=1
        if !READY!==0 timeout /t 1 /nobreak >nul
    )
)
if %READY%==0 (
    echo [ERROR] ngrok did not start in time.
    exit /b 1
)

:: --- get ngrok public URL ---
echo [INFO] Fetching ngrok public URL...
for /f "delims=" %%u in ('uv run python -c "import urllib.request,json; data=json.loads(urllib.request.urlopen(\"http://localhost:4040/api/tunnels\").read()); tunnels=data[\"tunnels\"]; https=[t for t in tunnels if t[\"proto\"]==\"https\"]; print(https[0][\"public_url\"] if https else tunnels[0][\"public_url\"])"') do set "NGROK_URL=%%u"
echo [INFO] ngrok URL: %NGROK_URL%

:: --- register Telegram webhook ---
set "WEBHOOK_URL=%NGROK_URL%/ontology/telegram/webhook"
echo [INFO] Registering Telegram webhook: %WEBHOOK_URL%

if "%TELEGRAM_WEBHOOK_SECRET%"=="" (
    set "PAYLOAD={\"url\": \"%WEBHOOK_URL%\"}"
) else (
    set "PAYLOAD={\"url\": \"%WEBHOOK_URL%\", \"secret_token\": \"%TELEGRAM_WEBHOOK_SECRET%\"}"
)

curl -s -X POST "https://api.telegram.org/bot%TELEGRAM_BOT_TOKEN%/setWebhook" ^
    -H "Content-Type: application/json" ^
    -d "!PAYLOAD!"

echo.
echo [INFO] Local dev environment is ready
echo [INFO]   FastAPI : http://localhost:8000/ontology/docs
echo [INFO]   ngrok   : %NGROK_URL%
echo [INFO]   Webhook : %WEBHOOK_URL%
echo.
echo [INFO] Close this window or press Ctrl+C to stop.
pause >nul
