# python_service/adapters/mixins/betfair_auth_mixin.py
"""Betfair authentication mixin with improved error handling."""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, Tuple

import httpx
import structlog

from ...credentials_manager import SecureCredentialsManager
from ...core.exceptions import AuthenticationError

log = structlog.get_logger(__name__)


class BetfairAuthMixin:
    """Encapsulates Betfair authentication logic for reuse across adapters."""

    session_token: Optional[str] = None
    token_expiry: Optional[datetime] = None
    _auth_lock: asyncio.Lock = None

    # Configuration
    AUTH_URL = "https://identitysso.betfair.com/api/login"
    TOKEN_VALIDITY_HOURS = 3
    TOKEN_REFRESH_BUFFER_MINUTES = 5

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        cls._auth_lock = asyncio.Lock()

    @property
    def _is_token_valid(self) -> bool:
        """Check if current token is still valid with buffer time."""
        if not self.session_token or not self.token_expiry:
            return False
        buffer = timedelta(minutes=self.TOKEN_REFRESH_BUFFER_MINUTES)
        return self.token_expiry > (datetime.now() + buffer)

    async def _authenticate(self, http_client: httpx.AsyncClient) -> bool:
        """
        Authenticates with Betfair using credentials from the system's credential manager.

        Returns:
            True if authentication succeeded, False otherwise

        Raises:
            AuthenticationError: If credentials are missing
        """
        async with self._auth_lock:
            if self._is_token_valid:
                return True

            log.info("Attempting to authenticate with Betfair...")

            try:
                username, password = SecureCredentialsManager.get_betfair_credentials()
            except Exception as e:
                log.error("Failed to retrieve Betfair credentials", error=str(e))
                raise AuthenticationError("Betfair", "Credentials not available") from e

            app_key = getattr(self.config, "BETFAIR_APP_KEY", None)
            if not all([app_key, username, password]):
                raise AuthenticationError(
                    "Betfair",
                    "Incomplete credentials: app_key, username, or password missing"
                )

            headers = {
                "X-Application": app_key,
                "Content-Type": "application/x-www-form-urlencoded",
            }
            payload = f"username={username}&password={password}"

            try:
                response = await http_client.post(
                    self.AUTH_URL, headers=headers, content=payload, timeout=20
                )
                response.raise_for_status()
                data = response.json()

                if data.get("status") == "SUCCESS":
                    self.session_token = data.get("token")
                    self.token_expiry = datetime.now() + timedelta(
                        hours=self.TOKEN_VALIDITY_HOURS
                    )
                    log.info("Betfair authentication successful.")
                    return True
                else:
                    log.error("Betfair authentication failed", error=data.get("error"))
                    self.session_token = None
                    self.token_expiry = None
                    return False

            except httpx.HTTPError as e:
                log.error("Betfair authentication HTTP error", error=str(e))
                self.session_token = None
                self.token_expiry = None
                return False

    def _get_authenticated_headers(self) -> dict:
        """Get headers with authentication token for API requests."""
        if not self.session_token:
            raise AuthenticationError("Betfair", "No valid session token")

        return {
            "X-Application": getattr(self.config, "BETFAIR_APP_KEY", ""),
            "X-Authentication": self.session_token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
