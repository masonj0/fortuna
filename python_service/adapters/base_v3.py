# python_service/adapters/base_v3.py
import time
import json
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Any, List
import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential, RetryError
from ..core.exceptions import AdapterHttpError
from ..models import Race

class BaseAdapterV3(ABC):
    """
    A self-contained, architecturally superior abstract base class for data adapters.
    It includes retry logic, a circuit breaker, and a standardized fetch/parse pattern.
    """
    # Circuit Breaker settings
    FAILURE_THRESHOLD = 3
    COOLDOWN_PERIOD_SECONDS = 300  # 5 minutes

    def __init__(self, source_name: str, base_url: str, config=None, timeout: int = 20):
        self.source_name = source_name
        self.base_url = base_url
        self.config = config
        self.timeout = timeout
        self.logger = structlog.get_logger(adapter_name=self.source_name)
        self.http_client: httpx.AsyncClient = None # To be assigned by the engine

        # Circuit Breaker State
        self.circuit_breaker_tripped = False
        self.circuit_breaker_failure_count = 0
        self.circuit_breaker_last_failure = 0

        # New: Manual override support
        self.manual_override_manager = None
        self.supports_manual_override = False  # Override in subclasses

    @abstractmethod
    async def _fetch_data(self, date: str) -> Any:
        """Fetches the raw data (e.g., HTML, JSON) for the given date."""
        raise NotImplementedError

    @abstractmethod
    def _parse_races(self, raw_data: Any) -> List[Race]:
        """Parses the raw data into a list of Race objects."""
        raise NotImplementedError

    async def get_races(self, date: str) -> AsyncGenerator[Race, None]:
        """Orchestrates the fetch and parse process with circuit breaker logic."""
        if self.circuit_breaker_tripped:
            if time.time() - self.circuit_breaker_last_failure < self.COOLDOWN_PERIOD_SECONDS:
                self.logger.warning("Circuit breaker is tripped. Skipping fetch.")
                return
            else:
                self._reset_circuit_breaker()

        try:
            raw_data = await self._fetch_data(date)
            if raw_data is not None:
                parsed_races = self._parse_races(raw_data)
                for race in parsed_races:
                    yield race
            self._reset_circuit_breaker() # Success
        except Exception:
            self.logger.error("get_races pipeline failed.", exc_info=True)
            self._handle_failure()

    @retry(wait=wait_exponential(multiplier=1, min=2, max=10), stop=stop_after_attempt(3))
    async def make_request(
        self, http_client: httpx.AsyncClient, method: str, url: str, **kwargs
    ) -> httpx.Response:
        """Makes an HTTP request with built-in retry logic."""
        full_url = f"{self.base_url.rstrip('/')}/{url.lstrip('/')}"
        try:
            self.logger.info(f"Making request: {method.upper()} {full_url}")
            response = await http_client.request(method, full_url, timeout=self.timeout, **kwargs)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            raise AdapterHttpError(self.source_name, e.response.status_code, str(e.request.url)) from e
        except (httpx.RequestError, RetryError) as e:
            raise AdapterHttpError(self.source_name, 503, str(e)) from e

    def get_status(self) -> dict:
        return {
            "adapter_name": self.source_name,
            "circuit_breaker_tripped": self.circuit_breaker_tripped,
            "failure_count": self.circuit_breaker_failure_count,
            "last_failure": datetime.fromtimestamp(self.circuit_breaker_last_failure).isoformat() if self.circuit_breaker_last_failure else None,
        }

    def _handle_failure(self):
        self.circuit_breaker_failure_count += 1
        self.circuit_breaker_last_failure = time.time()
        if self.circuit_breaker_failure_count >= self.FAILURE_THRESHOLD:
            self.circuit_breaker_tripped = True
            self.logger.critical("Circuit breaker has been tripped.")

    def _reset_circuit_breaker(self):
        if self.circuit_breaker_tripped:
            self.logger.info("Cooldown period passed. Resetting circuit breaker.")
        self.circuit_breaker_tripped = False
        self.circuit_breaker_failure_count = 0

    def enable_manual_override(self, manager):
        """Enable manual override for this adapter"""
        self.manual_override_manager = manager
        self.supports_manual_override = True

    async def make_request_with_override(
        self,
        http_client,
        method: str,
        url: str,
        date: str,
        **kwargs
    ):
        """
        Enhanced make_request that supports manual override fallback.

        If the request fails with a 403 or similar bot-blocking error,
        it registers a manual override request and returns None, allowing
        the fetch to continue with other sources.
        """
        full_url = url if url.startswith('http') else f"{self.base_url}{url}"

        try:
            # Try normal automated fetch first
            response = await self.make_request(http_client, method, url, **kwargs)
            return response

        except Exception as e:
            # Check if this is a bot-blocking error
            if self._is_bot_blocking_error(e):
                if self.supports_manual_override and self.manual_override_manager:
                    # Register for manual override
                    request_id = self.manual_override_manager.register_failed_fetch(
                        adapter_name=self.source_name,
                        url=full_url,
                        date=date,
                        error=e
                    )

                    self.logger.warning(
                        "Automated fetch failed - manual override registered",
                        adapter=self.source_name,
                        request_id=request_id,
                        url=full_url
                    )

                    # Check if manual data already provided
                    manual_data = self.manual_override_manager.get_completed_data(request_id)
                    if manual_data:
                        # Return a mock response with manual data
                        return self._create_mock_response(manual_data)

                return None
            else:
                # Not a bot-blocking error, re-raise
                raise

    def _is_bot_blocking_error(self, error: Exception) -> bool:
        """Determine if an error is likely due to bot blocking"""
        error_str = str(error).lower()
        blocking_indicators = [
            "403",
            "forbidden",
            "cloudflare",
            "captcha",
            "access denied",
            "bot",
            "automated"
        ]
        return any(indicator in error_str for indicator in blocking_indicators)

    def _create_mock_response(self, content: str):
        """Create a mock response object from manual content"""
        class MockResponse:
            def __init__(self, text_content):
                self.text = text_content
                self.status_code = 200

            def json(self):
                return json.loads(self.text)

        return MockResponse(content)
