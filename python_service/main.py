import uvicorn
import multiprocessing

if __name__ == "__main__":
    # Guard for Windows compatibility
    multiprocessing.freeze_support()

    # Now that the sys.path is fixed in the spec file, this string
    # will work correctly in both development and the packaged .exe.
    uvicorn.run(
        "python_service.api:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        workers=1
    )
