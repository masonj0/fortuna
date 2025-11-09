# run_backend.py
import os
import sys
import time
from datetime import datetime

import uvicorn

# --- PyInstaller Explicit Imports ---
# These are not used directly in this script, but they are essential for
# PyInstaller's static analysis to discover and package the dynamically loaded
# adapter modules from the `python_service.adapters` directory.
from python_service.adapters import at_the_races_adapter  # noqa: F401
from python_service.adapters import betfair_adapter  # noqa: F401
from python_service.adapters import betfair_datascientist_adapter  # noqa: F401
from python_service.adapters import betfair_greyhound_adapter  # noqa: F401
from python_service.adapters import brisnet_adapter  # noqa: F401
from python_service.adapters import drf_adapter  # noqa: F401
from python_service.adapters import equibase_adapter  # noqa: F401
from python_service.adapters import fanduel_adapter  # noqa: F401
from python_service.adapters import gbgb_api_adapter  # noqa: F401
from python_service.adapters import greyhound_adapter  # noqa: F401
from python_service.adapters import harness_adapter  # noqa: F401
from python_service.adapters import horseracingnation_adapter  # noqa: F401
from python_service.adapters import nyrabets_adapter  # noqa: F401
from python_service.adapters import oddschecker_adapter  # noqa: F401
from python_service.adapters import pointsbet_greyhound_adapter  # noqa: F401
from python_service.adapters import punters_adapter  # noqa: F401
from python_service.adapters import racing_and_sports_adapter  # noqa: F401
from python_service.adapters import racing_and_sports_greyhound_adapter  # noqa: F401
from python_service.adapters import racingpost_adapter  # noqa: F401
from python_service.adapters import racingtv_adapter  # noqa: F401
from python_service.adapters import sporting_life_adapter  # noqa: F401
from python_service.adapters import tab_adapter  # noqa: F401
from python_service.adapters import template_adapter  # noqa: F401
from python_service.adapters import the_racing_api_adapter  # noqa: F401
from python_service.adapters import timeform_adapter  # noqa: F401
from python_service.adapters import tvg_adapter  # noqa: F401
from python_service.adapters import twinspires_adapter  # noqa: F401
from python_service.adapters import universal_adapter  # noqa: F401
from python_service.adapters import xpressbet_adapter  # noqa: F401
# ------------------------------------

# This script serves as the main entry point for the PyInstaller-packaged backend.
# By running from the project root, it ensures that the 'python_service'
# directory is correctly interpreted as a Python package, resolving the
# "attempted relative import with no known parent package" error.


def main():
    """
    Starts the FastAPI application using uvicorn.
    Specifies the application instance as a string to allow for the correct
    package context to be established.
    """
    # CRITICAL: Add a small delay for the Windows networking stack to initialize,
    # which can prevent socket binding errors in a bundled executable environment.
    time.sleep(1)

    # This configuration is for the packaged application, so reload is False.
    # The host is set to 0.0.0.0 for reliability in bundled contexts where 127.0.0.1 might not be immediately available.
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 8000))

    # CRITICAL DEBUG TRACE: Helps diagnose startup hangs.
    print(f"[{datetime.now().isoformat()}] INFO: Uvicorn startup sequence initiated (PID {os.getpid()})")
    print(f"[{datetime.now().isoformat()}] INFO: Attempting to bind to {host}:{port}")
    sys.stdout.flush()  # Force the line out of the buffer immediately.

    uvicorn.run("python_service.api:app", host=host, port=port, reload=False, log_level="info")


if __name__ == "__main__":
    # When PyInstaller creates the executable, this __name__ == "__main__"
    # block is the entry point.

    # It's good practice to ensure the project root is on the Python path,
    # though for a simple script like this, it's the execution context
    # that matters most.
    project_root = os.path.dirname(os.path.abspath(__file__))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

    main()
