# run_backend.py
import sys
from pathlib import Path

# Add the project root to the Python path
# This is crucial for resolving imports correctly when running from the command line
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

import uvicorn
from python_service.api import create_app
from python_service.config import get_settings

if __name__ == "__main__":
    settings = get_settings()
    app = create_app(settings)

    print(f"✅ Fortuna Backend is running on http://{settings.UVICORN_HOST}:{settings.UVICORN_PORT}")

    uvicorn.run(
        app,
        host=settings.UVICORN_HOST,
        port=settings.UVICORN_PORT,
        log_level="info",
        reload=True  # Be cautious with reload in a threaded app
    )
