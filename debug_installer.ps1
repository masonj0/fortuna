# 1. Get the location of this script
$currentDir = $PSScriptRoot

# 2. Find all .msi files in this folder
$msiFiles = Get-ChildItem -Path $currentDir -Filter "*.msi"

# 3. Validate we found exactly one MSI
if ($msiFiles.Count -eq 0) {
    Write-Host "❌ Error: No MSI files found in $currentDir" -ForegroundColor Red
    Read-Host "Press Enter to exit..."
    Exit
}
if ($msiFiles.Count -gt 1) {
    Write-Host "❌ Error: Multiple MSI files found. I don't know which one to run:" -ForegroundColor Red
    $msiFiles | ForEach-Object { Write-Host " - $($_.Name)" }
    Read-Host "Press Enter to exit..."
    Exit
}

# 4. Set up file paths
$targetMsi = $msiFiles[0].FullName
$logFile = Join-Path -Path $currentDir -ChildPath "install_debug.log"

Write-Host "------------------------------------------------" -ForegroundColor Cyan
Write-Host "🚀 Target Found: $($msiFiles[0].Name)" -ForegroundColor Green
Write-Host "📝 Log File:     $logFile" -ForegroundColor Yellow
Write-Host "------------------------------------------------" -ForegroundColor Cyan

# 5. Run MSIEXEC
# /i   = Install
# /L*v = Log all information (Verbose)
try {
    Start-Process -FilePath "msiexec.exe" -ArgumentList "/i `"$targetMsi`" /L*v `"$logFile`"" -Wait
    Write-Host "✅ Installer finished." -ForegroundColor Green
}
catch {
    Write-Host "❌ Failed to launch msiexec." -ForegroundColor Red
    Write-Error $_
}

# 6. Pause so you can read the output
Read-Host "Press Enter to close this window..."
