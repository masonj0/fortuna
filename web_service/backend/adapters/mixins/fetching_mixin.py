import asyncio
import random
from typing import Any, Dict, List, Optional

from ...core.smart_fetcher import GlobalResourceManager

class RacePageFetcherMixin:
    """Mixin for concurrent fetching of individual race pages."""

    async def _fetch_race_pages_concurrent(
        self,
        metadata: List[Dict[str, Any]],
        headers: Dict[str, str],
        semaphore_limit: int = 5,
        delay_range: tuple[float, float] = (0.5, 1.5)
    ) -> List[Dict[str, Any]]:
        """Fetch multiple race pages in parallel with controlled concurrency and delays."""
        # Using a local semaphore combined with the global one if possible
        local_sem = asyncio.Semaphore(semaphore_limit)

        async def fetch_single(item):
            url = item.get("url")
            if not url:
                return None

            async with local_sem:
                # Add a small random jitter to appear more human
                await asyncio.sleep(delay_range[0] + random.random() * (delay_range[1] - delay_range[0]))

                try:
                    if hasattr(self, 'logger'):
                        self.logger.debug("fetching_race_page", url=url)

                    # Call make_request from the BaseAdapterV3
                    resp = await self.make_request("GET", url, headers=headers)

                    if resp and hasattr(resp, "text") and resp.text:
                        if hasattr(self, 'logger'):
                            self.logger.debug("fetched_race_page", url=url, status=getattr(resp, 'status', 'unknown'))
                        return {**item, "html": resp.text}
                except Exception as e:
                    if hasattr(self, 'logger'):
                        self.logger.error("failed_fetching_race_page", url=url, error=str(e))
                return None

        tasks = [fetch_single(m) for m in metadata]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return [r for r in results if not isinstance(r, Exception) and r is not None]
