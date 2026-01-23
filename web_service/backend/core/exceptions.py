# python_service/core/exceptions.py
"""
Custom, application-specific exceptions for the Fortuna Faucet service.

This module defines a hierarchy of exception classes to provide standardized
error handling, particularly for the data adapter layer. Using these specific
exceptions instead of generic ones allows for more precise error handling and
clearer logging throughout the application.
"""


class FortunaException(Exception):
    """Base class for all custom exceptions in this application."""

    pass


class AdapterError(FortunaException):
    """Base class for all adapter-related errors."""

    def __init__(self, adapter_name: str, message: str):
        self.adapter_name = adapter_name
        super().__init__(f"[{adapter_name}] {message}")


class AdapterRequestError(AdapterError):
    """Raised for general network or request-related issues."""

    pass


class AdapterHttpError(AdapterRequestError):
    """Raised for unsuccessful HTTP responses (e.g., 4xx or 5xx status codes)."""

    def __init__(
        self,
        adapter_name: str,
        status_code: int,
        url: str,
        message: str | None = None,
        response_body: str | None = None,
        request_method: str | None = None,
    ):
        self.status_code = status_code
        self.url = url
        self.response_body = response_body
        self.request_method = request_method

        final_message = message or f"Received HTTP {status_code} from {url}"
        super().__init__(adapter_name, final_message)


class AdapterAuthError(AdapterHttpError):
    """Raised specifically for HTTP 401/403 errors, indicating an auth failure."""

    pass


class AdapterRateLimitError(AdapterHttpError):
    """Raised specifically for HTTP 429 errors, indicating a rate limit has been hit."""

    pass


class AdapterTimeoutError(AdapterRequestError):
    """Raised when a request to an external API times out."""

    pass


class AdapterConnectionError(AdapterRequestError):
    """Raised for DNS lookup failures or refused connections."""

    pass


class AdapterConfigError(AdapterError):
    """Raised when an adapter is missing necessary configuration (e.g., an API key)."""

    pass


class AdapterParsingError(AdapterError):
    """Raised when an adapter fails to parse the response from an API."""

    pass
