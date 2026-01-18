@echo off
echo ========================================
echo BotForex Dashboard - Starting...
echo ========================================

:: Start Streamlit in background
start "Streamlit" cmd /c "cd /d E:\Project\BotForex && .venv\Scripts\streamlit run app.py --server.port 8501 --server.headless true"

:: Wait for Streamlit to start
timeout /t 5 /nobreak > nul

:: Start ngrok tunnel
echo.
echo Starting ngrok tunnel...
echo Your public URL will appear below:
echo ========================================
ngrok http 8501
