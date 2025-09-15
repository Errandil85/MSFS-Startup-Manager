@echo off
REM Build script for MSFS exe.xml Manager
REM Requires PyInstaller installed: pip install pyinstaller

REM Create venv if not exists
if not exist .venv (
    python -m venv .venv
)

call .venv\Scripts\activate

REM Install deps
pip install -r requirements.txt
pip install pyinstaller

set APP_NAME=MSFS-Startup-Manager
set ICON_FILE=icon.ico

REM Clean old builds
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
if exist %APP_NAME%.spec del %APP_NAME%.spec

REM Build exe
pyinstaller ^
 --noconfirm ^
 --onefile ^
 --windowed ^
 --name "%APP_NAME%" ^
 --icon "%ICON_FILE%" ^
 --add-data "%ICON_FILE%;." ^
 main.py

copy "%ICON_FILE%" dist\
echo.
echo Build finished. EXE located in the "dist" folder.
pause
