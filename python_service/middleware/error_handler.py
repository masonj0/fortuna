from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
import httpx
import logging

logger = logging.getLogger(__name__)

# A dictionary mapping exception types to user-friendly messages and appropriate HTTP status codes
EXCEPTION_MAP = {
    httpx.ConnectError: ("Could not connect to an external data service. Please check your internet connection and firewall settings.", 503),
    httpx.ReadTimeout: ("A data source is not responding in time. This is usually a temporary issue. Please try again in a few minutes.", 504),
    httpx.HTTPStatusError: ("An external data service returned an error. The service may be temporarily down or experiencing issues.", 502),
    KeyError: ("A required data field was missing from a data source, causing a processing error.", 500),
    ValueError: ("Received invalid or unexpected data from a data source.", 500),
}

class UserFriendlyErrorMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            logger.error(f"Caught exception: {type(exc).__name__}: {exc}", exc_info=True)

            # Default error message
            message, status_code = "An unexpected internal error occurred. Please check the logs for details.", 500

            # Find the most specific matching exception in our map
            for exc_type, (msg, code) in EXCEPTION_MAP.items():
                if isinstance(exc, exc_type):
                    message, status_code = msg, code
                    break

            return JSONResponse(
                status_code=status_code,
                content={"detail": message}
            )
