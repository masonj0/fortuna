from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone
import re
import asyncio
from selectolax.parser import HTMLParser, Node

from ..base_adapter_v3 import BaseAdapterV3
from ..mixins import BrowserHeadersMixin, DebugMixin
from ...models import Race, Runner, ResultRace, ResultRunner
from ...utils.text import normalize_venue_name, clean_text
from ...core.smart_fetcher import FetchStrategy, BrowserEngine, StealthMode


class RacingPostToteAdapter(BrowserHeadersMixin, DebugMixin, BaseAdapterV3):
    """
    Adapter for fetching Tote dividends and results from Racing Post.
    """
    SOURCE_NAME = "RacingPostTote"
    BASE_URL = "https://www.racingpost.com"

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(source_name=self.SOURCE_NAME, base_url=self.BASE_URL, config=config)

    def _configure_fetch_strategy(self) -> FetchStrategy:
        return FetchStrategy(
            primary_engine=BrowserEngine.CURL_CFFI,
            enable_js=True,
            stealth_mode=StealthMode.CAMOUFLAGE,
            timeout=45
        )

    def _get_headers(self) -> dict:
        return self._get_browser_headers(host="www.racingpost.com")

    async def _fetch_data(self, date_str: str) -> Optional[Dict[str, Any]]:
        url = f"/results/{date_str}"
        resp = await self.make_request("GET", url, headers=self._get_headers())
        if not resp or not resp.text:
            return None

        self._save_debug_snapshot(resp.text, f"rp_tote_results_{date_str}")
        parser = HTMLParser(resp.text)

        # Extract links to individual race results
        links = [a.attributes.get("href") for a in parser.css('a[data-test-selector="RC-meetingItem__link_race"]') if a.attributes.get("href")]

        async def fetch_result_page(link):
            r = await self.make_request("GET", link, headers=self._get_headers())
            return (link, r.text if r else "")

        tasks = [fetch_result_page(link) for link in links]
        pages = await asyncio.gather(*tasks)
        return {"pages": pages, "date": date_str}

    def _parse_races(self, raw_data: Any) -> List[ResultRace]:
        if not raw_data or not raw_data.get("pages"):
            return []

        races = []
        date_str = raw_data["date"]

        for link, html_content in raw_data["pages"]:
            if not html_content:
                continue
            try:
                parser = HTMLParser(html_content)
                race = self._parse_result_page(parser, date_str, link)
                if race:
                    races.append(race)
            except Exception as e:
                self.logger.warning("Failed to parse RP result page", link=link, error=str(e))

        return races

    def _parse_result_page(self, parser: HTMLParser, date_str: str, url: str) -> Optional[ResultRace]:
        venue_node = parser.css_first('a[data-test-selector="RC-course__name"]')
        if not venue_node:
            return None
        venue = normalize_venue_name(venue_node.text(strip=True))

        time_node = parser.css_first('span[data-test-selector="RC-course__time"]')
        if not time_node:
            return None
        time_str = time_node.text(strip=True)

        try:
            start_time = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        except:
            return None

        # Extract dividends
        dividends = {}
        tote_container = parser.css_first('div[data-test-selector="RC-toteReturns"]')
        if not tote_container:
             # Try alternate selector
             tote_container = parser.css_first('.rp-toteReturns')

        if tote_container:
            for row in (tote_container.css('div.rp-toteReturns__row') or tote_container.css('.rp-toteReturns__row')):
                label_node = row.css_first('div.rp-toteReturns__label') or row.css_first('.rp-toteReturns__label')
                val_node = row.css_first('div.rp-toteReturns__value') or row.css_first('.rp-toteReturns__value')
                if label_node and val_node:
                    label = clean_text(label_node.text())
                    value = clean_text(val_node.text())
                    if label and value:
                        dividends[label] = value

        # Extract runners (finishers)
        runners = []
        for row in parser.css('div[data-test-selector="RC-resultRunner"]'):
            name_node = row.css_first('a[data-test-selector="RC-resultRunnerName"]')
            if not name_node:
                continue
            name = clean_text(name_node.text())
            pos_node = row.css_first('span.rp-resultRunner__position')
            pos = clean_text(pos_node.text()) if pos_node else "?"

            runners.append(ResultRunner(
                name=name,
                number=0,
                position=pos
            ))

        def get_canonical_venue_local(venue: str) -> str:
            if not venue: return ""
            canonical = re.sub(r'\s*\([^)]*\)\s*', '', venue)
            canonical = re.sub(r'[^a-zA-Z0-9]', '', canonical).lower()
            return canonical

        race = ResultRace(
            id=f"rp_tote_{get_canonical_venue_local(venue)}_{date_str.replace('-', '')}_{time_str.replace(':', '')}",
            venue=venue,
            race_number=1, # RP doesn't easily show race number on result page title
            start_time=start_time,
            runners=runners,
            source=self.SOURCE_NAME,
            official_dividends={k: self._parse_currency_value(v) for k, v in dividends.items()},
            chart_url=url
        )
        return race

    def _parse_currency_value(self, value_str: str) -> float:
        """Parse currency strings like '£1.23'."""
        if not value_str:
            return 0.0
        try:
            cleaned = re.sub(r'[^\d.]', '', value_str)
            return float(cleaned) if cleaned else 0.0
        except (ValueError, TypeError):
            return 0.0
