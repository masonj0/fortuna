# ====================================================================
# 🍀 FORTUNA FAUCET - SUPREME QUICK START
# ====================================================================
# "The best way to run the app without building an installer."
# ====================================================================

param(
    [switch]$SkipChecks, # Use this if you know your environment is perfect
    [switch]$NoFrontend, # Use this if you only want to test the Python API
    [switch]$Help        # Show usage information
)

$ErrorActionPreference = 'Stop'

# --- HELP MENU ---
if ($Help) {
    Clear-Host
    Write-Host "🍀 FORTUNA QUICK START - HELP" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "USAGE:" -ForegroundColor Cyan
    Write-Host "  .\fortuna-quick-start.ps1 [options]"
    Write-Host ""
    Write-Host "OPTIONS:" -ForegroundColor Cyan
    Write-Host "  -NoFrontend    Launch backend only (for API testing)"
    Write-Host "  -SkipChecks    Skip dependency validation (faster)"
    Write-Host "  -Help          Show this help message"
    Write-Host ""
    Write-Host "EXAMPLES:" -ForegroundColor Cyan
    Write-Host "  .\fortuna-quick-start.ps1                    # Full launch"
    Write-Host "  .\fortuna-quick-start.ps1 -NoFrontend        # Backend only"
    Write-Host "  .\fortuna-quick-start.ps1 -SkipChecks        # Fast mode"
    Write-Host ""
    Write-Host "FIRST TIME SETUP:" -ForegroundColor Cyan
    Write-Host "  1. python -m venv .venv"
    Write-Host "  2. .venv\Scripts\python.exe -m pip install -r web_service\backend\requirements.txt"
    Write-Host "  3. cd electron && npm install && cd .."
    Write-Host ""
    Write-Host "URLS:" -ForegroundColor Cyan
    Write-Host "  Backend API:  http://127.0.0.1:8000/docs"
    Write-Host "  Frontend UI:  http://localhost:3000"
    Write-Host ""
    exit 0
}

Clear-Host

# --- 1. CONFIGURATION (Dynamic Paths) ---
$PROJECT_ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent
$VENV_PATH    = Join-Path $PROJECT_ROOT ".venv"
$PYTHON_EXE   = Join-Path $VENV_PATH "Scripts\python.exe"
$BACKEND_DIR  = Join-Path $PROJECT_ROOT "web_service\backend"
$FRONTEND_DIR = Join-Path $PROJECT_ROOT "electron"

# --- 2. UI HELPERS ---
function Show-Header {
    Write-Host ""
    Write-Host "╔═══════════════════════════════════════════════╗" -ForegroundColor Yellow
    Write-Host "║  🍀 FORTUNA FAUCET: MISSION TO LUNCHTIME 🚀  ║" -ForegroundColor Yellow
    Write-Host "╚═══════════════════════════════════════════════╝" -ForegroundColor Yellow
    Write-Host ""
}

function Show-Step ([string]$msg) {
    Write-Host ('🔹 ' + $msg) -ForegroundColor Cyan
}

function Show-Success ([string]$msg) {
    Write-Host ('✅ ' + $msg) -ForegroundColor Green
}

function Show-Warn ([string]$msg) {
    Write-Host ('⚠️  ' + $msg) -ForegroundColor Yellow
}

function Show-Fail ([string]$msg) {
    Write-Host ""
    Write-Host ('❌ ' + $msg) -ForegroundColor Red
    Write-Host ""
    Write-Host "💡 TIP: Run with -Help flag for setup instructions" -ForegroundColor Gray
    Write-Host ""
    exit 1
}

function Show-Info ([string]$msg) {
    Write-Host ('ℹ️  ' + $msg) -ForegroundColor Gray
}

# --- 3. PORT MANAGER (The "Self-Healing" Feature) ---
function Clear-Ports {
    $ports = @(8000)
    if (-not $NoFrontend) { $ports += 3000 }

    $cleared = $false
    foreach ($port in $ports) {
        $proc = Get-NetTCPConnection -LocalPort $port -ErrorAction SilentlyContinue
        if ($proc) {
            Show-Warn "Port $port is in use. Clearing it..."
            Stop-Process -Id $proc.OwningProcess -Force -ErrorAction SilentlyContinue
            Start-Sleep -Milliseconds 500
            $cleared = $true
        }
    }

    if ($cleared) {
        Show-Success "Ports cleared successfully"
    }
}

# --- 4. HEALTH CHECKER ---
function Wait-For-Backend {
    Write-Host ""
    Write-Host "⏳ Waiting for Backend to wake up" -NoNewline -ForegroundColor Cyan
    $maxRetries = 30
    $dots = 0

    for ($i = 0; $i -lt $maxRetries; $i++) {
        try {
            $response = Invoke-WebRequest -Uri "http://127.0.0.1:8000/health" -UseBasicParsing -TimeoutSec 1 -ErrorAction Stop
            if ($response.StatusCode -eq 200) {
                Write-Host " Ready! 🎉" -ForegroundColor Green
                Write-Host ""
                return $true
            }
        } catch {
            Write-Host "." -NoNewline -ForegroundColor Gray
            $dots++
            if ($dots % 10 -eq 0) {
                Write-Host " $($dots)s" -NoNewline -ForegroundColor DarkGray
            }
            Start-Sleep -Seconds 1
        }
    }
    Write-Host ""
    Show-Fail "Backend failed to start after $maxRetries seconds.`n   Check the Python window for errors or logs."
}

# --- 5. FIRST-TIME HELPER ---
function Show-FirstTimeHelp {
    Write-Host ""
    Write-Host "╔════════════════════════════════════════════════════════╗" -ForegroundColor Yellow
    Write-Host "║  👋 LOOKS LIKE YOUR FIRST TIME!                       ║" -ForegroundColor Yellow
    Write-Host "╠════════════════════════════════════════════════════════╣" -ForegroundColor Yellow
    Write-Host "║  Quick Setup (run these commands):                     ║" -ForegroundColor White
    Write-Host "║                                                        ║" -ForegroundColor White
    Write-Host "║  1️⃣  python -m venv .venv                              ║" -ForegroundColor Cyan
    Write-Host "║  2️⃣  .venv\Scripts\python.exe -m pip install ``        ║" -ForegroundColor Cyan
    Write-Host "║       -r web_service\backend\requirements.txt          ║" -ForegroundColor Cyan
    if (-not $NoFrontend) {
        Write-Host "║  3️⃣  cd electron && npm install && cd ..              ║" -ForegroundColor Cyan
    }
    Write-Host "║                                                        ║" -ForegroundColor White
    Write-Host "║  Then run this script again!                           ║" -ForegroundColor White
    Write-Host "╚════════════════════════════════════════════════════════╝" -ForegroundColor Yellow
    Write-Host ""
}

# ====================================================================
# MAIN EXECUTION FLOW
# ====================================================================

Show-Header

# Show mode
if ($NoFrontend) {
    Show-Info "Running in Backend-Only mode"
    Write-Host ""
}

if ($SkipChecks) {
    Show-Info "Skipping pre-flight checks (fast mode)"
    Write-Host ""
}

# --- STEP 1: PRE-FLIGHT CHECKS ---
if (-not $SkipChecks) {
    Show-Step "Running Pre-flight Checks..."
    Write-Host ""

    $allGood = $true
    $missingItems = @()

    # 1. Check Python Virtual Environment
    Write-Host "   Checking Python venv..." -NoNewline
    if (-not (Test-Path $PYTHON_EXE)) {
        Write-Host " ❌ Missing" -ForegroundColor Red
        $missingItems += "Python virtual environment"
        $allGood = $false
    } else {
        Write-Host " ✅" -ForegroundColor Green
    }

    # 2. Check Python Dependencies
    if (Test-Path $PYTHON_EXE) {
        Write-Host "   Checking Python packages..." -NoNewline
        $pipList = & $PYTHON_EXE -m pip list 2>&1
        if ($pipList -notmatch "fastapi") {
            Write-Host " ⚠️  Missing dependencies" -ForegroundColor Yellow
            Show-Warn "Installing Python dependencies (this may take a minute)..."
            & $PYTHON_EXE -m pip install -q -r (Join-Path $BACKEND_DIR "requirements.txt")
            if ($LASTEXITCODE -eq 0) {
                Show-Success "Python packages installed"
            } else {
                $allGood = $false
            }
        } else {
            Write-Host " ✅" -ForegroundColor Green
        }
    }

    # 3. Check Node.js (Only if Frontend is needed)
    if (-not $NoFrontend) {
        Write-Host "   Checking Node.js..." -NoNewline
        if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
            Write-Host " ❌ Missing" -ForegroundColor Red
            $missingItems += "Node.js (download from nodejs.org)"
            $allGood = $false
        } else {
            $nodeVersion = node --version
            Write-Host " ✅ ($nodeVersion)" -ForegroundColor Green
        }

        # 4. Check Node Modules
        Write-Host "   Checking Node packages..." -NoNewline
        if (-not (Test-Path (Join-Path $FRONTEND_DIR "node_modules"))) {
            Write-Host " ⚠️  Missing dependencies" -ForegroundColor Yellow
            Show-Warn "Installing Node packages (this takes a moment)..."
            Push-Location $FRONTEND_DIR
            npm install --silent 2>&1 | Out-Null
            Pop-Location
            if ($LASTEXITCODE -eq 0) {
                Show-Success "Node packages installed"
            } else {
                $allGood = $false
            }
        } else {
            Write-Host " ✅" -ForegroundColor Green
        }
    }

    Write-Host ""

    if (-not $allGood) {
        if ($missingItems.Count -gt 0) {
            Show-FirstTimeHelp
            exit 1
        } else {
            Show-Fail "Some dependencies failed to install. Check error messages above."
        }
    }

    Show-Success "All systems go! 🚀"
    Write-Host ""
}

# --- STEP 2: CLEAR THE RUNWAY ---
Show-Step "Clearing Ports..."
Clear-Ports
Write-Host ""

# --- STEP 3: LAUNCH BACKEND (Separate Window) ---
Show-Step "Launching Backend Engine..."
$BackendScript = @"
`$Host.UI.RawUI.WindowTitle = "🍀 Fortuna Backend"
Write-Host "╔════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║    FORTUNA BACKEND - LIVE LOGS        ║" -ForegroundColor Cyan
Write-Host "╚════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""
cd '$BACKEND_DIR'
& '$PYTHON_EXE' main.py
Write-Host ""
Write-Host "Backend stopped. Press Enter to close this window..." -ForegroundColor Yellow
Read-Host
"@

$BackendProcess = Start-Process powershell -ArgumentList "-NoExit", "-Command", $BackendScript -PassThru
Show-Info "Backend window opened (PID: $($BackendProcess.Id))"

# --- STEP 4: WAIT FOR SIGNAL ---
Wait-For-Backend

# --- STEP 5: LAUNCH FRONTEND (Separate Window) ---
if (-not $NoFrontend) {
    Show-Step "Launching Frontend Interface..."
    $FrontendScript = @"
`$Host.UI.RawUI.WindowTitle = "🍀 Fortuna Frontend"
Write-Host "╔════════════════════════════════════════╗" -ForegroundColor Magenta
Write-Host "║    FORTUNA FRONTEND - LIVE LOGS       ║" -ForegroundColor Magenta
Write-Host "╚════════════════════════════════════════╝" -ForegroundColor Magenta
Write-Host ""
cd '$FRONTEND_DIR'
npm start
Write-Host ""
Write-Host "Frontend stopped. Press Enter to close this window..." -ForegroundColor Yellow
Read-Host
"@
    $FrontendProcess = Start-Process powershell -ArgumentList "-NoExit", "-Command", $FrontendScript -PassThru
    Show-Info "Frontend window opened (PID: $($FrontendProcess.Id))"
    Write-Host ""
    Show-Success "Frontend launched successfully!"
} else {
    Show-Success "Backend ready (Frontend skipped)"
}

# --- STEP 6: MISSION CONTROL ---
Write-Host ""
Write-Host "╔═══════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║              ✅ FORTUNA IS RUNNING                    ║" -ForegroundColor Green
Write-Host "╠═══════════════════════════════════════════════════════╣" -ForegroundColor Green
Write-Host "║  🔗 Backend API:   http://127.0.0.1:8000/docs         ║" -ForegroundColor White
if (-not $NoFrontend) {
    Write-Host "║  🌐 Frontend UI:   http://localhost:3000              ║" -ForegroundColor White
}
Write-Host "║                                                       ║" -ForegroundColor Green
Write-Host "║  💡 Both services are running in separate windows    ║" -ForegroundColor Gray
Write-Host "║     Keep those windows open to see live logs!        ║" -ForegroundColor Gray
Write-Host "╚═══════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""
Write-Host "Press [ENTER] to stop all services and exit..." -ForegroundColor Yellow
Write-Host ""

Read-Host

# --- STEP 7: CLEANUP ---
Write-Host ""
Show-Step "Initiating shutdown sequence..."
Write-Host ""

$shutdownSteps = @(
    "Stopping backend process",
    "Stopping frontend process",
    "Clearing ports",
    "Final cleanup"
)

foreach ($step in $shutdownSteps) {
    Write-Host "   $step..." -NoNewline -ForegroundColor Gray

    if ($step -match "backend" -and $BackendProcess) {
        Stop-Process -Id $BackendProcess.Id -Force -ErrorAction SilentlyContinue
    }
    if ($step -match "frontend" -and $FrontendProcess) {
        Stop-Process -Id $FrontendProcess.Id -Force -ErrorAction SilentlyContinue
    }
    if ($step -match "Clearing") {
        Clear-Ports
    }

    Start-Sleep -Milliseconds 300
    Write-Host " ✅" -ForegroundColor Green
}

Write-Host ""
Write-Host "╔═══════════════════════════════════════════════════════╗" -ForegroundColor Cyan
Write-Host "║           👋 SHUTDOWN COMPLETE - HAVE A NICE DAY!     ║" -ForegroundColor Cyan
Write-Host "╚═══════════════════════════════════════════════════════╝" -ForegroundColor Cyan
Write-Host ""
Start-Sleep -Seconds 1
