# ====================================================================
# 🍀 FORTUNA FAUCET - SUPREME QUICK START
# ====================================================================
# "The best way to run the app without building an installer."
# ====================================================================

param(
    [switch]$SkipChecks, # Use this if you know your environment is perfect
    [switch]$NoFrontend  # Use this if you only want to test the Python API
)

$ErrorActionPreference = 'Stop'
Clear-Host

# --- 1. CONFIGURATION (Dynamic Paths) ---
$PROJECT_ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
# Adjust these if your folder structure changes
$VENV_PATH    = Join-Path $PROJECT_ROOT ".venv"
$PYTHON_EXE   = Join-Path $VENV_PATH "Scripts\python.exe"
$BACKEND_DIR  = Join-Path $PROJECT_ROOT "web_service\backend"
$FRONTEND_DIR = Join-Path $PROJECT_ROOT "electron"

# --- 2. UI HELPERS ---
function Show-Header {
    Write-Host "===============================================" -ForegroundColor Yellow
    Write-Host "   FORTUNA FAUCET: MISSION TO LUNCHTIME 🚀     " -ForegroundColor Yellow
    Write-Host "===============================================" -ForegroundColor Yellow
}
function Show-Step ([string]$msg) { Write-Host "`n🔹 $msg" -ForegroundColor Cyan }
function Show-Success ([string]$msg) { Write-Host "✅ $msg" -ForegroundColor Green }
function Show-Warn ([string]$msg) { Write-Host "⚠️  $msg" -ForegroundColor Yellow }
function Show-Fail ([string]$msg) { Write-Host "❌ $msg" -ForegroundColor Red; exit 1 }

# --- 3. PORT MANAGER (The "Self-Healing" Feature) ---
function Clear-Ports {
    $ports = @(8000)
    if (-not $NoFrontend) { $ports += 3000 }

    foreach ($port in $ports) {
        $proc = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
        if ($proc) {
            Show-Warn "Port $port is in use. Clearing it..."
            Stop-Process -Id $proc.OwningProcess -Force -ErrorAction SilentlyContinue
        }
    }
}

# --- 4. HEALTH CHECKER ---
function Wait-For-Backend {
    Write-Host "   Waiting for Backend to wake up..." -NoNewline -ForegroundColor Gray
    $maxRetries = 30
    for ($i = 0; $i -lt $maxRetries; $i++) {
        try {
            $response = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -UseBasicParsing -TimeoutSec 1 -ErrorAction Stop
            if ($response.StatusCode -eq 200) {
                Write-Host " Connected!" -ForegroundColor Green
                return $true
            }
        } catch {
            Write-Host "." -NoNewline -ForegroundColor Gray
            Start-Sleep -Seconds 1
        }
    }
    Show-Fail "Backend failed to start after $maxRetries seconds. Check the Python window for errors."
}

# ====================================================================
# MAIN EXECUTION FLOW
# ====================================================================

Show-Header

# --- STEP 1: PRE-FLIGHT CHECKS ---
if (-not $SkipChecks) {
    Show-Step "Checking Systems..."

    # 1. Check Python Virtual Environment
    if (-not (Test-Path $PYTHON_EXE)) {
        Show-Fail "Python Virtual Environment not found!`n   Run: python -m venv .venv"
    }

    # 2. Check Python Dependencies
    $pipList = & $PYTHON_EXE -m pip list 2>&1
    if ($pipList -notmatch "fastapi") {
        Show-Warn "Python dependencies missing. Installing..."
        & $PYTHON_EXE -m pip install -r (Join-Path $BACKEND_DIR "requirements.txt")
    }

    # 3. Check Node.js (Only if Frontend is needed)
    if (-not $NoFrontend) {
        if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
            Show-Fail "Node.js is missing! Install it from nodejs.org"
        }
        # 4. Check Node Modules
        if (-not (Test-Path (Join-Path $FRONTEND_DIR "node_modules"))) {
            Show-Warn "Node modules missing. Installing (this takes a moment)..."
            Push-Location $FRONTEND_DIR
            npm install --quiet
            Pop-Location
        }
    }
    Show-Success "Systems Go."
}

# --- STEP 2: CLEAR THE RUNWAY ---
Show-Step "Clearing Ports..."
Clear-Ports

# --- STEP 3: LAUNCH BACKEND (Separate Window) ---
Show-Step "Launching Backend Engine..."
$BackendScript = "cd '$BACKEND_DIR'; & '$PYTHON_EXE' main.py; Read-Host 'Backend Stopped. Press Enter to close.'"
# Start in new window so user can see logs
$BackendProcess = Start-Process powershell -ArgumentList "-NoExit", "-Command", "$BackendScript" -PassThru

# --- STEP 4: WAIT FOR SIGNAL ---
Wait-For-Backend

# --- STEP 5: LAUNCH FRONTEND (Separate Window) ---
if (-not $NoFrontend) {
    Show-Step "Launching Frontend Interface..."
    $FrontendScript = "cd '$FRONTEND_DIR'; npm start"
    $FrontendProcess = Start-Process powershell -ArgumentList "-NoExit", "-Command", "$FrontendScript" -PassThru
    Show-Success "Frontend Launched!"
} else {
    Show-Success "Backend Ready (Frontend skipped)"
}

# --- STEP 6: MISSION CONTROL ---
Write-Host "`n===============================================" -ForegroundColor Green
Write-Host "   ✅ FORTUNA IS RUNNING" -ForegroundColor Green
Write-Host "   Backend:  http://127.0.0.1:8000/docs" -ForegroundColor Gray
if (-not $NoFrontend) {
    Write-Host "   Frontend: http://localhost:3000" -ForegroundColor Gray
}
Write-Host "===============================================" -ForegroundColor Green
Write-Host "`nPress [ENTER] to stop all services and exit..." -ForegroundColor Yellow

Read-Host

# --- STEP 7: CLEANUP ---
Show-Step "Shutting down..."

if ($BackendProcess) {
    Stop-Process -Id $BackendProcess.Id -Force -ErrorAction SilentlyContinue
}
if ($FrontendProcess) {
    Stop-Process -Id $FrontendProcess.Id -Force -ErrorAction SilentlyContinue
}

# Double tap ports just to be sure
Clear-Ports

Show-Success "Shutdown Complete. Have a nice day!"
Start-Sleep -Seconds 1
