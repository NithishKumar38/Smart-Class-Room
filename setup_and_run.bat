@echo off
echo ============================================================
echo  AI Classroom Co-Pilot — Setup and Launch Script
echo  Haryana Government Schools
echo ============================================================
echo.

cd /d "d:\projects\Projects\smart classroom"

REM ── Step 1: Create virtual environment ──────────────────────
echo [1/5] Creating virtual environment...
python -m venv venv
if errorlevel 1 (
    echo ERROR: Could not create virtual environment.
    echo Make sure Python 3.11+ is installed and in your PATH.
    pause
    exit /b 1
)
echo       Done!
echo.

REM ── Step 2: Activate venv ────────────────────────────────────
echo [2/5] Activating virtual environment...
call venv\Scripts\activate.bat
echo       Done!
echo.

REM ── Step 3: Upgrade pip ──────────────────────────────────────
echo [3/5] Upgrading pip...
python -m pip install --upgrade pip --quiet
echo       Done!
echo.

REM ── Step 4: Install requirements ─────────────────────────────
echo [4/5] Installing dependencies (this may take 3-5 minutes)...
echo       Please wait — downloading packages...
pip install -r requirements.txt
if errorlevel 1 (
    echo ERROR: Dependency installation failed.
    echo Check your internet connection and try again.
    pause
    exit /b 1
)
echo       All dependencies installed!
echo.

REM ── Step 5: Copy .env if missing ─────────────────────────────
echo [5/5] Setting up environment file...
if not exist .env (
    copy .env.example .env
    echo       .env file created from template.
    echo.
    echo ============================================================
    echo  ACTION REQUIRED:
    echo  Open .env file and replace:
    echo    GEMINI_API_KEY=your_gemini_api_key_here
    echo  with your actual Gemini API key from:
    echo    https://aistudio.google.com/app/apikey
    echo ============================================================
    echo.
    pause
) else (
    echo       .env file already exists.
)
echo.

REM ── Launch the app ───────────────────────────────────────────
echo ============================================================
echo  Launching AI Classroom Co-Pilot...
echo  App will open at: http://localhost:8501
echo  Press Ctrl+C to stop the server
echo ============================================================
echo.
streamlit run app.py

pause
