# Comprehensive MSI build pipeline for Fortuna Faucet
# Version 3.0 - Three-Executable Architecture

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
@("python", "npm", "heat.exe", "candle.exe", "light.exe") | ForEach-Object {
    if (-not (Get-Command $_ -ErrorAction SilentlyContinue)) {
        Write-Error "$_ not found in PATH. Please ensure it is installed and accessible."
        exit 1
    }
    Write-Success "$_ found in PATH."
}

# ==================== PHASE 2: BUILD BACKEND EXECUTABLE ====================
Write-Header "Phase 2: Building Standalone Backend"
Write-Info "Installing Python dependencies and running PyInstaller..."
# Activate venv if it exists, otherwise assume packages are globally available
if (Test-Path ".\.venv\Scripts\Activate.ps1") {
    & ".\.venv\Scripts\Activate.ps1"
}
python -m pip install -r requirements.txt
pyinstaller --onefile --name fortuna-api --add-data "python_service:python_service" python_service/api.py
Write-Success "Backend executable created at .\dist\fortuna-api"


# ==================== PHASE 3: BUILD STATIC FRONTEND ====================
Write-Header "Phase 3: Building Static Frontend"
Write-Info "Installing Node.js dependencies and running Next.js build..."
Push-Location ".\web_platform\frontend"
npm install
npm run build
Pop-Location
Write-Success "Static frontend created at .\web_platform\frontend\out"

# ==================== PHASE 4: PREPARE & HARVEST FILES ====================
Write-Header "Phase 4: Preparing & Harvesting Files for WiX"
$buildDir = ".\wix_build"
if (Test-Path $buildDir) { Remove-Item $buildDir -Recurse -Force }
New-Item -ItemType Directory -Path $buildDir -Force | Out-Null

Write-Info "Harvesting backend executable..."
& heat.exe file ".\dist\fortuna-api" -o "$buildDir\backend_files.wxs" `
    -gg -sf -srd -cg BackendFileGroup -dr INSTALLFOLDER -var "var.BackendSourceDir"

Write-Info "Harvesting frontend static files..."
& heat.exe dir ".\web_platform\frontend\out" -o "$buildDir\frontend_files.wxs" `
    -gg -sf -srd -cg FrontendFileGroup -dr INSTALLFOLDER -var "var.FrontendSourceDir"

Write-Success "File harvesting complete."

# ==================== PHASE 5: COMPILATION ====================
Write-Header "Phase 5: Compiling WiX Sources"
$objDir = "$buildDir\obj"
New-Item -ItemType Directory -Path $objDir -Force | Out-Null
Copy-Item ".\wix\*.wxs" "$buildDir"

@("$buildDir\product.wxs", "$buildDir\backend_files.wxs", "$buildDir\frontend_files.wxs") | ForEach-Object {
    Write-Info "Compiling $(Split-Path $_ -Leaf)..."
    & candle.exe $_ -o "$objDir\" `
        -ext WixUtilExtension `
        -d"BackendSourceDir=.\dist" `
        -d"FrontendSourceDir=.\web_platform\frontend\out" `
        -dVersion="$AppVersion" `
        -arch x64
    if ($LASTEXITCODE -ne 0) { throw "Compilation failed for $_" }
}
Write-Success "Compilation complete."

# ==================== PHASE 6: LINKING ====================
Write-Header "Phase 6: Linking MSI Package"
New-Item -ItemType Directory -Path $OutputPath -Force | Out-Null
$msiPath = "$OutputPath\Fortuna-Faucet-$AppVersion-x64.msi"

Write-Info "Linking objects into MSI..."
& light.exe -out $msiPath (Get-ChildItem "$objDir\*.wixobj") `
    -sw1076 `
    -ext WixUIExtension -ext WixUtilExtension `
    -cultures:en-us -b $buildDir

if ($LASTEXITCODE -ne 0) { throw "MSI linking failed" }

$fileSize = (Get-Item $msiPath).Length / 1MB
Write-Success "MSI created: $msiPath ($($fileSize.ToString('F2')) MB)"

# ==================== PHASE 7: METADATA ====================
Write-Header "Phase 7: Generating Installation Metadata"
$metadata = @{
    Version = $AppVersion
    BuildDate = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
    Configuration = $Configuration
    FileSize_MB = [math]::Round($fileSize, 2)
    SHA256 = (Get-FileHash $msiPath -Algorithm SHA256).Hash
} | ConvertTo-Json -Depth 5

$metadata | Out-File "$OutputPath\metadata.json" -Encoding UTF8
Write-Success "Metadata saved."

Write-Host ""
Write-Header "Build Complete"
Write-Success "Ready for distribution!"
Write-Info "MSI: $msiPath"
Write-Info "Metadata: $OutputPath\metadata.json"
