Set-Location D:\BotForex
New-Item -ItemType Directory -Force D:\BotForex\logs | Out-Null
$log = "D:\BotForex\logs\streamlit.log"
& "D:\BotForex\.venv\Scripts\streamlit.exe" run app.py --server.port 8501 *>> $log
