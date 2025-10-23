param (
    [string][Parameter(Mandatory=$true)] $InstallPath
)

function Write-Log {
    param ([string]$Message)
    # This log file is temporary and will be rolled back if the installation fails.
    # Its primary purpose is for debugging the installer itself.
    Add-Content -Path "$env:TEMP\fortuna_validation.log" -Value "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - $Message"
}

try {
    Write-Log "--- Starting Installation Validation ---"
    Write-Log "Install Path: $InstallPath"

    $pythonExe = Join-Path $InstallPath "python\python.exe"
    Write-Log "Python Executable Path: $pythonExe"

    if (-not (Test-Path $pythonExe)) {
        Write-Log "[ERROR] python.exe not found at the expected location."
        # The script must exit with a non-zero code to trigger the MSI rollback.
        exit 1
    }

    Write-Log "Python executable found. Testing execution..."

    # Attempt to execute python.exe --version
    $process = Start-Process -FilePath $pythonExe -ArgumentList "--version" -Wait -PassThru -NoNewWindow

    if ($process.ExitCode -ne 0) {
        Write-Log "[ERROR] python.exe failed to execute correctly. Exit Code: $($process.ExitCode)"
        exit 1
    }

    Write-Log "Python execution successful. Validation passed."
    Write-Log "--- Validation Complete ---"

    # Exit with 0 for success
    exit 0
}
catch {
    Write-Log "[FATAL] An unexpected error occurred during validation: $_"
    # Exit with a non-zero code to signal failure to the installer
    exit 1
}
