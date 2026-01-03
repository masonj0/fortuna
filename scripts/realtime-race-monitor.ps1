<#
.SYNOPSIS
    Fortuna Real-Time Race Monitor (v1.0)
    Builds, launches, and queries the backend service to provide live racecard comparisons.
#>

$ErrorActionPreference = "Stop"

# --- Configuration ---
$PYTHON_VERSION = "3.11"
$BACKEND_DIR    = "web_service/backend"
$SPEC_FILE      = "fortuna-unified.spec"
$SERVICE_PORT   = 8102
$API_KEY        = "a_secure_test_api_key_that_is_long_enough" # Mock key for local execution

# --- Helper Functions ---
function Show-Step($msg) { Write-Host "`n🚀 $msg" -ForegroundColor Cyan }
function Show-Success($msg) { Write-Host "   ✅ $msg" -ForegroundColor Green }
function Show-Warn($msg) { Write-Host "   ⚠️  $msg" -ForegroundColor Yellow }
function Show-Fail($msg) { Write-Host "   ❌ $msg" -ForegroundColor Red; exit 1 }

# --- Main Execution ---
try {
    # 1. Environment Setup & Dependency Installation
    Show-Step "Preparing environment..."
    try {
        $pyVer = & python --version 2>&1
        if ($pyVer -notmatch $PYTHON_VERSION) {
            Show-Warn "Python version mismatch. Expected $($PYTHON_VERSION), found $($pyVer)."
        }
        Show-Success "Found Python: $pyVer"
    } catch {
        Show-Fail "Python not found. Please ensure Python $($PYTHON_VERSION) is in your PATH."
    }

    Show-Step "Installing dependencies..."
    try {
        python -m pip install --upgrade pip --quiet
        pip install -r "$($BACKEND_DIR)/requirements.txt"
        pip install pyinstaller==6.6.0
        Show-Success "All Python dependencies are installed."
    } catch {
        Show-Fail "Failed to install dependencies. Check logs for details."
    }


    # 2. Build the Backend Executable
    Show-Step "Building backend executable with PyInstaller..."

    # Clean previous builds
    if (Test-Path "dist") { Remove-Item -Recurse -Force "dist" }
    if (Test-Path "build") { Remove-Item -Recurse -Force "build" }

    # PyInstaller requires these directories to exist at build time
    New-Item -ItemType Directory -Path "$($BACKEND_DIR)/data", "$($BACKEND_DIR)/json", "$($BACKEND_DIR)/logs" -Force | Out-Null

    try {
        pyinstaller --noconfirm --clean $SPEC_FILE
        Show-Success "Backend executable built successfully."
    } catch {
        Show-Fail "PyInstaller build failed. See output for details."
    }

    # 3. Launch the Backend Service
    Show-Step "Launching backend service..."
    $exePath = Resolve-Path "dist/fortuna-webservice/fortuna-webservice.exe"
    if (-not (Test-Path $exePath)) {
        Show-Fail "Could not find the built executable at $($exePath)."
    }

    # The executable needs its runtime directories in its own folder
    $exeDir = Split-Path $exePath -Parent
    New-Item -ItemType Directory -Path "$($exeDir)/data", "$($exeDir)/json", "$($exeDir)/logs" -Force | Out-Null
    Show-Success "Created runtime directories in $($exeDir)."

    # Start the process in the background
    $process = Start-Process -FilePath $exePath -WindowStyle Hidden -PassThru
    $Global:BackendProcessId = $process.Id # Store PID for cleanup
    Show-Success "Backend service is starting in the background (PID: $($Global:BackendProcessId))."


    # 4. Health Check & API Query
    Show-Step "Waiting for service to become healthy..."
    $healthUrl = "http://localhost:$($SERVICE_PORT)/health"
    $maxRetries = 20
    $retryDelay = 3 # seconds

    for ($i = 0; $i -lt $maxRetries; $i++) {
        try {
            $response = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing
            if ($response.StatusCode -eq 200) {
                Show-Success "Service is healthy and responding."
                break
            }
        } catch {
            Write-Host "   ... waiting ($($i+1)/$($maxRetries))"
            Start-Sleep -Seconds $retryDelay
        }
        if ($i -eq $maxRetries - 1) {
            Show-Fail "Service failed to start within the timeout period."
        }
    }

    Show-Step "Querying API for live race data..."
    $racesUrl = "http://localhost:$($SERVICE_PORT)/api/races"
    $headers = @{ "X-API-Key" = $API_KEY }
    try {
        $apiResponse = Invoke-RestMethod -Uri $racesUrl -Headers $headers -Method Get
        Show-Success "Successfully fetched data for $($apiResponse.races.Count) races."
    } catch {
        Show-Fail "Failed to query the API. Error: $($_.Exception.Message)"
    }


    # 5. Process and Format Data
    Show-Step "Formatting race comparison..."
    $now = [datetime]::UtcNow
    $upcomingRaces = $apiResponse.races | Where-Object { [datetime]$_.startTime -gt $now } | Sort-Object startTime | Select-Object -First 3

    $output = @()
    $output += "--- Fortuna Real-Time Race Monitor ---"
    $output += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss UTC')"
    $output += "========================================"

    foreach ($race in $upcomingRaces) {
        $raceTime = [datetime]$race.startTime
        $timeToPost = New-TimeSpan -Start $now -End $raceTime
        $output += ""
        $output += "$($race.venue) - Race $($race.race_number) ($($raceTime.ToLocalTime().ToString('h:mm tt')))"
        $output += "Starts in: $($timeToPost.Minutes)m $($timeToPost.Seconds)s"
        $output += "----------------------------------------"
        $output += "{0,-25} {1,-15} {2,-15}" -f "Runner", "Best Odds", "Source"
        $output += "{0,-25} {1,-15} {2,-15}" -f "-----", "---------", "------"

        foreach ($runner in $race.runners) {
            $bestOdds = $null
            $bestSource = "N/A"
            if ($runner.odds) {
                $oddsValues = $runner.odds.psobject.Properties | ForEach-Object { $_.Value }
                if($oddsValues) {
                    $best = $oddsValues | Sort-Object win -Descending | Select-Object -First 1
                    if($best -and $best.win){
                        $bestOdds = $best.win
                        $bestSource = $best.source
                    }
                }
            }
            $output += "{0,-25} {1,-15} {2,-15}" -f $runner.name, $bestOdds, $bestSource
        }
    }

    $output += "========================================"

    # Display the formatted output in the console
    $output | Out-Host

} finally {
    # 6. Cleanup
    Show-Step "Cleaning up..."
    if ($Global:BackendProcessId) {
        try {
            Stop-Process -Id $Global:BackendProcessId -Force
            Show-Success "Backend service (PID: $($Global:BackendProcessId)) stopped."
        } catch {
            Show-Warn "Could not stop backend service (PID: $($Global:BackendProcessId)). It may have already exited."
        }
    } else {
        Show-Success "No backend process to stop."
    }
}
