# Comprehensive MSI build pipeline for Fortuna Faucet

param(
    [ValidateSet("Debug", "Release")]
    [string]$Configuration = "Release",
    [string]$Version = "2.1.0",
    [string]$OutputPath = ".\dist"
)

$ErrorActionPreference = "Stop"

function Write-Header { Write-Host ("=" * 70) -ForegroundColor Cyan; Write-Host $args -ForegroundColor Cyan; Write-Host ("=" * 70) -ForegroundColor Cyan }
function Write-Success { Write-Host "✓ $args" -ForegroundColor Green }
function Write-Error { Write-Host "✗ $args" -ForegroundColor Red }
function Write-Info { Write-Host "• $args" -ForegroundColor Yellow }

# ==================== PHASE 1: PREREQUISITES ====================
Write-Header "Phase 1: Checking Prerequisites"

@("git", "python") | ForEach-Object {
    if (-not (Get-Command $_ -ErrorAction SilentlyContinue)) {
        Write-Error "$_ not found in PATH"
        exit 1
    }
    Write-Success "$_ found"
}

# ==================== PHASE 2: FILE HARVESTING ====================
Write-Header "Phase 2: Harvesting File Structure"

$buildDir = ".\wix_build"
if (Test-Path $buildDir) { Remove-Item $buildDir -Recurse -Force }
New-Item -ItemType Directory -Path $buildDir -Force | Out-Null

Write-Info "Harvesting backend files..."
& heat.exe dir ".\python_service" -o "$buildDir\backend_files.wxs" `
    -gg -sf -srd -cg BackendFileGroup -dr INSTALLFOLDER -var "var.BackendSourceDir"

Write-Info "Harvesting frontend files..."
& heat.exe dir ".\web_platform\frontend\build" -o "$buildDir\frontend_files.wxs" `
    -gg -sf -srd -cg FrontendFileGroup -dr INSTALLFOLDER -var "var.FrontendSourceDir"

Write-Success "File harvesting complete"

# ==================== PHASE 3: COMPILATION ====================
Write-Header "Phase 3: Compiling WiX Sources"

$objDir = "$buildDir\obj"
New-Item -ItemType Directory -Path $objDir -Force | Out-Null

Copy-Item ".\wix\product.wxs" "$buildDir\product.wxs"

@("$buildDir\product.wxs", "$buildDir\backend_files.wxs", "$buildDir\frontend_files.wxs") | ForEach-Object {
    Write-Info "Compiling $(Split-Path $_ -Leaf)..."
    & candle.exe $_ -o "$objDir\" `
        -d"BackendSourceDir=.\python_service" `
        -d"FrontendSourceDir=.\web_platform\frontend\build" `
        -arch x64
    if ($LASTEXITCODE -ne 0) { throw "Compilation failed" }
}

Write-Success "Compilation complete"

# ==================== PHASE 4: LINKING ====================
Write-Header "Phase 4: Linking MSI Package"

New-Item -ItemType Directory -Path $OutputPath -Force | Out-Null
$msiPath = "$OutputPath\Fortuna-Faucet-$Version-x64.msi"

Write-Info "Linking objects into MSI..."
& light.exe -out $msiPath (Get-ChildItem "$objDir\*.wixobj") `
    -ext WixUIExtension -ext WixUtilExtension `
    -cultures:en-us -b $buildDir

if ($LASTEXITCODE -ne 0) { throw "MSI linking failed" }

$fileSize = (Get-Item $msiPath).Length / 1MB
Write-Success "MSI created: $msiPath ($($fileSize.ToString('F2')) MB)"

# ==================== PHASE 5: METADATA ====================
Write-Header "Phase 5: Generating Installation Metadata"

$metadata = @{
    Version = $Version
    BuildDate = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
    Configuration = $Configuration
    FileSize_MB = [math]::Round($fileSize, 2)
    SHA256 = (Get-FileHash $msiPath -Algorithm SHA256).Hash
    Requirements = @{
        Windows = "Windows 7 SP1 or later (64-bit)"
        AdminRights = $true
        DiskSpace_GB = 2
        RAM_GB = 4
    }
} | ConvertTo-Json -Depth 5

$metadata | Out-File "$OutputPath\metadata.json" -Encoding UTF8
Write-Success "Metadata saved"

Write-Host ""
Write-Header "Build Complete"
Write-Success "Ready for distribution!"
Write-Info "MSI: $msiPath"
Write-Info "Metadata: $OutputPath\metadata.json"