@echo off
echo ========================================
echo  Stopping BotForex services...
echo ========================================
echo.

taskkill /f /im ngrok.exe >nul 2>&1 && echo  [OK] ngrok stopped || echo  [--] ngrok not running
taskkill /f /im streamlit.exe >nul 2>&1 && echo  [OK] streamlit stopped || echo  [--] streamlit not running
taskkill /f /fi "WINDOWTITLE eq Streamlit*" >nul 2>&1

:: Also kill any python processes running bot_runner (trading bots)
:: Uncomment below if you want to also stop running bots:
:: taskkill /f /fi "WINDOWTITLE eq bot_*" >nul 2>&1 && echo  [OK] bots stopped

echo.
echo  All services stopped.
echo ========================================
pause
