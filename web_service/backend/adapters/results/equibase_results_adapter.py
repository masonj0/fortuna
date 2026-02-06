from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone, date
import re
import asyncio
from selectolax.parser import HTMLParser, Node

from ..base_adapter_v3 import BaseAdapterV3
from ..mixins import BrowserHeadersMixin, DebugMixin
from ...models import ResultRace, ResultRunner
from ...utils.text import normalize_venue_name, clean_text
from ...utils.odds import parse_odds_to_decimal
from ...core.smart_fetcher import FetchStrategy, BrowserEngine


class EquibaseResultsAdapter(BrowserHeadersMixin, DebugMixin, BaseAdapterV3):
    """
    Adapter for Equibase Results / Summary Charts.
    Primary source for US thoroughbred race results.
    """

    SOURCE_NAME = "EquibaseResults"
    BASE_URL = "https://www.equibase.com"

    def __init__(self, **kwargs):
        super().__init__(
            source_name=self.SOURCE_NAME,
            base_url=self.BASE_URL,
            **kwargs
        )
        self._semaphore = asyncio.Semaphore(5)

    def _configure_fetch_strategy(self) -> FetchStrategy:
        return FetchStrategy(
            primary_engine=BrowserEngine.HTTPX,
            enable_js=False,
            timeout=30,
        )

    def _get_headers(self) -> dict:
        return self._get_browser_headers(host="www.equibase.com")

    async def _fetch_data(self, date_str: str) -> Optional[Dict[str, Any]]:
        """Fetch results index and all track pages for a date."""
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            self.logger.error("Invalid date format", date=date_str)
            return None

        url = f"/static/chart/summary/index.html?date={dt.strftime('%m/%d/%Y')}"

        resp = await self.make_request("GET", url, headers=self._get_headers())
        if not resp or not resp.text:
            self.logger.warning("No response from Equibase index", url=url)
            return None

        self._save_debug_snapshot(resp.text, f"eqb_results_index_{date_str}")
        parser = HTMLParser(resp.text)

        # Extract track-specific result page links
        links = set()
        for a in parser.css("a"):
            href = a.attributes.get("href", "")
            if (
                "/static/chart/summary/" in href
                and href.endswith(".html")
                and "index.html" not in href
            ):
                links.add(href)

        if not links:
            self.logger.warning("No track result links found", date=date_str)
            return None

        self.logger.info("Found track result pages", count=len(links))

        # Fetch all track pages concurrently
        async def fetch_track_page(link: str) -> Tuple[str, str]:
            async with self._semaphore:
                try:
                    r = await self.make_request("GET", link, headers=self._get_headers())
                    return (link, r.text if r else "")
                except Exception as e:
                    self.logger.warning("Failed to fetch track page", link=link, error=str(e))
                    return (link, "")

        tasks = [fetch_track_page(link) for link in links]
        pages = await asyncio.gather(*tasks)

        valid_pages = [(link, html) for link, html in pages if html]
        return {"pages": valid_pages, "date": date_str}

    def _parse_races(self, raw_data: Any) -> List[ResultRace]:
        """Parse all track pages into ResultRace objects."""
        if not raw_data or not raw_data.get("pages"):
            return []

        races = []
        for link, html_content in raw_data["pages"]:
            if not html_content:
                continue
            try:
                parsed = self._parse_track_page(html_content, raw_data["date"], link)
                races.extend(parsed)
            except Exception as e:
                self.logger.warning(
                    "Failed to parse track page",
                    link=link,
                    error=str(e),
                    exc_info=True
                )
        return races

    def _parse_track_page(
        self,
        html_content: str,
        date_str: str,
        source_url: str
    ) -> List[ResultRace]:
        """Parse a single track's results page."""
        parser = HTMLParser(html_content)
        races = []

        # Get venue from header
        track_node = parser.css_first("h3") or parser.css_first("h2")
        if not track_node:
            self.logger.debug("No track header found", url=source_url)
            return []

        venue = normalize_venue_name(track_node.text(strip=True))
        if not venue:
            return []

        # Find all race tables - they typically have "Race X" in the header
        all_tables = parser.css("table")
        race_tables = []

        for table in all_tables:
            header = table.css_first("thead tr th")
            if header and "Race" in header.text():
                race_tables.append(table)

        for race_table in race_tables:
            try:
                race = self._parse_race_table(race_table, venue, date_str, parser)
                if race:
                    races.append(race)
            except Exception as e:
                self.logger.debug("Failed to parse race table", error=str(e))

        return races

    def _parse_race_table(
        self,
        race_table: Node,
        venue: str,
        date_str: str,
        page_parser: HTMLParser
    ) -> Optional[ResultRace]:
        """Parse a single race table into a ResultRace."""
        header = race_table.css_first("thead tr th")
        if not header:
            return None

        race_num_match = re.search(r"Race\s+(\d+)", header.text())
        if not race_num_match:
            return None

        race_num = int(race_num_match.group(1))

        # Parse runners
        runners = []
        for row in race_table.css("tbody tr"):
            runner = self._parse_runner_row(row)
            if runner:
                runners.append(runner)

        if not runners:
            return None

        # Parse exotic payouts from the dividends section
        trifecta_payout, trifecta_combo = self._find_exotic_payout(
            race_table, page_parser, "trifecta"
        )
        exacta_payout, exacta_combo = self._find_exotic_payout(
            race_table, page_parser, "exacta"
        )

        # Build start time
        try:
            race_date = datetime.strptime(date_str, "%Y-%m-%d")
            start_time = race_date.replace(
                hour=12, minute=0,
                tzinfo=timezone.utc
            )
        except ValueError:
            start_time = datetime.now(timezone.utc)

        def get_canonical_venue_local(venue: str) -> str:
            if not venue: return ""
            canonical = re.sub(r'\s*\([^)]*\)\s*', '', venue)
            canonical = re.sub(r'[^a-zA-Z0-9]', '', canonical).lower()
            return canonical

        return ResultRace(
            id=f"eqb_res_{get_canonical_venue_local(venue)}_{date_str.replace('-', '')}_R{race_num}",
            venue=venue,
            race_number=race_num,
            start_time=start_time,
            runners=runners,
            source=self.SOURCE_NAME,
            is_fully_parsed=True,
            trifecta_payout=trifecta_payout,
            trifecta_combination=trifecta_combo,
            exacta_payout=exacta_payout,
            exacta_combination=exacta_combo,
        )

    def _parse_runner_row(self, row: Node) -> Optional[ResultRunner]:
        """Parse a single runner row from results table."""
        cols = row.css("td")
        if len(cols) < 3:
            return None

        pos_text = clean_text(cols[0].text())
        num_text = clean_text(cols[1].text())
        name = clean_text(cols[2].text())

        # Skip header-like rows
        if not name or name.upper() in ("HORSE", "NAME", "RUNNER"):
            return None

        # Parse number
        try:
            number = int(num_text) if num_text.isdigit() else 0
        except ValueError:
            number = 0

        # Parse odds
        odds_text = clean_text(cols[3].text()) if len(cols) > 3 else ""
        final_odds = parse_odds_to_decimal(odds_text)

        # Parse payouts (columns 4, 5, 6 typically)
        win_pay = place_pay = show_pay = 0.0
        if len(cols) >= 7:
            win_pay = self._parse_currency_value(cols[4].text())
            place_pay = self._parse_currency_value(cols[5].text())
            show_pay = self._parse_currency_value(cols[6].text())

        return ResultRunner(
            name=name,
            number=number,
            position=pos_text,
            final_win_odds=final_odds,
            win_payout=win_pay,
            place_payout=place_pay,
            show_payout=show_pay,
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

    def _find_exotic_payout(
        self,
        race_table: Node,
        page_parser: HTMLParser,
        bet_type: str
    ) -> Tuple[Optional[float], Optional[str]]:
        """Find exotic bet payout from dividend tables."""
        all_tables = page_parser.css("table")
        race_table_html = race_table.html if hasattr(race_table, 'html') else str(race_table)

        found_race_table = False
        for table in all_tables:
            table_html = table.html if hasattr(table, 'html') else str(table)

            if not found_race_table:
                if table_html == race_table_html:
                    found_race_table = True
                continue

            table_text = table.text().lower()
            if bet_type.lower() not in table_text:
                continue

            for row in table.css("tr"):
                row_text = row.text().lower()
                if bet_type.lower() in row_text:
                    cols = row.css("td")
                    if len(cols) >= 2:
                        combination = clean_text(cols[0].text())
                        payout = self._parse_currency_value(cols[1].text())
                        if payout > 0:
                            return payout, combination
            break

        return None, None
