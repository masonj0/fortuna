#!/bin/bash

echo -e "\e[36m=== FORTUNA PRE-BUILD VERIFICATION ===\e[0m"

# 1. Check all required files exist
echo -e "\n\e[1m[1] Checking required files...\e[0m"
required_files=(
    "web_service/backend/main.py"
    "web_service/backend/api.py"
    "web_service/backend/config.py"
    "web_service/backend/port_check.py"
    "web_service/backend/requirements.txt"
    "web_service/frontend/package.json"
    "web_service/frontend/next.config.js"
    "fortuna-monolith.spec"
)

missing_files=()
all_found=true
for file in "${required_files[@]}"; do
    if [ -f "$file" ]; then
        echo -e "  \e[32m✅ $file\e[0m"
    else
        echo -e "  \e[31m❌ $file\e[0m"
        missing_files+=("$file")
        all_found=false
    fi
done

if [ "$all_found" = false ]; then
    echo -e "\n\e[31m❌ FATAL: Missing files:\e[0m"
    for file in "${missing_files[@]}"; do
        echo "  - $file"
    done
    exit 1
fi

# 2. Test Python imports
echo -e "\n\e[1m[2] Testing Python imports...\e[0m"
cat > test_imports.py << EOL
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
EOL

python test_imports.py
if [ $? -ne 0 ]; then
    echo -e "\e[31m❌ Import test FAILED\e[0m"
    rm test_imports.py
    exit 1
fi
rm test_imports.py

# 3. Check frontend
echo -e "\n\e[1m[3] Checking frontend...\e[0m"
if [ -f "web_service/frontend/next.config.js" ]; then
    if grep -q "output: 'export'" "web_service/frontend/next.config.js"; then
        echo -e "  \e[32m✅ next.config.js has output: 'export'\e[0m"
    else
        echo -e "  \e[31m❌ next.config.js missing output: 'export'\e[0m"
        exit 1
    fi
else
    echo -e "  \e[33m⚠️  next.config.js will be created during build\e[0m"
fi

# 4. Check spec file
echo -e "\n\e[1m[4] Checking fortuna-monolith.spec...\e[0m"
if [ -f "fortuna-monolith.spec" ]; then
    if grep -q "SPECPATH" "fortuna-monolith.spec"; then
        echo -e "  \e[32m✅ spec uses SPECPATH\e[0m"
    else
        echo -e "  \e[33m⚠️  spec doesn't use SPECPATH (may have path issues)\e[0m"
    fi
else
    echo -e "  \e[31m❌ fortuna-monolith.spec not found\e[0m"
    exit 1
fi

echo -e "\n\e[32m✅ ALL CHECKS PASSED - Safe to build!\e[0m"
