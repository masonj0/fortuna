@echo off
setlocal enabledelayedexpansion

:: ============================================================================
:: Fortuna Faucet - Unified Development Environment Runner
:: ============================================================================
:: This script automates the setup and launch of the full development
:: environment (Python backend + Next.js frontend).
::
:: It will:
:: 1. Check for required dependencies (Python 3.11+, Node.js).
:: 2. Create and populate the Python virtual environment if missing.
:: 3. Install frontend Node modules if missing.
:: 4. Launch both backend and frontend servers concurrently.
:: ============================================================================

title Fortuna Faucet Dev Runner

:: --- Phase 1: Pre-flight Checks ---
echo [1/4] Running pre-flight checks...

:: Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not found in your PATH. Please install Python 3.11 or later.
    pause
    exit /b 1
)

:: Check for Node.js
npm --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js (npm) is not found in your PATH. Please install Node.js (LTS).
    pause
    exit /b 1
)
echo [OK] All prerequisites found.
echo.

:: --- Phase 2: Environment Setup ---
echo [2/4] Verifying development environment...

:: Check for Python virtual environment
if not exist ".venv" (
    echo [INFO] Python virtual environment not found. Creating it now...
    python -m venv .venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create Python virtual environment.
        pause
        exit /b 1
    )
    echo [INFO] Virtual environment created.
)

:: Check for Python dependencies
echo [INFO] Installing/verifying Python dependencies...
call .\.venv\Scripts\activate.bat
pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install Python dependencies from requirements.txt.
    pause
    exit /b 1
)
call .\.venv\Scripts\deactivate.bat
echo [OK] Python environment is ready.
echo.

:: Check for frontend dependencies
if not exist "web_platform\frontend\node_modules" (
    echo [INFO] Frontend dependencies (node_modules) not found. Installing now...
    npm install --prefix web_platform/frontend
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install frontend dependencies.
        pause
        exit /b 1
    )
)
echo [OK] Frontend environment is ready.
echo.


:: --- Phase 3: Launch Services ---
echo [3/4] Launching services...
echo [INFO] Starting Python backend server in a new window...
start "Fortuna Backend" cmd /c "call .\.venv\Scripts\activate.bat && python -m uvicorn python_service.api:app --host 127.0.0.1 --port 8000"

echo [INFO] Starting Next.js frontend server in a new window...
start "Fortuna Frontend" cmd /c "npm run dev --prefix web_platform/frontend"

echo.

:: --- Phase 4: Open Browser ---
echo [4/4] Opening application in browser...
echo [INFO] Waiting 10 seconds for servers to initialize...
timeout /t 10 /nobreak >nul
start http://localhost:3000

echo.
echo ============================================================================
echo  All services launched! You can close this window.
echo ============================================================================
echo.

pause
exit /b 0
