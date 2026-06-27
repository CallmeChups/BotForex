@echo off
cd /d D:\BotForex
if not exist D:\BotForex\logs mkdir D:\BotForex\logs
D:\BotForex\.venv\Scripts\streamlit.exe run app.py --server.port 8501 >> D:\BotForex\logs\streamlit.log 2>&1
