@echo off
cd /d "%~dp0"

:: Try pythonw (no console window), fall back to python, then py launcher
set "PYEXE="
for %%c in (pythonw.exe pythonw python.exe python py.exe py) do (
    if not defined PYEXE (
        where %%c >nul 2>&1 && set "PYEXE=%%c"
    )
)

if not defined PYEXE (
    echo Python not found. Please install Python 3.10+ from https://python.org
    pause
    exit /b 1
)

start "" "%PYEXE%" ModernAutoPiano\run.py
