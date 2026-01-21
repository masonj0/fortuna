# python_service/adapters/base_v3.py
from abc import ABC
from abc import abstractmethod
from typing import Any
from typing import List

import httpx
import structlog
from tenacity import RetryError
from tenacity import retry
from tenacity import stop_after_attempt
from tenacity import wait_exponential

from ..core.exceptions import AdapterHttpError
from ..manual_override_manager import ManualOverrideManager
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
        self.manual_override_manager: ManualOverrideManager = None
        self.supports_manual_override = True  # Can be overridden by subclasses

    def enable_manual_override(self, manager: ManualOverrideManager):
        """Injects the manual override manager into the adapter."""
        self.manual_override_manager = manager

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

    async def get_races(self, date: str) -> List[Race]:
        """
        Orchestrates the fetch-then-parse pipeline for the adapter.
        This public method should not be overridden by subclasses.
        """
        raw_data = None

        if self.manual_override_manager:
            lookup_key = f"{self.base_url}/racecards/{date}"
            manual_data = self.manual_override_manager.get_manual_data(self.source_name, lookup_key)
            if manual_data:
                self.logger.info("Using manually submitted data for request", url=lookup_key)
                raw_data = {"pages": [manual_data[0]], "date": date}

        if raw_data is None:
            try:
                raw_data = await self._fetch_data(date)
            except AdapterHttpError as e:
                if self.manual_override_manager and self.supports_manual_override:
                    self.manual_override_manager.register_failure(self.source_name, e.url)
                raise

        if raw_data is not None:
            return self._parse_races(raw_data)

        return []

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        reraise=True,  # Reraise the final exception to be caught by get_races
    )
    async def make_request(self, http_client: httpx.AsyncClient, method: str, url: str, **kwargs) -> httpx.Response:
        """
        Makes a resilient HTTP request with built-in retry logic using tenacity.
        """
        # Ensure the URL is correctly formed, whether it's relative or absolute
        full_url = url if url.startswith("http") else f"{self.base_url.rstrip('/')}/{url.lstrip('/')}"

        # Ensure headers are present and add a standard User-Agent to mimic a browser
        headers = kwargs.get("headers", {})
        if "User-Agent" not in headers:
            headers["User-Agent"] = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/107.0.0.0 Safari/537.36"
            )
        kwargs["headers"] = headers

        try:
            self.logger.info("Making request", method=method.upper(), url=full_url)
            response = await http_client.request(method, full_url, timeout=self.timeout, **kwargs)
            response.raise_for_status()  # Raise an exception for 4xx/5xx responses
            return response
        except httpx.HTTPStatusError as e:
            self.logger.error(
                "HTTP Status Error during request",
                status_code=e.response.status_code,
                url=str(e.request.url),
            )
            raise AdapterHttpError(
                adapter_name=self.source_name,
                status_code=e.response.status_code,
                url=str(e.request.url),
            ) from e
        except (httpx.RequestError, RetryError) as e:
            self.logger.error("Request Error or Retry Error", error=str(e))
            raise AdapterHttpError(
                adapter_name=self.source_name,
                status_code=503,  # Service Unavailable
                url=full_url,
            ) from e

    def get_status(self) -> dict:
        """
        Returns a dictionary representing the adapter's current status.
        Subclasses can extend this to include more specific health checks.
        """
        return {
            "adapter_name": self.source_name,
            "status": "OK",  # Basic status; can be enhanced in subclasses
        }
