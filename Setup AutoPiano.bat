@echo off
setlocal enabledelayedexpansion
title AutoPiano Setup
color 0F

echo.
echo  ==============================================
echo   AutoPiano Setup
echo  ==============================================
echo.

:: ── Step 1: Check for Python 3.10+ ───────────────────────────────────────────
echo [1/3] Checking for Python...

set "PYTHON="
for %%c in (python python3 py) do (
    if not defined PYTHON (
        %%c --version >nul 2>&1
        if not errorlevel 1 (
            for /f "tokens=2" %%v in ('%%c --version 2^>^&1') do (
                for /f "tokens=1,2 delims=." %%a in ("%%v") do (
                    if %%a GEQ 3 if %%b GEQ 10 set "PYTHON=%%c"
                )
            )
        )
    )
)

if defined PYTHON (
    echo  [OK] Found: !PYTHON!
    goto :install_deps
)

:: ── Step 2: Install Python via winget ────────────────────────────────────────
echo  [!] Python 3.10+ not found. Attempting to install via winget...
echo.

winget --version >nul 2>&1
if errorlevel 1 (
    echo  [!] winget not available.
    goto :manual_python
)

winget install --id Python.Python.3.13 --source winget --silent --accept-package-agreements --accept-source-agreements
if errorlevel 1 (
    echo  [!] winget install failed.
    goto :manual_python
)

echo  [OK] Python installed via winget.
echo  Refreshing PATH...

:: Refresh PATH so python is available
for /f "usebackq tokens=2*" %%a in (`reg query "HKCU\Environment" /v PATH 2^>nul`) do set "UPATH=%%b"
for /f "usebackq tokens=2*" %%a in (`reg query "HKLM\SYSTEM\CurrentControlSet\Control\Session Manager\Environment" /v PATH 2^>nul`) do set "SPATH=%%b"
set "PATH=%SPATH%;%UPATH%;%LOCALAPPDATA%\Programs\Python\Python313;%LOCALAPPDATA%\Programs\Python\Python313\Scripts"

:: Re-check
for %%c in (python python3 py) do (
    if not defined PYTHON (
        %%c --version >nul 2>&1
        if not errorlevel 1 set "PYTHON=%%c"
    )
)

if defined PYTHON goto :install_deps

:manual_python
echo.
echo  ================================================
echo   Python could not be installed automatically.
echo.
echo   Please install Python 3.10+ manually:
echo     1. Go to https://python.org/downloads
echo     2. Download and run the installer
echo     3. CHECK "Add Python to PATH"
echo     4. Re-run this setup
echo  ================================================
echo.
pause
exit /b 1

:: ── Step 3: Install pip packages ─────────────────────────────────────────────
:install_deps
echo.
echo [2/3] Installing dependencies...
echo.

!PYTHON! -m pip install --upgrade pip --quiet
!PYTHON! -m pip install -r ModernAutoPiano\requirements.txt

if errorlevel 1 (
    echo.
    echo  [ERROR] Dependency installation failed.
    echo  Try running this script as Administrator.
    pause
    exit /b 1
)

echo.
echo  [OK] All packages installed.

:: ── Step 4: Create launcher ───────────────────────────────────────────────────
echo.
echo [3/3] Creating launcher...

(
echo @echo off
echo cd /d "%%~dp0"
echo start "" pythonw ModernAutoPiano\run.py
) > "AutoPiano.bat"

echo  [OK] AutoPiano.bat created.

:: ── Done ─────────────────────────────────────────────────────────────────────
echo.
echo  ==============================================
echo   Setup complete! Launching AutoPiano...
echo  ==============================================
echo.

start "" "AutoPiano.bat"
timeout /t 2 /nobreak >nul
exit /b 0
