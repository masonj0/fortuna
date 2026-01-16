# pre-build-check.ps1
Write-Host "=== FORTUNA PRE-BUILD VERIFICATION ===" -ForegroundColor Cyan

# 1. Check all required files exist
Write-Host "`n[1] Checking required files..."
$required = @(
    "web_service/backend/main.py",
    "web_service/backend/api.py",
    "web_service/backend/config.py",
    "web_service/backend/port_check.py",
    "web_service/backend/requirements.txt",
    "web_service/frontend/package.json",
    "web_service/frontend/next.config.js",
    "fortuna-monolith.spec"
)

$missing = @()
foreach ($file in $required) {
    if (Test-Path $file) {
        Write-Host "  ✅ $file"
    } else {
        Write-Host "  ❌ $file"
        $missing += $file
    }
}

if ($missing.Count -gt 0) {
    Write-Host "`n❌ FATAL: Missing files:" -ForegroundColor Red
    $missing | ForEach-Object { Write-Host "  - $_" }
    exit 1
}

# 2. Test Python imports
Write-Host "`n[2] Testing Python imports..."
$testScript = @"
import sys
sys.path.insert(0, '.')

try:
    from web_service.backend.api import app
    print('✅ api.app imported')
except ImportError as e:
    print(f'❌ Failed to import api.app: {e}')
    sys.exit(1)

try:
    from web_service.backend.config import get_settings
    settings = get_settings()
    print(f'✅ config.get_settings imported (host={settings.UVICORN_HOST}, port={settings.FORTUNA_PORT})')
except ImportError as e:
    print(f'❌ Failed to import config: {e}')
    sys.exit(1)

try:
    from web_service.backend.port_check import check_port_and_exit_if_in_use
    print('✅ port_check.check_port_and_exit_if_in_use imported')
except ImportError as e:
    print(f'❌ Failed to import port_check: {e}')
    sys.exit(1)

print('✅ All imports successful')
"@

$testScript | Out-File -FilePath "test_imports.py" -Encoding UTF8
python test_imports.py
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Import test FAILED" -ForegroundColor Red
    exit 1
}
Remove-Item "test_imports.py"

# 3. Check frontend
Write-Host "`n[3] Checking frontend..."
if (Test-Path "web_service/frontend/next.config.js") {
    $config = Get-Content "web_service/frontend/next.config.js"
    if ($config -match "output:\s*['`"]export['`"]") {
        Write-Host "  ✅ next.config.js has output: 'export'"
    } else {
        Write-Host "  ❌ next.config.js missing output: 'export'" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "  ⚠️  next.config.js will be created during build"
}

# 4. Check spec file
Write-Host "`n[4] Checking fortuna-monolith.spec..."
if (Test-Path "fortuna-monolith.spec") {
    $spec = Get-Content "fortuna-monolith.spec"
    if ($spec -match "SPECPATH") {
        Write-Host "  ✅ spec uses SPECPATH"
    } else {
        Write-Host "  ⚠️  spec doesn't use SPECPATH (may have path issues)"
    }
} else {
    Write-Host "  ❌ fortuna-monolith.spec not found" -ForegroundColor Red
    exit 1
}

Write-Host "`n✅ ALL CHECKS PASSED - Safe to build!" -ForegroundColor Green
