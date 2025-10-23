# Download and prepare portable Python
$pythonVersion = "3.11.7"
$pythonUrl = "https://www.python.org/ftp/python/$pythonVersion/python-$pythonVersion-embed-amd64.zip"
$buildDir = ".\build"
$pythonDir = "$buildDir\python"

Write-Host "[INFO] Setting up embedded Python..." -ForegroundColor Green

# Create build directory if it doesn't exist
if (-not (Test-Path $buildDir)) {
    New-Item -ItemType Directory -Path $buildDir | Out-Null
}

# Download
if (-not (Test-Path "$buildDir\python-embed.zip")) {
    Write-Host "[DOWNLOAD] Downloading Python $pythonVersion..."
    Invoke-WebRequest -Uri $pythonUrl -OutFile "$buildDir\python-embed.zip"
}

# Extract
if (Test-Path $pythonDir) {
    Remove-Item $pythonDir -Recurse -Force
}
Expand-Archive -Path "$buildDir\python-embed.zip" -DestinationPath $pythonDir -Force

# Install pip
Write-Host "[INFO] Installing pip..."
$getpip = "$buildDir\get-pip.py"
Invoke-WebRequest -Uri "https://bootstrap.pypa.io/get-pip.py" -OutFile $getpip
& "$pythonDir\python.exe" $getpip

# Install requirements
Write-Host "[INFO] Installing Python dependencies..."
# Note: --target is used to install packages to a specific directory, which is essential for embedded/portable environments.
& "$pythonDir\Scripts\pip.exe" install --quiet -r "requirements.txt" --target "$pythonDir\Lib\site-packages"

Write-Host "[SUCCESS] Embedded Python ready at $pythonDir" -ForegroundColor Green
