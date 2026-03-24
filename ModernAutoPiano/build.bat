@echo off
echo Building AutoPiano GUI...
python -m PyInstaller --noconfirm --onefile --windowed --name "AutoPiano" --add-data "config;config" --collect-all customtkinter --paths "src" "run.py"
echo.
echo Build complete. Executable is in dist\AutoPiano.exe
pause
