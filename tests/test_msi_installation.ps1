param([string]$MsiPath = ".\dist\Fortuna-Faucet-2.1.0-x64.msi")

Write-Host "Testing MSI Installation..." -ForegroundColor Cyan

# Test 1: File integrity
Write-Host "• Verifying MSI structure..."
if (Test-Path $MsiPath) {
    Write-Host "✓ MSI file exists"
} else {
    Write-Error "MSI file not found"
    exit 1
}

# Test 2: Installation
Write-Host "• Testing interactive installation..."
& msiexec.exe /i $MsiPath /l*v "test_install.log"

# Test 3: Verify installation
Write-Host "• Verifying files were installed..."
$programFiles = "$env:PROGRAMFILES\Fortuna Faucet"
if (Test-Path $programFiles) {
    Write-Host "✓ Installation successful"
} else {
    Write-Error "Installation failed"
    exit 1
}

# Test 4: Registry entries
Write-Host "• Checking registry entries..."
$regPath = "HKLM:\Software\Fortuna Faucet"
if (Test-Path $regPath) {
    Write-Host "✓ Registry entries found"
} else {
    Write-Error "Registry entries missing"
    exit 1
}