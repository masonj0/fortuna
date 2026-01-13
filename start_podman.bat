@echo off
REM ============================================================
REM Fortuna Faucet - Podman Launcher for Windows
REM A simple, friendly way to start your racing analysis engine
REM ============================================================

setlocal enabledelayedexpansion

REM Colors and styling
cls
echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║                                                            ║
echo ║            🐴  FORTUNA FAUCET LAUNCHER (Podman) 🐴         ║
echo ║          Racing Strategy Analysis Engine                  ║
echo ║                                                            ║
echo ╚════════════════════════════════════════════════════════════╝
echo.

REM ============================================================
REM STEP 1: Check if Podman is installed
REM ============================================================
echo [1/5] Checking for Podman installation...
podman --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo ✗ ERROR: Podman is not installed or not in PATH
    echo.
    echo To use Fortuna, you need Podman Desktop:
    echo https://podman-desktop.io/
    echo.
    echo After installing Podman, restart your computer and try again.
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('podman --version') do set PODMAN_VERSION=%%i
echo ✓ Found: %PODMAN_VERSION%
echo.

REM ============================================================
REM STEP 2: Check if Podman machine is running
REM ============================================================
echo [2/5] Checking if Podman machine is running...
podman ps >nul 2>&1
if errorlevel 1 (
    echo.
    echo ✗ ERROR: Podman machine is not running
    echo.
    echo Please:
    echo 1. Open "Podman Desktop" from your Start Menu
    echo 2. Make sure your Podman machine is started
    echo 3. Then run this launcher again
    echo.
    pause
    exit /b 1
)
echo ✓ Podman machine is running
echo.

REM ============================================================
REM STEP 3: Pull latest image
REM ============================================================
echo [3/5] Pulling latest Fortuna image from Docker Hub...
echo (This may take a minute on first run)
echo.
podman pull docker.io/masonj0/fortuna-faucet:latest
if errorlevel 1 (
    echo.
    echo ⚠ Warning: Could not pull from Docker Hub
    echo Checking for local image...
    podman image inspect masonj0/fortuna-faucet:latest >nul 2>&1
    if errorlevel 1 (
        echo ✗ ERROR: No local image found
        echo Please check your internet connection and try again.
        echo.
        pause
        exit /b 1
    )
    echo ✓ Using existing local image
)
echo ✓ Image ready
echo.

REM ============================================================
REM STEP 4: Start container
REM ============================================================
echo [4/5] Starting Fortuna container...
echo.

REM Stop any existing container (ignore errors)
podman stop fortuna-faucet >nul 2>&1
podman rm fortuna-faucet >nul 2>&1

REM Create data directories if they don't exist
if not exist "data" mkdir data
if not exist "logs" mkdir logs

REM Start container with proper quoting for paths with spaces
podman run -d ^
  --name fortuna-faucet ^
  -p 8000:8000 ^
  -v "%cd%\data:/app/web_service/backend/data" ^
  -v "%cd%\logs:/app/web_service/backend/logs" ^
  docker.io/masonj0/fortuna-faucet:latest

if errorlevel 1 (
    echo.
    echo ✗ ERROR: Failed to start container
    echo.
    echo Try these troubleshooting steps:
    echo 1. Open Podman Desktop
    echo 2. Make sure your Podman machine is running
    echo 3. Open Command Prompt and run: podman ps
    echo    (This tests if Podman is working)
    echo 4. Run this launcher again
    echo.
    pause
    exit /b 1
)

echo ✓ Container started successfully
echo.

REM ============================================================
REM STEP 5: Wait and verify startup
REM ============================================================
echo [5/5] Waiting for application to start...
timeout /t 3 /nobreak

REM Check if container is still running
podman inspect fortuna-faucet >nul 2>&1
if errorlevel 1 (
    echo.
    echo ✗ ERROR: Container exited unexpectedly
    echo.
    echo Showing container logs for debugging:
    echo.
    podman logs fortuna-faucet
    echo.
    pause
    exit /b 1
)

echo ✓ Application is ready!
echo.

REM ============================================================
REM SUCCESS - Open browser and show logs
REM ============================================================
cls
echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║                                                            ║
echo ║            🎉  FORTUNA IS RUNNING! (Podman) 🎉           ║
echo ║                                                            ║
echo ║  Your racing analysis engine is ready at:                ║
echo ║                                                            ║
echo ║          http://localhost:8000                            ║
echo ║                                                            ║
echo ║  Opening browser now...                                   ║
echo ║                                                            ║
echo ╚════════════════════════════════════════════════════════════╝
echo.

REM Open browser
start http://localhost:8000

REM Small delay to let browser open
timeout /t 2 /nobreak

REM Show logs
echo.
echo ┌────────────────────────────────────────────────────────────┐
echo │ Live Application Logs (Ctrl+C to stop)                    │
echo └────────────────────────────────────────────────────────────┘
echo.

podman logs -f fortuna-faucet

REM Cleanup on exit
echo.
echo Stopping Fortuna...
podman stop fortuna-faucet >nul 2>&1
echo ✓ Fortuna stopped

exit /b 0
