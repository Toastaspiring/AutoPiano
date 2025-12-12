@echo off
echo Building ModernAutoPiano...
python -m PyInstaller --noconfirm --onefile --console --name "ModernAutoPiano" --icon "NONE" --add-data "config;config" --paths "src" "run.py"
echo Build Complete. Check dist/ folder.
pause
