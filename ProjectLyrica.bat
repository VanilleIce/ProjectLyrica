@echo off
title Project Lyrica Launcher
color 0A

echo ========================================
echo         Project Lyrica v2.8.0
echo ========================================
echo.

:: Run the application
cd /d "%~dp0"
python code/ProjectLyrica.py

:: Pause if there was an error
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Application crashed!
    pause
)