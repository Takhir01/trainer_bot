@echo off
title ThirtyFiveCoach Bot
color 0A

echo ========================================
echo       ThirtyFiveCoach Telegram Bot
echo ========================================
echo.

cd /d "%~dp0"

if not exist venv\Scripts\python.exe (
    echo [ERROR] Virtual environment not found!
    echo Please make sure the venv folder is created.
    pause
    exit /b
)

echo Starting bot.py...
echo To stop the bot, close this window or press Ctrl+C.
echo.

.\venv\Scripts\python.exe bot.py

echo.
echo Bot stopped.
pause
