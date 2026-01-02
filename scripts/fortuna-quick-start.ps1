<#
.SYNOPSIS
    Fortuna Supreme Developer Bootstrapper (v2.0)
    Aligns with CI/CD 'Champion' workflows for robust local development.

.DESCRIPTION
    - Auto-detects and kills blocking processes on ports 8000/3000
    - Validates Python/Node environments
    - Installs dependencies using fast caching strategies (npm ci)
    - Launches Backend (FastAPI) and Frontend (Next.js) in parallel

.PARAMETER Clean
    Removes build artifacts and caches (.next, __pycache__, etc.) before starting.

.PARAMETER Production
    Builds the frontend for production instead of running in dev mode.

.PARAMETER NoFrontend
    Launches only the backend API.
#>

param(
    [switch]$SkipChecks,
    [switch]$NoFrontend,
    [switch]$Production,
    [switch]$Clean,
    [switch]$Help
)

$ErrorActionPreference = "Stop"

# --- Configuration ---
$PROJECT_ROOT = Resolve-Path "$PSScriptRoot\.."
$BACKEND_DIR  = Join-Path $PROJECT_ROOT "web_service\backend"
$FRONTEND_DIR = Join-Path $PROJECT_ROOT "web_platform\frontend"
$PYTHON_CMD   = "py -3.11" # Assumes python is in PATH. Use 'py -3.11' if needed.

# --- Helper Functions ---
function Show-Step($msg) { Write-Host "`n🔵 $msg" -ForegroundColor Cyan }
function Show-Success($msg) { Write-Host "   ✅ $msg" -ForegroundColor Green }
function Show-Warn($msg) { Write-Host "   ⚠️  $msg" -ForegroundColor Yellow }
function Show-Fail($msg) { Write-Host "   ❌ $msg" -ForegroundColor Red; exit 1 }

function Clear-BuildCache {
    Show-Step "Cleaning build caches (-Clean active)..."
    $paths = @(
        (Join-Path $FRONTEND_DIR ".next"),
        (Join-Path $FRONTEND_DIR "node_modules\.cache"),
        (Join-Path $BACKEND_DIR "__pycache__"),
        (Join-Path $BACKEND_DIR "*.spec")
    )
    foreach ($p in $paths) {
        if (Test-Path $p) {
            Remove-Item -Path $p -Recurse -Force -ErrorAction SilentlyContinue
            Write-Host "   Deleted: $p" -ForegroundColor Gray
        }
    }
    Show-Success "Cache cleared."
}

function Check-Port($port, $name) {
    $process = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
    if ($process) {
        Show-Warn "Port $port ($name) is blocked by PID $process. Killing it..."
        Stop-Process -Id $process -Force
        Show-Success "Port $port freed."
    }
}

# --- Main Execution ---

Write-Host "`n🚀 FORTUNA SUPREME BOOTSTRAPPER" -ForegroundColor Magenta
Write-Host "=================================" -ForegroundColor Gray

if ($Help) { Get-Help $PSCommandPath -Detailed; exit }
if ($Clean) { Clear-BuildCache }

# 1. Pre-flight Checks
if (-not $SkipChecks) {
    Show-Step "System Health Check"
    Check-Port 8000 "Backend API"
    Check-Port 3000 "Frontend UI"
}

# 2. Backend Setup
Show-Step "Preparing Backend (Python)..."
if (-not (Test-Path $BACKEND_DIR)) { Show-Fail "Backend directory not found at: $BACKEND_DIR" }

# Check for Python
try {
    $pyVer = & $PYTHON_CMD --version 2>&1
    Show-Success "Found $pyVer"
} catch {
    Show-Fail "Python not found in PATH."
}

# Upgrade Pip & Wheel
Write-Host "   Upgrading pip/wheel..." -NoNewline
& $PYTHON_CMD -m pip install --upgrade pip wheel --quiet
Write-Host " Done." -ForegroundColor Green

# Verify Critical Imports
Write-Host "   Verifying dependencies..." -NoNewline
$testImport = & $PYTHON_CMD -c "import fastapi, uvicorn, structlog; print('OK')" 2>$null
if ($testImport -match "OK") {
    Write-Host " OK (Skipping install)" -ForegroundColor Green
} else {
    Write-Host " Missing." -ForegroundColor Yellow
    Show-Warn "Installing requirements from requirements.txt..."
    Push-Location $BACKEND_DIR
    & $PYTHON_CMD -m pip install -r requirements.txt
    Pop-Location
}

# 3. Frontend Setup
if (-not $NoFrontend) {
    Show-Step "Preparing Frontend (Node.js)..."
    if (-not (Test-Path $FRONTEND_DIR)) { Show-Fail "Frontend directory not found at: $FRONTEND_DIR" }

    Push-Location $FRONTEND_DIR

    # Smart Install (npm ci vs install)
    if (Test-Path "node_modules") {
        Show-Success "Node modules present."
    } else {
        Show-Warn "Installing dependencies (npm ci)..."
        npm ci --silent
    }

    # Production Build Logic
    if ($Production) {
        Show-Step "Building for Production..."
        npm run build
        Show-Success "Production build complete."
    }

    Pop-Location
}

# 4. Launch Sequence
Show-Step "Launching Services..."

# Launch Backend
$backendScript = "cd `"$BACKEND_DIR`"; & $PYTHON_CMD -m uvicorn main:app --reload --port 8000"
Start-Process pwsh -ArgumentList "-NoExit", "-Command", $backendScript -WindowStyle Normal
Show-Success "Backend launched on Port 8000"

# Launch Frontend
if (-not $NoFrontend) {
    $cmd = if ($Production) { "start" } else { "dev" }
    $frontendScript = "cd `"$FRONTEND_DIR`"; npm run $cmd"
    Start-Process pwsh -ArgumentList "-NoExit", "-Command", $frontendScript -WindowStyle Normal
    Show-Success "Frontend launched on Port 3000 ($cmd mode)"
}

Write-Host "`n✨ Fortuna is running! Press Ctrl+C in the popup windows to stop." -ForegroundColor Cyan