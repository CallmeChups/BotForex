@echo off
cd /d D:\BotForex
if not exist D:\BotForex\logs mkdir D:\BotForex\logs
D:\BotForex\.venv\Scripts\python.exe api_server.py --port 8502 >> D:\BotForex\logs\api_server.log 2>&1
