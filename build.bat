@echo off
REM Create venv if not exists
if not exist .venv (
    python -m venv .venv
)

call .venv\Scripts\activate

REM Install deps
pip install -r requirements.txt
pip install pyinstaller

REM Build exe
pyinstaller main.spec

echo.
echo Build complete! Check the "dist" folder for MSFSExeXmlManager.exe
pause
