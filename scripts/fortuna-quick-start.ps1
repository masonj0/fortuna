# ====================================================================
# Fortuna Faucet - Quick Start Script (No Installation Required)
# ====================================================================
# This script runs Fortuna directly from source without any MSI
# Useful for development and testing before packaging
# ====================================================================

param(
    [switch]$SkipChecks,
    [switch]$NoFrontend
)

$ErrorActionPreference = 'Stop'
$OriginalLocation = Get-Location

# ============= CONFIGURATION =============
$PROJECT_ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
$VENV_PATH = Join-Path $PROJECT_ROOT ".venv"
$PYTHON_EXE = Join-Path $VENV_PATH "Scripts\python.exe"
$BACKEND_DIR = Join-Path $PROJECT_ROOT "python_service"
$FRONTEND_DIR = Join-Path $PROJECT_ROOT "web_platform\frontend"
$BACKEND_PORT = 8000
$FRONTEND_PORT = 3000

# ============= HELPER FUNCTIONS =============

function Write-Status {
    param([string]$Message, [string]$Status = "INFO")
    $Color = switch ($Status) {
        "OK"      { "Green" }
        "ERROR"   { "Red" }
        "WARNING" { "Yellow" }
        default   { "Cyan" }
    }
    Write-Host "[$Status] $Message" -ForegroundColor $Color
}

function Test-CommandExists {
    param([string]$Command)
    try {
        Get-Command $Command -ErrorAction Stop | Out-Null
        return $true
    } catch {
        return $false
    }
}

function Test-PortAvailable {
    param([int]$Port)
    try {
        $Listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Any, $Port)
        $Listener.Start()
        $Listener.Stop()
        return $true
    } catch {
        return $false
    }
}

function Stop-ProcessOnPort {
    param([int]$Port)
    $Connection = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
    if ($Connection) {
        $ProcessId = $Connection.OwningProcess
        Write-Status "Killing process $ProcessId on port $Port" "WARNING"
        Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    }
}

function Wait-ForBackend {
    param([int]$MaxAttempts = 30)

    Write-Status "Waiting for backend to start (http://127.0.0.1:$BACKEND_PORT/health)..."

    for ($i = 1; $i -le $MaxAttempts; $i++) {
        try {
            $Response = Invoke-WebRequest -Uri "http://127.0.0.1:$BACKEND_PORT/health" -UseBasicParsing -TimeoutSec 2
            if ($Response.StatusCode -eq 200) {
                Write-Status "Backend is healthy!" "OK"
                return $true
            }
        } catch {
            Write-Host "." -NoNewline
            Start-Sleep -Seconds 1
        }
    }

    Write-Status "Backend failed to start after $MaxAttempts seconds" "ERROR"
    return $false
}

# ============= PREFLIGHT CHECKS =============

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host " Fortuna Faucet - Quick Start" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

if (-not $SkipChecks) {
    Write-Status "Running preflight checks..."

    # Check Python
    if (-not (Test-Path $PYTHON_EXE)) {
        Write-Status "Python virtual environment not found at $VENV_PATH" "ERROR"
        Write-Status "Please run setup script first or create venv manually" "ERROR"
        exit 1
    }
    Write-Status "Python venv found" "OK"

    # Check Node.js
    if (-not (Test-CommandExists "node")) {
        Write-Status "Node.js not found in PATH" "ERROR"
        Write-Status "Install from: https://nodejs.org/" "ERROR"
        exit 1
    }
    Write-Status "Node.js found: $(node --version)" "OK"

    # Check npm
    if (-not (Test-CommandExists "npm")) {
        Write-Status "npm not found" "ERROR"
        exit 1
    }
    Write-Status "npm found: $(npm --version)" "OK"

    # Check if ports are available
    if (-not (Test-PortAvailable $BACKEND_PORT)) {
        Write-Status "Port $BACKEND_PORT is already in use" "WARNING"
        Stop-ProcessOnPort $BACKEND_PORT
    }

    if (-not $NoFrontend -and -not (Test-PortAvailable $FRONTEND_PORT)) {
        Write-Status "Port $FRONTEND_PORT is already in use" "WARNING"
        Stop-ProcessOnPort $FRONTEND_PORT
    }

    # Check Python dependencies
    Write-Status "Checking Python dependencies..."
    $PipList = & $PYTHON_EXE -m pip list
    if ($PipList -notmatch "fastapi") {
        Write-Status "Python dependencies not installed" "WARNING"
        Write-Status "Installing dependencies..."
        & $PYTHON_EXE -m pip install -r (Join-Path $BACKEND_DIR "requirements.txt")
    } else {
        Write-Status "Python dependencies OK" "OK"
    }

    # Check Node dependencies
    if (-not $NoFrontend) {
        Write-Status "Checking Node.js dependencies..."
        $NodeModules = Join-Path $FRONTEND_DIR "node_modules"
        if (-not (Test-Path $NodeModules)) {
            Write-Status "Node.js dependencies not installed" "WARNING"
            Write-Status "Installing dependencies..."
            Push-Location $FRONTEND_DIR
            npm install
            Pop-Location
        } else {
            Write-Status "Node.js dependencies OK" "OK"
        }
    }

    Write-Host ""
}

# ============= LAUNCH BACKEND =============

Write-Status "Starting backend server..."

$BackendJob = Start-Job -ScriptBlock {
    param($PythonExe, $BackendDir)
    Set-Location $BackendDir
    & $PythonExe -m uvicorn api:app --host 127.0.0.1 --port 8000 --reload
} -ArgumentList $PYTHON_EXE, $BACKEND_DIR

Write-Status "Backend job started (ID: $($BackendJob.Id))"

# Wait for backend to be healthy
if (-not (Wait-ForBackend)) {
    Write-Status "Backend startup failed. Checking logs..." "ERROR"
    Receive-Job $BackendJob
    Stop-Job $BackendJob
    Remove-Job $BackendJob
    exit 1
}

# ============= LAUNCH FRONTEND =============

if (-not $NoFrontend) {
    Write-Status "Starting frontend dev server..."

    $FrontendJob = Start-Job -ScriptBlock {
        param($FrontendDir)
        Set-Location $FrontendDir
        npm run dev
    } -ArgumentList $FRONTEND_DIR

    Write-Status "Frontend job started (ID: $($FrontendJob.Id))"

    # Wait a bit for frontend to start
    Start-Sleep -Seconds 5

    Write-Status "Opening browser..." "OK"
    Start-Process "http://localhost:$FRONTEND_PORT"
}

# ============= MONITORING =============

Write-Host "`n========================================" -ForegroundColor Green
Write-Host " Fortuna is now running!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Status "Backend:  http://127.0.0.1:$BACKEND_PORT" "OK"
if (-not $NoFrontend) {
    Write-Status "Frontend: http://127.0.0.1:$FRONTEND_PORT" "OK"
}
Write-Host ""
Write-Host "Press Ctrl+C to stop all services" -ForegroundColor Yellow
Write-Host ""

try {
    while ($true) {
        Start-Sleep -Seconds 2

        # Check if jobs are still running
        if ($BackendJob.State -eq "Failed" -or $BackendJob.State -eq "Stopped") {
            Write-Status "Backend has stopped unexpectedly!" "ERROR"
            Receive-Job $BackendJob
            break
        }

        if (-not $NoFrontend -and ($FrontendJob.State -eq "Failed" -or $FrontendJob.State -eq "Stopped")) {
            Write-Status "Frontend has stopped unexpectedly!" "ERROR"
            Receive-Job $FrontendJob
            break
        }
    }
} finally {
    # ============= CLEANUP =============
    Write-Host "`n`nShutting down..." -ForegroundColor Yellow

    if ($BackendJob) {
        Write-Status "Stopping backend..."
        Stop-Job $BackendJob -ErrorAction SilentlyContinue
        Remove-Job $BackendJob -Force -ErrorAction SilentlyContinue
    }

    if ($FrontendJob) {
        Write-Status "Stopping frontend..."
        Stop-Job $FrontendJob -ErrorAction SilentlyContinue
        Remove-Job $FrontendJob -Force -ErrorAction SilentlyContinue
    }

    # Kill any remaining processes on the ports
    Stop-ProcessOnPort $BACKEND_PORT
    if (-not $NoFrontend) {
        Stop-ProcessOnPort $FRONTEND_PORT
    }

    Set-Location $OriginalLocation
    Write-Status "Cleanup complete" "OK"
}

# ============= USAGE EXAMPLES =============
<#
.SYNOPSIS
Quick start script for Fortuna Faucet (no installation required)

.DESCRIPTION
Launches the backend and frontend servers directly from source code
Useful for development and testing before creating an MSI installer

.PARAMETER SkipChecks
Skip all preflight dependency checks (faster startup)

.PARAMETER NoFrontend
Only start the backend API server (no UI)

.EXAMPLE
.\fortuna-quick-start.ps1
Starts both backend and frontend with full checks

.EXAMPLE
.\fortuna-quick-start.ps1 -NoFrontend
Starts only the backend API (useful for API testing)

.EXAMPLE
.\fortuna-quick-start.ps1 -SkipChecks
Fast startup (assumes all dependencies are already installed)
#>