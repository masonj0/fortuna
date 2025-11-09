import uvicorn
import multiprocessing

if __name__ == "__main__":
    # Guard for Windows compatibility
    multiprocessing.freeze_support()

    # The pathex change in the .spec file ensures that the Python interpreter
    # can find the 'python_service' package. Therefore, this string is now
    # correct for both local development and the packaged executable.
    uvicorn.run(
        "python_service.api:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        workers=1
    )