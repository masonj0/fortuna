from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import re
from selectolax.parser import HTMLParser

from ..base_adapter_v3 import BaseAdapterV3
from ..mixins import BrowserHeadersMixin, DebugMixin, RacePageFetcherMixin
from ...models import ResultRace, ResultRunner
from ...utils.text import normalize_venue_name, clean_text
from ...core.smart_fetcher import FetchStrategy, BrowserEngine


class AtTheRacesResultsAdapter(BrowserHeadersMixin, DebugMixin, RacePageFetcherMixin, BaseAdapterV3):
    """Adapter for At The Races results (UK/IRE)."""

    SOURCE_NAME = "AtTheRacesResults"
    BASE_URL = "https://www.attheraces.com"

    def __init__(self, **kwargs):
        super().__init__(
            source_name=self.SOURCE_NAME,
            base_url=self.BASE_URL,
            **kwargs
        )

    def _configure_fetch_strategy(self) -> FetchStrategy:
        return FetchStrategy(primary_engine=BrowserEngine.HTTPX, enable_js=False)

    def _get_headers(self) -> dict:
        return self._get_browser_headers(host="www.attheraces.com")

    async def _fetch_data(self, date_str: str) -> Optional[Dict[str, Any]]:
        url = f"/results/{date_str}"
        resp = await self.make_request("GET", url, headers=self._get_headers())
        if not resp:
            return None

        parser = HTMLParser(resp.text)

        # Find result page links
        links = []
        for a in parser.css("a[href*='/results/']"):
            href = a.attributes.get("href", "")
            # ATR format: /results/Venue/DD-Mon-YYYY/HHMM
            if re.search(r"/results/[^/]+/\d{2}-[A-Za-z]{3}-\d{4}/", href):
                links.append(href)

        unique_links = list(set(links))
        if not unique_links:
            return None

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
                self.logger.warning("Failed to parse ATR result", error=str(e))

        return races

    def _parse_race_page(
        self,
        html_content: str,
        date_str: str,
        url: str
    ) -> Optional[ResultRace]:
        """Parse an ATR result page."""
        parser = HTMLParser(html_content)

        header = parser.css_first(".race-header__details--primary")
        if not header:
            return None

        venue_node = header.css_first("h2")
        if not venue_node:
            return None
        venue = normalize_venue_name(venue_node.text(strip=True))

        # Extract race number from URL: /results/Venue/Date/R1 or just time
        race_num = 1
        url_match = re.search(r'/R(\d+)$', url)
        if url_match:
            race_num = int(url_match.group(1))

        # Parse runners
        runners = []
        for row in parser.css(".result-racecard__row"):
            try:
                name_node = row.css_first(".result-racecard__horse-name a")
                pos_node = row.css_first(".result-racecard__pos")

                if not name_node:
                    continue

                name = clean_text(name_node.text())
                pos = clean_text(pos_node.text()) if pos_node else None

                # Saddle number
                num_node = row.css_first(".result-racecard__saddle-cloth")
                number = 0
                if num_node:
                    try:
                        number = int(clean_text(num_node.text()))
                    except ValueError:
                        pass

                runners.append(ResultRunner(
                    name=name,
                    number=number,
                    position=pos,
                ))
            except Exception:
                continue

        # Parse trifecta from dividends table
        trifecta_pay = None
        trifecta_combo = None
        div_table = parser.css_first(".result-racecard__dividends-table")
        if div_table:
            for row in div_table.css("tr"):
                row_text = row.text().lower()
                if "trifecta" in row_text:
                    cols = row.css("td")
                    if len(cols) >= 2:
                        trifecta_combo = clean_text(cols[0].text())
                        trifecta_pay = self._parse_currency_value(cols[1].text())
                    break

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
            id=f"atr_res_{get_canonical_venue_local(venue)}_{date_str.replace('-', '')}_R{race_num}",
            venue=venue,
            race_number=race_num,
            start_time=start_time,
            runners=runners,
            trifecta_payout=trifecta_pay,
            trifecta_combination=trifecta_combo,
            source=self.SOURCE_NAME,
        )

    def _parse_currency_value(self, value_str: str) -> float:
        """Parse currency strings like '$123.45'."""
        if not value_str:
            return 0.0
        try:
            cleaned = re.sub(r'[^\d.]', '', value_str)
            return float(cleaned) if cleaned else 0.0
        except (ValueError, TypeError):
            return 0.0
