#!/bin/bash
file="web_service/backend/adapters/base_adapter_v3.py"

echo "Checking Fix #1 (import json)..."
if grep -q "^import json" "$file"; then
    echo "  ✅ Fix #1: PRESENT"
else
    echo "  ❌ Fix #1: MISSING"
fi

echo "Checking Fix #2 (init in __init__)..."
if grep -A 20 "def __init__" "$file" | grep -q "self.circuit_breaker = CircuitBreaker()"; then
    echo "  ✅ Fix #2: PRESENT"
else
    echo "  ❌ Fix #2: MISSING or in wrong location"
fi

echo "Checking Fix #3 (await calls)..."
count=$(grep -c "await self.circuit_breaker" "$file")
if [ "$count" -eq 4 ]; then
    echo "  ✅ Fix #3: PRESENT (found $count await calls)"
elif [ "$count" -gt 0 ]; then
    echo "  ⚠️  Fix #3: PARTIAL (found $count/4 await calls)"
else
    echo "  ❌ Fix #3: MISSING"
fi
