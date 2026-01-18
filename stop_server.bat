@echo off
echo Stopping BotForex services...
taskkill /f /im ngrok.exe 2>nul
taskkill /f /im streamlit.exe 2>nul
taskkill /f /fi "WINDOWTITLE eq Streamlit*" 2>nul
echo Done.
