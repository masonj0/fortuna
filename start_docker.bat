@echo off
REM ============================================================
REM Fortuna Faucet - Docker Launcher for Windows
REM A simple, friendly way to start your racing analysis engine
REM ============================================================

setlocal enabledelayedexpansion

REM Colors and styling
cls
echo.
echo ╔════════════════════════════════════════════════════════════╗
echo ║                                                            ║
echo ║            🐴  FORTUNA FAUCET LAUNCHER  🐴                ║
echo ║          Racing Strategy Analysis Engine                  ║
echo ║                                                            ║
echo ╚════════════════════════════════════════════════════════════╝
echo.

REM ============================================================
REM STEP 1: Check if Docker is installed
REM ============================================================
echo [1/5] Checking for Docker installation...
docker --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo ✗ ERROR: Docker is not installed or not in PATH
    echo.
    echo To use Fortuna, you need Docker Desktop:
    echo https://www.docker.com/products/docker-desktop
    echo.
    echo After installing Docker, restart your computer and try again.
    echo.
    pause
    exit /b 1
)

for /f "tokens=*" %%i in ('docker --version') do set DOCKER_VERSION=%%i
echo ✓ Found: %DOCKER_VERSION%
echo.

REM ============================================================
REM STEP 2: Check if Docker daemon is running
REM ============================================================
echo [2/5] Checking if Docker daemon is running...
docker ps >nul 2>&1
if errorlevel 1 (
    echo.
    echo ✗ ERROR: Docker daemon is not running
    echo.
    echo Please:
    echo 1. Open "Docker Desktop" from your Start Menu
    echo 2. Wait 30 seconds for Docker to fully start
    echo 3. Then run this launcher again
    echo.
    pause
    exit /b 1
)
echo ✓ Docker daemon is running
echo.

REM ============================================================
REM STEP 3: Pull latest Docker image
REM ============================================================
echo [3/5] Pulling latest Fortuna image from Docker Hub...
echo (This may take a minute on first run)
echo.
docker pull masonj0/fortuna-faucet:latest
if errorlevel 1 (
    echo.
    echo ⚠ Warning: Could not pull from Docker Hub
    echo Checking for local image...
    docker image inspect masonj0/fortuna-faucet:latest >nul 2>&1
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
docker stop fortuna-faucet >nul 2>&1
docker rm fortuna-faucet >nul 2>&1

REM Create data directories if they don't exist
if not exist "data" mkdir data
if not exist "logs" mkdir logs

REM Start container with proper quoting for paths with spaces
docker run -d ^
  --name fortuna-faucet ^
  -p 8000:8000 ^
  -v "%cd%\data:/app/web_service/backend/data" ^
  -v "%cd%\logs:/app/web_service/backend/logs" ^
  masonj0/fortuna-faucet:latest

if errorlevel 1 (
    echo.
    echo ✗ ERROR: Failed to start container
    echo.
    echo Try these troubleshooting steps:
    echo 1. Open Docker Desktop
    echo 2. Wait for it to fully start
    echo 3. Open Command Prompt and run: docker ps
    echo    (This tests if Docker is working)
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
docker inspect fortuna-faucet >nul 2>&1
if errorlevel 1 (
    echo.
    echo ✗ ERROR: Container exited unexpectedly
    echo.
    echo Showing container logs for debugging:
    echo.
    docker logs fortuna-faucet
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
echo ║            🎉  FORTUNA IS RUNNING!  🎉                   ║
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

docker logs -f fortuna-faucet

REM Cleanup on exit
echo.
echo Stopping Fortuna...
docker stop fortuna-faucet >nul 2>&1
echo ✓ Fortuna stopped

exit /b 0
