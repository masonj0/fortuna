
import sys
sys.path.insert(0, '.')
try:
    from web_service.backend.api import app
    print(f'✅ app object loaded: {type(app).__name__}')
except Exception as e:
    print(f'❌ CRITICAL IMPORT ERROR: {e}')
    import traceback
    traceback.print_exc()
    sys.exit(1)
