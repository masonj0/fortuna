# python_service/adapters/mixins/headers_mixin.py
"""Mixin for generating browser-like HTTP headers."""

from typing import Optional

from ..constants import (
    CHROME_SEC_CH_UA,
    CHROME_USER_AGENT,
    DEFAULT_BROWSER_HEADERS,
)


class BrowserHeadersMixin:
    """Mixin that provides browser-like HTTP headers."""

    def _get_browser_headers(
        self,
        host: Optional[str] = None,
        referer: Optional[str] = None,
        *,
        include_sec_ch: bool = True,
    ) -> dict:
        """
        Generate browser-like headers for HTTP requests.

        Args:
            host: The Host header value
            referer: The Referer header value
            include_sec_ch: Whether to include sec-ch-ua headers

        Returns:
            Dictionary of HTTP headers
        """
        headers = {
            **DEFAULT_BROWSER_HEADERS,
            "User-Agent": CHROME_USER_AGENT,
        }

        if host:
            headers["Host"] = host

        if referer:
            headers["Referer"] = referer

        if include_sec_ch:
            headers.update({
                "sec-ch-ua": CHROME_SEC_CH_UA,
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"Windows"',
            })

        return headers
