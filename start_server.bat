@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

echo ========================================
echo  BotForex Server - Auto Setup
echo ========================================
echo.

:: -------------------------------------------
:: CONFIG (edit these paths if needed)
:: -------------------------------------------
set "BOT_DIR=%~dp0"
set "EXNESS_EXE=C:\Program Files\MetaTrader 5 EXNESS\terminal64.exe"
set "NGROK_EXE=C:\Users\Hyperion\Downloads\ngrok-v3-stable-windows-amd64\ngrok.exe"
set "ULTRAVIEWER_EXE=C:\Program Files (x86)\UltraViewer\UltraViewer_Desktop.exe"
set "STREAMLIT_PORT=8501"

:: Load Telegram config from .env
for /f "tokens=1,2 delims==" %%a in ('type "%BOT_DIR%.env" ^| findstr /v "#" ^| findstr /b "TELEGRAM_BOT_TOKEN= TELEGRAM_CHAT_ID="') do (
    set "%%a=%%b"
)

:: -------------------------------------------
:: STEP 1: Fix timezone to GMT+7
:: -------------------------------------------
echo [1/6] Setting timezone to GMT+7 (SE Asia)...
tzutil /s "SE Asia Standard Time" >nul 2>&1
if %errorlevel% equ 0 (
    echo       OK - Timezone set to SE Asia Standard Time
) else (
    echo       WARN - Need admin rights to set timezone
    echo       Run this .bat as Administrator if timezone keeps resetting
)
echo.

:: -------------------------------------------
:: STEP 2: Start MetaTrader 5 (Exness)
:: -------------------------------------------
echo [2/6] Starting MetaTrader 5 (Exness)...
if exist "%EXNESS_EXE%" (
    start "" "%EXNESS_EXE%"
    echo       OK - MT5 launched. Verify your trading account is correct.
) else (
    echo       SKIP - MT5 not found at: %EXNESS_EXE%
)
echo.

:: -------------------------------------------
:: STEP 3: Start UltraViewer (optional)
:: -------------------------------------------
echo [3/6] Starting UltraViewer...
if exist "%ULTRAVIEWER_EXE%" (
    start "" "%ULTRAVIEWER_EXE%"
    echo       OK - UltraViewer launched.
    echo       NOTE: ID and Password will be sent to Telegram after manual input.
) else (
    echo       SKIP - UltraViewer not found at: %ULTRAVIEWER_EXE%
)
echo.

:: -------------------------------------------
:: STEP 4: Start Streamlit
:: -------------------------------------------
echo [4/6] Starting Streamlit dashboard...
start /min "Streamlit" cmd /c "cd /d "%BOT_DIR%" && .venv\Scripts\streamlit run app.py --server.port %STREAMLIT_PORT% --server.headless true"
echo       OK - Streamlit starting on port %STREAMLIT_PORT%...

:: Wait for Streamlit to be ready
echo       Waiting for Streamlit to be ready...
set "READY=0"
for /l %%i in (1,1,15) do (
    if !READY! equ 0 (
        timeout /t 1 /nobreak >nul
        curl -s -o nul -w "" http://localhost:%STREAMLIT_PORT% >nul 2>&1
        if !errorlevel! equ 0 (
            set "READY=1"
            echo       OK - Streamlit is ready!
        )
    )
)
if !READY! equ 0 (
    echo       WARN - Streamlit may still be loading, continuing anyway...
)
echo.

:: -------------------------------------------
:: STEP 5: Start ngrok tunnel
:: -------------------------------------------
echo [5/6] Starting ngrok tunnel...
if not exist "%NGROK_EXE%" (
    echo       ERROR - ngrok not found at: %NGROK_EXE%
    echo       Please install ngrok or update the path in this file.
    goto :done
)

:: Kill any existing ngrok
taskkill /f /im ngrok.exe >nul 2>&1

:: Start ngrok in background
start /min "ngrok" "%NGROK_EXE%" http %STREAMLIT_PORT%

:: Wait for ngrok API to be ready
echo       Waiting for ngrok tunnel...
set "NGROK_URL="
for /l %%i in (1,1,10) do (
    if "!NGROK_URL!" == "" (
        timeout /t 1 /nobreak >nul
        for /f "delims=" %%u in ('curl -s http://localhost:4040/api/tunnels 2^>nul ^| "%BOT_DIR%.venv\Scripts\python.exe" -c "import sys,json; d=json.load(sys.stdin); print(d['tunnels'][0]['public_url'] if d.get('tunnels') else '')" 2^>nul') do (
            set "NGROK_URL=%%u"
        )
    )
)

if "!NGROK_URL!" == "" (
    echo       ERROR - Could not get ngrok URL. Check ngrok manually.
    goto :done
)

echo       OK - Public URL: !NGROK_URL!
echo.

:: -------------------------------------------
:: STEP 6: Send URL to Telegram
:: -------------------------------------------
echo [6/6] Sending server URL to Telegram...

if "!TELEGRAM_BOT_TOKEN!" == "" (
    echo       SKIP - Telegram not configured in .env
    goto :done
)

:: Format current time
for /f "delims=" %%t in ('"%BOT_DIR%.venv\Scripts\python.exe" -c "from datetime import datetime; from zoneinfo import ZoneInfo; print(datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')).strftime('%%H:%%M %%d/%%m/%%Y'))"') do set "NOW=%%t"

set "MSG=🚀 <b>BotForex Server Started</b>%%0A%%0A🌐 Dashboard: !NGROK_URL!%%0A⏰ Time: !NOW!%%0A%%0AServer is ready for trading."

curl -s -X POST "https://api.telegram.org/bot!TELEGRAM_BOT_TOKEN!/sendMessage" ^
    -d "chat_id=!TELEGRAM_CHAT_ID!" ^
    -d "text=!MSG!" ^
    -d "parse_mode=HTML" >nul 2>&1

if %errorlevel% equ 0 (
    echo       OK - URL sent to Telegram!
) else (
    echo       WARN - Failed to send Telegram message
)

:done
echo.
echo ========================================
echo  Setup Complete!
echo ========================================
echo  Dashboard: http://localhost:%STREAMLIT_PORT%
if not "!NGROK_URL!" == "" echo  Public:    !NGROK_URL!
echo.
echo  Press any key to close this window.
echo  (Streamlit and ngrok will keep running)
echo ========================================
pause >nul
