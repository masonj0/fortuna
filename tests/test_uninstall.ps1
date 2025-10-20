Write-Host "Testing uninstall..." -ForegroundColor Cyan

$regPath = 'HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*'
$product = Get-ItemProperty $regPath | Where-Object { $_.DisplayName -like '*Fortuna*' }

if ($product) {
    & msiexec.exe /x $product.PSChildName /qn /l*v "uninstall_test.log"

    Start-Sleep -Seconds 2

    $programFiles = "$env:PROGRAMFILES\Fortuna Faucet"
    if (-not (Test-Path $programFiles)) {
        Write-Host "✓ Uninstall successful"
    } else {
        Write-Host "✗ Uninstall incomplete"
        exit 1
    }
} else {
    Write-Host "✗ Product not found in registry"
    exit 1
}