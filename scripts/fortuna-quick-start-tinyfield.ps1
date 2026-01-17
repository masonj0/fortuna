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
    [string]$PythonExecutable
)

$ErrorActionPreference = "Stop"

# --- Configuration ---
$PROJECT_ROOT = Resolve-Path "$PSScriptRoot\.."
$BACKEND_DIR  = Join-Path $PROJECT_ROOT "web_service\backend"
$FRONTEND_DIR = Join-Path $PROJECT_ROOT "web_service\frontend" # CORRECTED PATH
$PYTHON_CMD   = if ($PythonExecutable) { $PythonExecutable } else { "py -3.11" }

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
            try {
                Remove-Item -Path $p -Recurse -Force
                Write-Host "   Deleted: $p" -ForegroundColor Gray
            } catch {
                Show-Warn "Could not delete '$p'. It might be locked. Error: $($_.Exception.Message)"
            }
        }
    }
    Show-Success "Cache cleared."
}

function Check-Port($port, $name) {
    $process = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
    if ($process) {
        Show-Warn "Port $port ($name) is blocked by PID $process. Giving 2s grace period before termination..."
        Start-Sleep -Seconds 2
        Stop-Process -Id $process -Force -ErrorAction SilentlyContinue
        Show-Success "Port $port freed."
    }
}

# --- Main Execution ---

Write-Host "`n🚀 FORTUNA SUPREME BOOTSTRAPPER (TinyField Edition)" -ForegroundColor Magenta
Write-Host "=================================================" -ForegroundColor Gray

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

try {
    & $PYTHON_CMD --version
    Show-Success "Python executable found."
} catch {
    Show-Fail "Python not found in PATH or specified executable is invalid."
}

Write-Host "   Upgrading pip/wheel..." -NoNewline
& $PYTHON_CMD -m pip install --upgrade pip wheel --quiet
Write-Host " Done." -ForegroundColor Green

Show-Warn "   Installing/verifying Python dependencies from requirements.txt..."
Push-Location $BACKEND_DIR
& $PYTHON_CMD -m pip install -r requirements.txt
Pop-Location

# 3. Frontend Setup
if (-not $NoFrontend) {
    Show-Step "Preparing Frontend (Node.js)..."
    if (-not (Test-Path $FRONTEND_DIR)) { Show-Fail "Frontend directory not found at: $FRONTEND_DIR" }

    Push-Location $FRONTEND_DIR
    if (Test-Path "node_modules") {
        Show-Success "Node modules present."
    } else {
        Show-Warn "Installing dependencies (npm ci)..."
        npm ci --silent
    }
    if ($Production) {
        Show-Step "Building for Production..."
        npm run build
        Show-Success "Production build complete."
    }
    Pop-Location
}

# 4. Launch Sequence
Show-Step "Launching Services..."

if ($env:CI) {
    Show-Warn "CI environment detected. Using Start-Job for backend..."
    $job = Start-Job -ScriptBlock {
        param($path, $cmd)
        Set-Location $path
        # In CI, we want logs to go to stdout for capture
        & $cmd -m uvicorn main:app --port 8000 --host 0.0.0.0
    } -ArgumentList $BACKEND_DIR, $PYTHON_CMD
    Show-Success "Backend job started (Job ID: $($job.Id))"

    # Health check with improved logging and standardized endpoint
    $healthCheckUrl = "http://localhost:8000/api/health"
    Write-Host "   Pinging backend health endpoint ($healthCheckUrl)..."
    Start-Sleep -Seconds 2 # Initial grace period
    $timeout = 45
    $start = Get-Date
    $healthy = $false
    while ((Get-Date) -lt $start.AddSeconds($timeout)) {
        try {
            $response = Invoke-WebRequest -Uri $healthCheckUrl -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -eq 200) {
                Show-Success "Backend is healthy and responding."
                $healthy = $true
                break
            }
        } catch {
            Write-Host "   ... ping failed. Error: $($_.Exception.Message)"
        }
        Start-Sleep -Seconds 1
    }

    if (-not $healthy) {
        Show-Fail "Backend did not start within the $timeout-second timeout."
        Receive-Job $job # Display any output from the failed job
        Stop-Job $job
        exit 1
    }

} else {
    # -- LOCAL DEVELOPMENT (Existing Logic) --
    $backendScript = "cd `"$BACKEND_DIR`"; & $PYTHON_CMD -m uvicorn main:app --reload --port 8000"
    Start-Process pwsh -ArgumentList "-NoExit", "-Command", $backendScript -WindowStyle Normal
    Show-Success "Backend launched on Port 8000"
}

if (-not $NoFrontend) {
    if ($env:CI) {
        # In CI, we assume backend serves static files from build. Frontend npm dev server not needed.
        Show-Warn "Frontend dev server launch is skipped in CI mode."
    } else {
        $cmd = if ($Production) { "start" } else { "dev" }
        $frontendScript = "cd `"$FRONTEND_DIR`"; npm run $cmd"
        Start-Process pwsh -ArgumentList "-NoExit", "-Command", $frontendScript -WindowStyle Normal
        Show-Success "Frontend launched on Port 3000 ($cmd mode)"
    }
}

if ($env:CI) {
    Write-Host "`n✨ CI run complete. Exiting." -ForegroundColor Cyan
} else {
    Write-Host "`n✨ Fortuna is running! Press Ctrl+C in the popup windows to stop." -ForegroundColor Cyan
}
