# Comprehensive MSI build pipeline for Fortuna Faucet
# Version 2.0 - ASCII-safe and dynamically versioned.

param(
    [ValidateSet("Debug", "Release")]
    [string]$Configuration = "Release",
    [string]$Version = "0.0.0", # This will be overridden by VERSION.txt in the script
    [string]$OutputPath = ".\dist"
)

$ErrorActionPreference = "Stop"

# --- ASCII-Safe Helper Functions ---
function Write-Header {
    $title = $args[0]
    Write-Host ("=" * 70) -ForegroundColor Cyan
    Write-Host $title -ForegroundColor Cyan
    Write-Host ("=" * 70) -ForegroundColor Cyan
}
function Write-Success { Write-Host "[SUCCESS] $($args[0])" -ForegroundColor Green }
function Write-Error { Write-Host "[ERROR] $($args[0])" -ForegroundColor Red }
function Write-Info { Write-Host "[INFO] $($args[0])" -ForegroundColor Yellow }

# ==================== PHASE 0: DYNAMIC CONFIGURATION ====================
Write-Header "Phase 0: Loading Dynamic Configuration"
$AppVersion = (Get-Content -Path ".\VERSION.txt" -Raw).Trim()
Write-Success "Application version loaded from VERSION.txt: $AppVersion"

# ==================== PHASE 1: PREREQUISITES ====================
Write-Header "Phase 1: Checking Prerequisites"

# This script assumes it's running in an environment where WiX and other tools are in the PATH.
# The GitHub Actions workflow handles this setup.
@("git", "python", "heat.exe", "candle.exe", "light.exe") | ForEach-Object {
    if (-not (Get-Command $_ -ErrorAction SilentlyContinue)) {
        Write-Error "$_ not found in PATH. Please ensure it is installed and accessible."
        exit 1
    }
    Write-Success "$_ found in PATH."
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
& heat.exe dir ".\web_platform\frontend\out" -o "$buildDir\frontend_files.wxs" `
    -gg -sf -srd -cg FrontendFileGroup -dr INSTALLFOLDER -var "var.FrontendSourceDir"

Write-Info "Harvesting Python environment files..."
& heat.exe dir ".\.venv" -o "$buildDir\venv_files.wxs" `
    -gg -sf -srd -cg VenvFileGroup -dr INSTALLFOLDER -var "var.VenvSourceDir"

Write-Success "File harvesting complete."

# ==================== PHASE 3: COMPILATION ====================
Write-Header "Phase 3: Compiling WiX Sources"
$objDir = "$buildDir\obj"
New-Item -ItemType Directory -Path $objDir -Force | Out-Null
Copy-Item ".\wix\product.wxs" "$buildDir\product.wxs"

@("$buildDir\product.wxs", "$buildDir\backend_files.wxs", "$buildDir\frontend_files.wxs", "$buildDir\venv_files.wxs") | ForEach-Object {
    Write-Info "Compiling $(Split-Path $_ -Leaf)..."
    & candle.exe $_ -o "$objDir\" `
        -ext WixUtilExtension `
        -d"BackendSourceDir=.\python_service" `
        -d"FrontendSourceDir=.\web_platform\frontend\out" `
        -d"VenvSourceDir=.\.venv" `
        -dVersion="$AppVersion.0" `
        -arch x64
    if ($LASTEXITCODE -ne 0) { throw "Compilation failed for $_" }
}
Write-Success "Compilation complete."

# ==================== PHASE 4: LINKING ====================
Write-Header "Phase 4: Linking MSI Package"
New-Item -ItemType Directory -Path $OutputPath -Force | Out-Null
$msiPath = "$OutputPath\Fortuna-Faucet-$AppVersion-x64.msi"

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
    Version = $AppVersion
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
Write-Success "Metadata saved."

Write-Host ""
Write-Header "Build Complete"
Write-Success "Ready for distribution!"
Write-Info "MSI: $msiPath"
Write-Info "Metadata: $OutputPath\metadata.json"
