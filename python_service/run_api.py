# python_service/run_api.py

import uvicorn


def main():
    # This entry point is for the packaged application
    uvicorn.run("python_service.api:app", host="127.0.0.1", port=8000, reload=False)

if __name__ == "__main__":
    main()
