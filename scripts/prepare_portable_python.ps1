# scripts/prepare_portable_python.ps1
# This script creates a self-contained, portable Python environment for the Electron app.

$ErrorActionPreference = "Stop"

# --- Helper Functions ---
function Write-Header {
    param([string]$title)
    Write-Host ("=" * 60) -ForegroundColor Green
    Write-Host $title -ForegroundColor Green
    Write-Host ("=" * 60) -ForegroundColor Green
}
function Write-Info {
    param([string]$message)
    Write-Host "[INFO] $message" -ForegroundColor Yellow
}
function Write-Success {
    param([string]$message)
    Write-Host "[SUCCESS] $message" -ForegroundColor Cyan
}

# --- Configuration ---
Write-Header "Step 1: Initializing Configuration"
$PythonEmbedUrl = "https://www.python.org/ftp/python/3.11.7/python-3.11.7-embed-amd64.zip"
$TempDir = ".\temp_build"
$PythonDir = ".\electron\python"
$PythonZipPath = Join-Path $TempDir "python_embed.zip"
$PythonExePath = Join-Path $PythonDir "python.exe"
$RequirementsPath = ".\requirements.txt"
Write-Success "Configuration loaded."

# --- Clean and Prepare Directories ---
Write-Header "Step 2: Preparing Directories"
if (Test-Path $PythonDir) {
    Write-Info "Removing existing portable Python directory..."
    Remove-Item $PythonDir -Recurse -Force
}
if (Test-Path $TempDir) {
    Remove-Item $TempDir -Recurse -Force
}
New-Item -ItemType Directory -Path $TempDir -Force | Out-Null
New-Item -ItemType Directory -Path $PythonDir -Force | Out-Null
Write-Success "Directories are clean and ready."

# --- Download and Extract Python ---
Write-Header "Step 3: Acquiring Embeddable Python"
Write-Info "Downloading Python from $PythonEmbedUrl..."
Invoke-WebRequest -Uri $PythonEmbedUrl -OutFile $PythonZipPath
Write-Info "Extracting Python to $PythonDir..."
Expand-Archive -Path $PythonZipPath -DestinationPath $PythonDir -Force
Write-Success "Portable Python environment created at $PythonDir"

# --- Install Dependencies ---
Write-Header "Step 4: Installing Dependencies"
Write-Info "Unpacking the base Python library..."
# The embeddable package comes with python311._pth. We need to unpack the stdlib zip file.
# First, find the name of the zip file (e.g., python311.zip)
$StdLibZip = Get-ChildItem -Path $PythonDir -Filter "python*.zip" | Select-Object -First 1
if ($StdLibZip) {
    Write-Info "Found Standard Library package: $($StdLibZip.Name)"
    Expand-Archive -Path $StdLibZip.FullName -DestinationPath (Join-Path $PythonDir "Lib") -Force
    # Remove the now-unnecessary ._pth file to enable normal module resolution
    Remove-Item (Join-Path $PythonDir "python*._pth")
    Write-Success "Standard library unpacked."
} else {
    Write-Host "[WARNING] Python standard library zip not found. This may cause issues." -ForegroundColor Yellow
}

Write-Info "Installing pip..."
& $PythonExePath -m ensurepip
$SitePackagesDir = Join-Path $PythonDir "Lib\site-packages"
Write-Info "Installing project dependencies into $SitePackagesDir..."
& $PythonExePath -m pip install --upgrade pip
& $PythonExePath -m pip install -r $RequirementsPath --target $SitePackagesDir
Write-Success "All dependencies installed."

# --- Cleanup ---
Write-Header "Step 5: Cleaning Up"
Remove-Item $TempDir -Recurse -Force
Write-Success "Temporary files removed."

Write-Header "Portable Python Environment is Ready!"
