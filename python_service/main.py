import uvicorn
import multiprocessing
import sys

# This is the standard, canonical way to check if the code is running
# as a packaged executable via PyInstaller.
# The 'sys.frozen' attribute is set to True by the PyInstaller bootloader.
IS_FROZEN = getattr(sys, 'frozen', False)

if __name__ == "__main__":
    # Guard for Windows compatibility
    multiprocessing.freeze_support()

    if IS_FROZEN:
        # In a packaged app, PyInstaller flattens the structure.
        # 'api.py' is at the root, so we import from the 'api' module.
        app_string = "api:app"
    else:
        # In a development environment, we run from the project root,
        # so we need the full package path.
        app_string = "python_service.api:app"

    # Programmatically run the Uvicorn server with the correct app string.
    uvicorn.run(
        app_string,
        host="0.0.0.0",
        port=8000,
        reload=False,
        workers=1
    )
