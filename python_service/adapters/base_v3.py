# python_service/adapters/base_v3.py
import time
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Any, List
import httpx
import structlog
from tenacity import retry, stop_after_attempt, wait_exponential, RetryError

from ..core.exceptions import AdapterHttpError
from ..models import Race

class BaseAdapterV3(ABC):
    """
    Abstract base class for all V3 data adapters.
    Enforces a standardized fetch/parse pattern and includes robust request handling.
    """

    def __init__(self, source_name: str, base_url: str, config=None, timeout: int = 20):
        self.source_name = source_name
        self.base_url = base_url
        self.config = config
        self.timeout = timeout
        self.logger = structlog.get_logger(adapter_name=self.source_name)
        self.http_client: httpx.AsyncClient = None  # Injected by the engine

        # Circuit Breaker State
        self.circuit_breaker_tripped = False
        self.circuit_breaker_failure_count = 0
        self.circuit_breaker_last_failure = 0
        self.FAILURE_THRESHOLD = 3
        self.COOLDOWN_PERIOD_SECONDS = 300  # 5 minutes

    @abstractmethod
    async def _fetch_data(self, date: str) -> Any:
        """
        Fetches the raw data (e.g., HTML, JSON) for the given date.
        This is the only method that should perform network operations.
        """
        raise NotImplementedError

    @abstractmethod
    def _parse_races(self, raw_data: Any) -> List[Race]:
        """
        Parses the raw data retrieved by _fetch_data into a list of Race objects.
        This method should be a pure function with no side effects.
        """
        raise NotImplementedError

    async def get_races(self, date: str) -> dict:
        """
        Orchestrates the fetch-then-parse pipeline for the adapter.
        This public method should not be overridden by subclasses.
        It now includes a check for manual override data.
        """
        from ..manual_override_manager import override_manager

        # Check for manual override data first
        override_content = override_manager.get_override(self.source_name)
        if override_content:
            self.logger.info("Using manual override data for fetch.", date=date)
            raw_data = override_content
        else:
            # If no override, proceed with the normal fetch.
            # Any exception here (including AdapterHttpError) will propagate
            # up to the OddsEngine to be handled.
            raw_data = await self._fetch_data(date)

        races = []
        if raw_data is not None:
            races = self._parse_races(raw_data)

        return {
            "races": races,
            "source_info": {
                "name": self.source_name,
                "status": "SUCCESS",
                "races_fetched": len(races),
                "error_message": None,
                "fetch_duration": 0,  # This will be calculated in the engine
            },
        }

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        reraise=True  # Reraise the final exception to be caught by get_races
    )
    async def make_request(
        self, http_client: httpx.AsyncClient, method: str, url: str, **kwargs
    ) -> httpx.Response:
        """
        Makes a resilient HTTP request with built-in retry logic and a circuit breaker.
        """
        if self.circuit_breaker_tripped:
            if time.time() - self.circuit_breaker_last_failure < self.COOLDOWN_PERIOD_SECONDS:
                self.logger.warning("Circuit breaker is tripped. Skipping request.")
                raise AdapterHttpError(
                    adapter_name=self.source_name,
                    status_code=503,
                    url=url,
                    detail="Circuit breaker is tripped"
                )
            else:
                self.logger.info("Circuit breaker cooldown expired. Attempting to reset.")
                self.circuit_breaker_tripped = False
                self.circuit_breaker_failure_count = 0

        full_url = url if url.startswith('http') else f"{self.base_url.rstrip('/')}/{url.lstrip('/')}"

        try:
            self.logger.info("Making request", method=method.upper(), url=full_url)
            response = await http_client.request(method, full_url, timeout=self.timeout, **kwargs)
            response.raise_for_status()
            self.circuit_breaker_failure_count = 0  # Reset on success
            return response
        except (httpx.RequestError, RetryError) as e:
            self.circuit_breaker_failure_count += 1
            self.circuit_breaker_last_failure = time.time()
            if self.circuit_breaker_failure_count >= self.FAILURE_THRESHOLD:
                self.circuit_breaker_tripped = True
                self.logger.error("Circuit breaker tripped due to repeated failures.")

            self.logger.error("Request Error or Retry Error", error=str(e))
            raise AdapterHttpError(
                adapter_name=self.source_name,
                status_code=503,  # Service Unavailable
                url=full_url,
                detail=str(e)
            ) from e

    def get_status(self) -> dict:
        """
        Returns a dictionary representing the adapter's current status.
        Subclasses can extend this to include more specific health checks.
        """
        return {
            "adapter_name": self.source_name,
            "status": "OK"  # Basic status; can be enhanced in subclasses
        }
