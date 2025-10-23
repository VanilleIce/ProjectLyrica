@echo off
title Project Lyrica Launcher
color 0A

:: Set CMD window size (columns x rows)
mode con: cols=60 lines=10

echo Starting Project Lyrica...

:: Check if Python is installed
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in PATH
    pause
    exit /b 1
)

:: Check if required packages are installed
python -c "import customtkinter, pynput, psutil" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing required Python packages...
    pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo Error: Failed to install required packages
        pause
        exit /b 1
    )
)

:: Run the application
echo Launching Project Lyrica...
cd /d "%~dp0"
python code/ProjectLyrica.py

:: Pause if there was an error
if %errorlevel% neq 0 pause