# python_service/adapters/at_the_races_adapter.py
"""Adapter for attheraces.com."""

import asyncio
import re
from datetime import datetime
from typing import Any, List, Optional

from selectolax.parser import HTMLParser, Node

from ..models import Race, Runner, OddsData
from ..utils.odds import parse_odds_to_decimal, SmartOddsExtractor
from ..utils.text import clean_text, normalize_venue_name
from .base_adapter_v3 import BaseAdapterV3
from .mixins import BrowserHeadersMixin, DebugMixin, RacePageFetcherMixin
from .utils.odds_validator import create_odds_data
from ..core.smart_fetcher import BrowserEngine, FetchStrategy


class AtTheRacesAdapter(BrowserHeadersMixin, DebugMixin, RacePageFetcherMixin, BaseAdapterV3):
    """
    Adapter for attheraces.com, migrated to BaseAdapterV3.
    Standardized on selectolax for performance.
    """

    SOURCE_NAME = "AtTheRaces"
    BASE_URL = "https://www.attheraces.com"

    SELECTORS = {
        "race_links": [
            'a.race-navigation-link',
            'a.sidebar-racecardsigation-link',
            'a[href^="/racecard/"]',
            'a[href*="/racecard/"]',
        ],
        "details_container": [
            ".race-header__details--primary",
            "atr-racecard-race-header .container",
            ".racecard-header .container",
        ],
        "track_name": ["h2", "h1 a", "h1"],
        "race_time": ["h2 b", "h1 span", ".race-time"],
        "distance": [
            ".race-header__details--secondary .p--large",
            ".race-header__details--secondary div",
        ],
        "runners": [
            ".card-cell--horse",
            ".odds-grid-horse",
            "atr-horse-in-racecard",
            ".horse-in-racecard",
        ],
    }

    def __init__(self, config=None):
        super().__init__(
            source_name=self.SOURCE_NAME,
            base_url=self.BASE_URL,
            config=config
        )

    def _configure_fetch_strategy(self) -> FetchStrategy:
        """AtTheRaces is a simple HTML site - HTTPX is fastest."""
        return FetchStrategy(primary_engine=BrowserEngine.HTTPX, enable_js=False)

    def _get_headers(self) -> dict:
        """Get headers for ATR requests."""
        return self._get_browser_headers(
            host="www.attheraces.com",
            referer="https://www.attheraces.com/racecards",
        )

    async def _fetch_data(self, date: str) -> Optional[dict]:
        """Fetch race pages for a given date."""
        index_url = f"/racecards/{date}"
        resp = await self.make_request("GET", index_url, headers=self._get_headers())
        if not resp or not resp.text:
            raise AdapterHttpError(self.source_name, 500, index_url)

        self._save_debug_snapshot(resp.text, f"atr_index_{date}")
        parser = HTMLParser(resp.text)
        metadata = self._extract_race_metadata(parser)

        if not metadata:
            return None

        pages = await self._fetch_race_pages_concurrent(metadata, self._get_headers(), semaphore_limit=5)
        return {"pages": pages, "date": date}

    def _extract_race_metadata(self, parser: HTMLParser) -> List[dict]:
        meta = []
        track_map = {}
        for link in parser.css('a[href*="/racecard/"]'):
            url = link.attributes.get("href")
            if not url or not (re.search(r"/\d{4}$", url) or re.search(r"/\d{1,2}$", url)):
                continue
            parts = url.split("/")
            if len(parts) >= 3:
                track = parts[2]
                if track not in track_map:
                    track_map[track] = []
                track_map[track].append(url)

        for track, urls in track_map.items():
            for i, url in enumerate(sorted(set(urls))):
                meta.append({"url": url, "race_number": i + 1, "venue_raw": track})

        if not meta:
            # Fallback to meeting summary
            for meeting in (parser.css(".meeting-summary") or parser.css(".p-meetings__item")):
                for i, link in enumerate(meeting.css('a[href*="/racecard/"]')):
                    if url := link.attributes.get("href"):
                        meta.append({"url": url, "race_number": i + 1})
        return meta

    def _parse_races(self, raw_data: Any) -> List[Race]:
        """Parse race pages into Race objects."""
        if not raw_data or not raw_data.get("pages"):
            return []

        try:
            race_date = datetime.strptime(raw_data["date"], "%Y-%m-%d").date()
        except ValueError:
            return []

        races = []
        for item in raw_data["pages"]:
            html_content = item.get("html")
            if not html_content:
                continue

            try:
                race = self._parse_single_race(html_content, item.get("url", ""), race_date, item.get("race_number"))
                if race:
                    races.append(race)
            except Exception as e:
                self.logger.warning("Error parsing race", url=item.get("url"), error=str(e))
        return races

    def _parse_single_race(
        self, html_content: str, url_path: str, race_date, race_number_fallback: Optional[int]
    ) -> Optional[Race]:
        """Parse a single race from HTML."""
        parser = HTMLParser(html_content)
        track_name, time_str, header_text = None, None, ""

        header = parser.css_first(".race-header__details") or parser.css_first(".racecard-header")
        if header:
            header_text = clean_text(header.text()) or ""
            time_match = re.search(r"(\d{1,2}:\d{2})", header_text)
            if time_match:
                time_str = time_match.group(1)
                track_raw = re.sub(r"\d{1,2}\s+[A-Za-z]{3}\s+\d{4}", "", header_text.replace(time_str, "")).strip()
                track_raw = re.split(r"\s+Race\s+\d+", track_raw, flags=re.I)[0]
                track_raw = re.sub(r"^\d+\s+", "", track_raw).split(" - ")[0].split("|")[0].strip()
                track_name = normalize_venue_name(track_raw)

        if not track_name:
            details = parser.css_first(".race-header__details--primary")
            if details:
                track_node = details.css_first("h2") or details.css_first("h1 a") or details.css_first("h1")
                if track_node:
                    track_name = normalize_venue_name(clean_text(track_node.text()))
                if not time_str:
                    time_node = details.css_first("h2 b") or details.css_first(".race-time")
                    if time_node:
                        time_str = clean_text(time_node.text()).replace(" ATR", "")

        if not track_name:
            parts = url_path.split("/")
            if len(parts) >= 3:
                track_name = normalize_venue_name(parts[2])

        if not time_str:
            parts = url_path.split("/")
            if len(parts) >= 5 and re.match(r"\d{4}", parts[-1]):
                raw_time = parts[-1]
                time_str = f"{raw_time[:2]}:{raw_time[2:]}"

        if not track_name or not time_str:
            return None

        try:
            start_time = datetime.combine(race_date, datetime.strptime(time_str, "%H:%M").time())
            start_time = start_time.replace(tzinfo=timezone.utc)
        except ValueError:
            return None

        race_number = race_number_fallback or 1
        distance = None
        dist_match = re.search(r"\|\s*(\d+[mfy].*)", header_text, re.I)
        if dist_match:
            distance = dist_match.group(1).strip()

        runners = self._parse_runners_enhanced(parser)

        if not runners:
            return None

        # Capture available bets
        available_bets = []
        html_lower = html_content.lower()
        for kw in ["superfecta", "trifecta", "exacta", "quinella"]:
            if kw in html_lower:
                available_bets.append(kw.capitalize())

        return Race(
            id=f"atr_{track_name.lower().replace(' ', '')}_{start_time:%Y%m%d}_R{race_number}",
            venue=track_name,
            race_number=race_number,
            start_time=start_time,
            runners=runners,
            distance=distance,
            source=self.SOURCE_NAME,
            metadata={"available_bets": available_bets}
        )

    def _parse_runners_enhanced(self, parser: HTMLParser) -> List[Runner]:
        """Improved runner parsing with odds fallback."""
        odds_map = {}
        for row in parser.css(".odds-grid__row--horse"):
            if m := re.search(r"row-(\d+)", row.attributes.get("id", "")):
                if price := row.attributes.get("data-bestprice"):
                    try:
                        p_val = float(price)
                        if p_val > 0:
                            odds_map[m.group(1)] = p_val
                    except:
                        pass

        runners = []
        for selector in self.SELECTORS["runners"]:
            nodes = parser.css(selector)
            if nodes:
                for i, node in enumerate(nodes):
                    runner = self._parse_single_runner_enhanced(node, odds_map, i + 1)
                    if runner:
                        runners.append(runner)
                break
        return runners

    def _parse_single_runner_enhanced(self, row: Node, odds_map: dict, fallback_number: int) -> Optional[Runner]:
        try:
            name_node = row.css_first("h3") or row.css_first("a.horse__link") or row.css_first('a[href*="/form/horse/"]')
            if not name_node:
                return None
            name = clean_text(name_node.text())
            if not name:
                return None

            num_node = row.css_first(".horse-in-racecard__saddle-cloth-number") or row.css_first(".odds-grid-horse__no")
            number = 0
            if num_node:
                ns = clean_text(num_node.text())
                if ns:
                    digits = "".join(filter(str.isdigit, ns))
                    if digits:
                        number = int(digits)

            if number == 0 or number > 50:
                number = fallback_number

            win_odds = None
            if horse_link := row.css_first('a[href*="/form/horse/"]'):
                if m := re.search(r"/(\d+)(\?|$)", horse_link.attributes.get("href", "")):
                    win_odds = odds_map.get(m.group(1))

            if win_odds is None:
                if odds_node := row.css_first(".horse-in-racecard__odds"):
                    win_odds = parse_odds_to_decimal(clean_text(odds_node.text()))

            # Advanced heuristic fallback
            if win_odds is None:
                win_odds = SmartOddsExtractor.extract_from_node(row)

            odds = {}
            if win_odds:
                odds[self.SOURCE_NAME] = OddsData(win=win_odds, source=self.SOURCE_NAME, last_updated=datetime.now(timezone.utc))

            return Runner(number=number, name=name, odds=odds)
        except:
            return None
