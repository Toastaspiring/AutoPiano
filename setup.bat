@echo off
title AutoPiano Setup
echo ================================================
echo  AutoPiano Setup
echo ================================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+ from https://python.org
    echo Make sure to check "Add Python to PATH" during installation.
    pause
    exit /b 1
)

echo [OK] Python found:
python --version
echo.

REM Install dependencies
echo Installing dependencies...
python -m pip install --upgrade pip --quiet
python -m pip install -r ModernAutoPiano\requirements.txt
if errorlevel 1 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo [OK] Dependencies installed.
echo.

REM Create launcher
echo Creating launcher...
(
echo @echo off
echo cd /d "%%~dp0"
echo start "" pythonw ModernAutoPiano\run.py
) > "AutoPiano.bat"

echo.
echo ================================================
echo  Setup complete!
echo  Run AutoPiano.bat to launch the app.
echo ================================================
echo.
pause