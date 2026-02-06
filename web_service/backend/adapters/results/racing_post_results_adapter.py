from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import re
from selectolax.parser import HTMLParser

from ..base_adapter_v3 import BaseAdapterV3
from ..mixins import BrowserHeadersMixin, DebugMixin, RacePageFetcherMixin
from ...models import ResultRace, ResultRunner
from ...utils.text import normalize_venue_name, clean_text
from ...core.smart_fetcher import FetchStrategy, BrowserEngine


class RacingPostResultsAdapter(BrowserHeadersMixin, DebugMixin, RacePageFetcherMixin, BaseAdapterV3):
    """Adapter for Racing Post UK/IRE results."""

    SOURCE_NAME = "RacingPostResults"
    BASE_URL = "https://www.racingpost.com"

    def __init__(self, **kwargs):
        super().__init__(
            source_name=self.SOURCE_NAME,
            base_url=self.BASE_URL,
            **kwargs
        )

    def _configure_fetch_strategy(self) -> FetchStrategy:
        return FetchStrategy(primary_engine=BrowserEngine.HTTPX, enable_js=False)

    def _get_headers(self) -> dict:
        return self._get_browser_headers(host="www.racingpost.com")

    async def _fetch_data(self, date_str: str) -> Optional[Dict[str, Any]]:
        url = f"/results/{date_str}"
        resp = await self.make_request("GET", url, headers=self._get_headers())
        if not resp:
            return None

        parser = HTMLParser(resp.text)

        # Find individual race result links
        links = []
        for a in parser.css("a[href*='/results/']"):
            href = a.attributes.get("href", "")
            if re.search(r"/results/\d+/", href):
                links.append(href)

        if not links:
            self.logger.warning("No result links found", date=date_str)
            return None

        unique_links = list(set(links))
        self.logger.info("Found result links", count=len(unique_links))

        metadata = [{"url": link, "race_number": 0} for link in unique_links]
        pages = await self._fetch_race_pages_concurrent(metadata, self._get_headers())

        return {"pages": pages, "date": date_str}

    def _parse_races(self, raw_data: Any) -> List[ResultRace]:
        if not raw_data:
            return []

        races = []
        date_str = raw_data.get("date", datetime.now().strftime("%Y-%m-%d"))

        for item in raw_data.get("pages", []):
            html_content = item.get("html")
            if not html_content:
                continue

            try:
                race = self._parse_race_page(html_content, date_str, item.get("url", ""))
                if race:
                    races.append(race)
            except Exception as e:
                self.logger.warning("Failed to parse RP result", error=str(e))

        return races

    def _parse_race_page(
        self,
        html_content: str,
        date_str: str,
        url: str
    ) -> Optional[ResultRace]:
        """Parse a Racing Post result page."""
        parser = HTMLParser(html_content)

        # Get venue
        venue_node = parser.css_first(".rp-raceTimeCourseName__course")
        if not venue_node:
            return None
        venue = normalize_venue_name(venue_node.text(strip=True))

        # Extract race number from URL or header
        race_num = 1
        race_num_match = re.search(r'Race\s+(\d+)', html_content)
        if race_num_match:
            race_num = int(race_num_match.group(1))

        # Parse runners
        runners = []
        for row in parser.css(".rp-horseTable__table__row"):
            try:
                name_node = row.css_first(".rp-horseTable__horse__name")
                pos_node = row.css_first(".rp-horseTable__pos__number")

                if not name_node:
                    continue

                name = clean_text(name_node.text())
                pos = clean_text(pos_node.text()) if pos_node else None

                # Try to get saddle number
                number_node = row.css_first(".rp-horseTable__saddleClothNo")
                number = 0
                if number_node:
                    num_text = clean_text(number_node.text())
                    try:
                        number = int(num_text)
                    except ValueError:
                        pass

                runners.append(ResultRunner(
                    name=name,
                    number=number,
                    position=pos,
                ))
            except Exception:
                continue

        if not runners:
            return None

        try:
            race_date = datetime.strptime(date_str, "%Y-%m-%d")
            start_time = race_date.replace(hour=12, minute=0, tzinfo=timezone.utc)
        except ValueError:
            start_time = datetime.now(timezone.utc)

        def get_canonical_venue_local(venue: str) -> str:
            if not venue: return ""
            canonical = re.sub(r'\s*\([^)]*\)\s*', '', venue)
            canonical = re.sub(r'[^a-zA-Z0-9]', '', canonical).lower()
            return canonical

        return ResultRace(
            id=f"rp_res_{get_canonical_venue_local(venue)}_{date_str.replace('-', '')}_R{race_num}",
            venue=venue,
            race_number=race_num,
            start_time=start_time,
            runners=runners,
            source=self.SOURCE_NAME,
        )
