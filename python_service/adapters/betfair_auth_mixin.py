# python_service/adapters/betfair_auth_mixin.py

import asyncio
from datetime import datetime
from datetime import timedelta
from typing import Optional

import httpx
import structlog

from ..credentials_manager import SecureCredentialsManager

log = structlog.get_logger(__name__)


class BetfairAuthMixin:
    """Encapsulates Betfair authentication logic for reuse across adapters."""

    session_token: Optional[str] = None
    token_expiry: Optional[datetime] = None
    _auth_lock = asyncio.Lock()

    async def _authenticate(self, http_client: httpx.AsyncClient):
        """
        Authenticates with Betfair using credentials from the system's credential manager,
        ensuring the session token is valid and refreshing it if necessary.
        """
        async with self._auth_lock:
            if self.session_token and self.token_expiry and self.token_expiry > (datetime.now() + timedelta(minutes=5)):
                return

            log.info("Attempting to authenticate with Betfair...")
            username, password = SecureCredentialsManager.get_betfair_credentials()

            if not all([self.config.BETFAIR_APP_KEY, username, password]):
                raise ValueError("Betfair credentials not fully configured in credential manager.")

            auth_url = "https://identitysso.betfair.com/api/login"
            headers = {
                "X-Application": self.config.BETFAIR_APP_KEY,
                "Content-Type": "application/x-www-form-urlencoded",
            }
            payload = f"username={username}&password={password}"

            response = await http_client.post(auth_url, headers=headers, content=payload, timeout=20)
            response.raise_for_status()
            data = response.json()

            if data.get("status") == "SUCCESS":
                self.session_token = data.get("token")
                self.token_expiry = datetime.now() + timedelta(hours=3)
                log.info("Betfair authentication successful.")
            else:
                log.error("Betfair authentication failed", error=data.get("error"))
                raise ConnectionError(f"Betfair authentication failed: {data.get('error')}")
