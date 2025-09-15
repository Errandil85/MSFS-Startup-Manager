REM Create venv if not exists
if not exist .venv (
    python -m venv .venv
)

call .venv\Scripts\activate

REM Install deps
pip install -r requirements.txt
pip install pyinstaller