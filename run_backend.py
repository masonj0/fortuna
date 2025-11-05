# run_backend.py
import uvicorn
import sys
import os
import python_service.api  # Explicit import for PyInstaller's analysis

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
    # This configuration is for the packaged application, so reload is False.
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(
        "python_service.api:app",
        host=host,
        port=port,
        reload=False,
        log_level="info"
    )

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
