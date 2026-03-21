@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

echo ========================================
echo  BotForex DEV Server (UI Redesign)
echo  Port: 8502
echo ========================================
echo.

set "BOT_DIR=%~dp0"
set "DEV_PORT=8502"

echo Starting Streamlit on port %DEV_PORT%...
start /min "Streamlit-Dev" cmd /c "cd /d "%BOT_DIR%" && .venv\Scripts\streamlit run app.py --server.port %DEV_PORT% --server.headless true"

:: Wait until ready
set "READY=0"
for /l %%i in (1,1,15) do (
    if !READY! equ 0 (
        timeout /t 1 /nobreak >nul
        curl -s -o nul http://localhost:%DEV_PORT% >nul 2>&1
        if !errorlevel! equ 0 (
            set "READY=1"
            echo OK - Dev server ready!
        )
    )
)
if !READY! equ 0 echo WARN - Still loading, open manually...

echo.
echo  Dashboard: http://localhost:%DEV_PORT%
echo  (Production stays at port 8501)
echo.
echo  Press any key to close this window.
pause >nul
