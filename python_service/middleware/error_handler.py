# python_service/middleware/error_handler.py

from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Convert Pydantic validation errors to user-friendly messages."""
    return JSONResponse(
        status_code=422,
        content={
            "detail": "Invalid request parameters",
            "errors": [
                {
                    "field": error["loc"][-1] if error["loc"] else "unknown",
                    "message": error["msg"],
                    "type": error["type"],
                }
                for error in exc.errors()
            ],
        },
    )
