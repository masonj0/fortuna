# python_service/run_server.py
import uvicorn
from config import get_settings
from db.init import initialize_database

def main():
    """
    Initializes the database and then starts the Uvicorn server programmatically.
    This wrapper provides a reliable way for external processes (like Electron)
    to launch the server and receive a clear success signal.
    """
    # Initialize the database before starting the server
    initialize_database()

    settings = get_settings()

    # This print statement is the crucial signal that the Electron process will wait for.
    print("Backend ready", flush=True)

    uvicorn.run(
        "api:app",
        host=settings.UVICORN_HOST,
        port=settings.UVICORN_PORT,
        reload=settings.UVICORN_RELOAD,
        log_level="info",
    )

if __name__ == "__main__":
    main()
