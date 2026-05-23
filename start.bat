@echo off
cd /d "%~dp0"
title Albion Bot
set PYTHONIOENCODING=utf-8

:loop
echo [%date% %time%] Starting bot...
python -u bot.py
echo [%date% %time%] Bot stopped. Restarting in 5 seconds...
timeout /t 5 /nobreak >nul
goto loop
