@echo off
setlocal
title Project Lyrica Launcher

echo ========================================
echo         Project Lyrica v2.8.0
echo ========================================
echo.

:: Check Python
where python >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+ and add it to PATH.
    pause
    exit /b 1
)

:: Check entry script
if not exist "code\ProjectLyrica.py" (
    echo [ERROR] code\ProjectLyrica.py not found.
    echo Make sure you run this from the Project Lyrica folder.
    pause
    exit /b 1
)

:: Run the application
cd /d "%~dp0"
python code\ProjectLyrica.py

:: Handle exit code
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Application crashed with exit code %errorlevel%.
    pause
    exit /b %errorlevel%
)

echo.
echo Application closed normally.
timeout /t 2 >nul