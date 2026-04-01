@echo off
title Abaad ERP v5.0

:: Try standard CPython venv layout first (Scripts\)
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
    goto launch
)

:: Fall back to MSYS2 / Git-Bash layout (bin\)
if exist "venv\bin\activate" (
    echo Note: Using MSYS2-style venv layout.
    echo Running python directly from venv\bin\
    set PATH=%CD%\venv\bin;%PATH%
    goto launch
)

echo  ERROR: Virtual environment not found.
echo  Please run SETUP.bat first.
echo.
pause
exit /b 1

:launch
python main.py

if errorlevel 1 (
    echo.
    echo  Startup failed — check the error above.
    echo  If the problem persists, try running SETUP.bat again.
    pause
    exit /b 1
)