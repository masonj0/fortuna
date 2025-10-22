# scripts/validate_installation.ps1
param (
    [string]$InstallPath
)

$ErrorActionPreference = "Stop"

function Write-Log {
    param([string]$Message)
    $LogMessage = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - $Message"
    Add-Content -Path (Join-Path $env:TEMP "fortuna-validation.log") -Value $LogMessage
}

Write-Log "--- Starting Post-Installation Validation ---"
Write-Log "Installation Path: $InstallPath"

# 1. Verify Python Executable Exists
$PythonExePath = Join-Path $InstallPath "python\python.exe"
Write-Log "Checking for Python at: $PythonExePath"
if (-not (Test-Path $PythonExePath)) {
    Write-Log "[FAIL] python.exe not found."
    exit 1603 # A fatal error code for MSI
}
Write-Log "[OK] python.exe found."

# 2. Verify Key Library (uvicorn) can be imported
$SitePackagesPath = Join-Path $InstallPath "python\Lib\site-packages"
Write-Log "Attempting to import 'uvicorn' from site-packages..."
try {
    # We execute python.exe and pass a command to it.
    # The PYTHONPATH environment variable tells Python where to look for modules.
    $Result = & $PythonExePath -c "import uvicorn; print('uvicorn imported successfully')" 2>&1

    if ($Result -like "*uvicorn imported successfully*") {
        Write-Log "[OK] 'uvicorn' import successful."
    } else {
        Write-Log "[FAIL] Failed to import 'uvicorn'. Output: $Result"
        exit 1603
    }
} catch {
    Write-Log "[FAIL] An exception occurred while trying to import 'uvicorn'."
    Write-Log $_.Exception.ToString()
    exit 1603
}

Write-Log "--- Validation Successful ---"
exit 0
