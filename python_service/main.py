import uvicorn
import multiprocessing

# This is the crucial import. We are grabbing the configured FastAPI app
# from your existing api.py file.
from python_service.api import app

# It's a best practice for Windows compatibility to guard the execution
# of the server in this block. PyInstaller and multiprocessing rely on it.
if __name__ == "__main__":
    # When freezing an application, the default 'spawn' start method
    # for multiprocessing is often necessary.
    multiprocessing.freeze_support()

    # Programmatically run the Uvicorn server.
    # We are telling it to run the 'app' object that we imported.
    # The host '0.0.0.0' is essential for the server to be reachable
    # within the GitHub Actions container.
    uvicorn.run(
        "python_service.api:app",
        host="0.0.0.0",
        port=8000,
        reload=False,  # Reloading is not needed in a packaged executable
        workers=1      # A single worker is standard for this setup
    )
