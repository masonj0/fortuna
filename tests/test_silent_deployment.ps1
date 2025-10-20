Write-Host "Testing silent deployment..." -ForegroundColor Cyan

& msiexec.exe /i "Fortuna-Faucet-2.1.0-x64.msi" `
    /qn /l*v "silent_test.log" `
    ALLUSERS=1 INSTALLSCOPE=perMachine

if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Silent deployment successful"
} else {
    Write-Host "✗ Silent deployment failed"
    Write-Host "Log: silent_test.log"
    exit 1
}