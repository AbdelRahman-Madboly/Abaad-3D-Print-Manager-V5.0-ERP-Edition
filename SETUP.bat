@echo off
title Abaad 3D Print Manager — Setup
echo.
echo  Abaad 3D Print Manager v5.0 - Setup
echo  =====================================
echo.

:: Check that python is on PATH
python --version >nul 2>&1
if errorlevel 1 (
    echo  ERROR: Python was not found on your system.
    echo.
    echo  Please download and install Python 3.10 or later from:
    echo  https://www.python.org/downloads/
    echo.
    echo  IMPORTANT: During installation, check the box that says
    echo  "Add Python to PATH" before clicking Install Now.
    echo.
    pause
    exit /b 1
)

:: Run the cross-platform installer
python scripts\install.py
if errorlevel 1 (
    echo.
    echo  Setup encountered an error. See messages above for details.
    pause
    exit /b 1
)

pause