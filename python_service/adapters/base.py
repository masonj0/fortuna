# python_service/adapters/base.py
import threading
import time

import httpx
import structlog
from tenacity import AsyncRetrying
from tenacity import stop_after_attempt
from tenacity import wait_exponential

from ..core.exceptions import AdapterAuthError
from ..core.exceptions import AdapterConnectionError
from ..core.exceptions import AdapterHttpError
from ..core.exceptions import AdapterRateLimitError
from ..core.exceptions import AdapterRequestError
from ..core.exceptions import AdapterTimeoutError


class BaseAdapter:
    """
    The consolidated, unified base class for all data adapters.

    This class provides a standard interface and robust error handling for all adapters.
    It includes:
    - Tenacity-based request retries with exponential backoff.
    - A thread-safe circuit breaker to prevent hammering failing services.
    - Standardized error handling that raises specific custom exceptions.
    """

    def __init__(self, source_name: str, base_url: str = "", config: dict = None):
        self.source_name = source_name
        self.base_url = base_url
        self.config = config or {}
        self.logger = structlog.get_logger(self.__class__.__name__)
        self._breaker_lock = threading.Lock()
        self.retryer = AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=2, max=10)
        )
        # Circuit Breaker State
        self.circuit_breaker_tripped = False
        self.circuit_breaker_failure_count = 0
        self.circuit_breaker_last_failure = 0
        self.FAILURE_THRESHOLD = 3
        self.COOLDOWN_PERIOD_SECONDS = 300  # 5 minutes

    async def make_request(
        self, http_client: httpx.AsyncClient, method: str, url: str, **kwargs
    ) -> httpx.Response:
        """
        Makes an HTTP request with retries, circuit breaker logic, and standardized error handling.

        Args:
            http_client: An httpx.AsyncClient instance.
            method: The HTTP method (e.g., "GET", "POST").
            url: The URL endpoint.
            **kwargs: Additional arguments for httpx.request.

        Returns:
            An httpx.Response object on success.

        Raises:
            AdapterHttpError: For 4xx/5xx responses.
            AdapterTimeoutError: For request timeouts.
            AdapterConnectionError: For connection-level errors.
            AdapterRequestError: For other httpx request errors or a tripped circuit breaker.
        """
        with self._breaker_lock:
            if self.circuit_breaker_tripped:
                if time.time() - self.circuit_breaker_last_failure > self.COOLDOWN_PERIOD_SECONDS:
                    self.logger.info("Circuit breaker cooldown expired. Attempting to reset.")
                    self.circuit_breaker_tripped = False
                    self.circuit_breaker_failure_count = 0
                else:
                    self.logger.warning("Circuit breaker is tripped. Skipping request.")
                    raise AdapterRequestError(self.source_name, "Circuit breaker is tripped")

        full_url = url if url.startswith('http') else f"{self.base_url}{url}"

        async def _make_request():
            response = await http_client.request(method, full_url, **kwargs)
            response.raise_for_status()
            return response

        try:
            async for attempt in self.retryer:
                with attempt:
                    response = await _make_request()
                    # On success, reset the circuit breaker failure count
                    with self._breaker_lock:
                        if self.circuit_breaker_failure_count > 0:
                            self.logger.info("Request successful. Resetting circuit breaker failure count.")
                            self.circuit_breaker_failure_count = 0
                    return response
        except httpx.TimeoutException as e:
            self._handle_failure()
            self.logger.error("request_timeout", url=full_url, error=str(e))
            raise AdapterTimeoutError(self.source_name, f"Request timed out for {full_url}") from e
        except httpx.ConnectError as e:
            self._handle_failure()
            self.logger.error("request_connection_error", url=full_url, error=str(e))
            raise AdapterConnectionError(self.source_name, f"Connection failed for {full_url}") from e
        except httpx.HTTPStatusError as e:
            self._handle_failure()
            status = e.response.status_code
            self.logger.error("http_status_error", status_code=status, url=full_url)
            if status in [401, 403]:
                raise AdapterAuthError(self.source_name, status, full_url) from e
            if status == 429:
                raise AdapterRateLimitError(self.source_name, status, full_url) from e
            raise AdapterHttpError(self.source_name, status, full_url) from e
        except httpx.RequestError as e:
            self._handle_failure()
            self.logger.error("request_error", url=full_url, error=str(e))
            raise AdapterRequestError(self.source_name, f"An unexpected request error occurred for {full_url}") from e

    def _handle_failure(self):
        """Manages the circuit breaker state on any request failure."""
        with self._breaker_lock:
            self.circuit_breaker_failure_count += 1
            self.circuit_breaker_last_failure = time.time()
            if self.circuit_breaker_failure_count >= self.FAILURE_THRESHOLD:
                if not self.circuit_breaker_tripped:
                    self.circuit_breaker_tripped = True
                    self.logger.critical("Circuit breaker tripped due to repeated failures.")
