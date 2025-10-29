# python_service/middleware/error_handler.py

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from ..user_friendly_errors import ERROR_MAP

class UserFriendlyException(Exception):
    def __init__(self, error_key: str, status_code: int = 500, details: str = None):
        self.error_key = error_key
        self.status_code = status_code
        self.details = details
        error_info = ERROR_MAP.get(error_key, ERROR_MAP["default"])
        self.message = error_info["message"]
        self.suggestion = error_info["suggestion"]
        super().__init__(self.message)

async def user_friendly_exception_handler(request: Request, exc: UserFriendlyException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "message": exc.message,
                "suggestion": exc.suggestion,
                "details": exc.details
            }
        },
    )

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
