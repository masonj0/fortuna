from typing import Any, Dict, List, Optional, Set, Tuple
from datetime import datetime, timezone
import re
import json
from selectolax.parser import HTMLParser, Node

from .base import (
    PageFetchingResultsAdapter,
    parse_currency_value,
    parse_fractional_odds,
    build_start_time,
    find_nested_value
)
from ...models import ResultRace, ResultRunner
from ...utils.text import normalize_venue_name, clean_text
from ...core.smart_fetcher import FetchStrategy, BrowserEngine
import fortuna


class SportingLifeResultsAdapter(PageFetchingResultsAdapter):
    """Sporting Life results (UK / IRE / International)."""

    SOURCE_NAME = "SportingLifeResults"
    BASE_URL    = "https://www.sportinglife.com"
    HOST        = "www.sportinglife.com"
    IMPERSONATE = "chrome120"
    TIMEOUT     = 45

    def _configure_fetch_strategy(self) -> fortuna.FetchStrategy:
        strategy = super()._configure_fetch_strategy()
        # SportingLife is JS-heavy; keep CURL_CFFI primary but ensure fallback (Project Hardening)
        strategy.primary_engine = fortuna.BrowserEngine.CURL_CFFI
        return strategy

    # -- link discovery ----------------------------------------------------

    async def _discover_result_links(self, date_str: str) -> Set[str]:
        resp = await self.make_request(
            "GET",
            f"/racing/results/{date_str}",
            headers=self._get_headers(),
        )
        if not resp or not resp.text:
            return set()
        self._save_debug_snapshot(resp.text, f"sl_results_index_{date_str}")
        return self._extract_sl_links(resp.text)

    def _extract_sl_links(self, html: str) -> set:
        links: set = set()
        for a in HTMLParser(html).css("a[href*='/racing/results/']"):
            href = a.attributes.get("href", "")
            if not href: continue
            if not self._venue_matches(a.text(), href):
                continue
            # /racing/results/2026-02-04/ludlow/901676/race-name
            if re.search(r"/results/\d{4}-\d{2}-\d{2}/.+/\d+/", href):
                links.add(href)
        return links

    # -- page parsing (two strategies) -------------------------------------

    def _parse_race_page(
        self, html: str, date_str: str, url: str,
    ) -> Optional[ResultRace]:
        parser = HTMLParser(html)

        # Strategy 1 — Next.js JSON payload (most reliable)
        script = parser.css_first("script#__NEXT_DATA__")
        if script:
            race = self._parse_from_next_data(script.text(), date_str)
            if race:
                return race

        # Strategy 2 — HTML scrape fallback
        return self._parse_from_html(parser, date_str)

    # -- Strategy 1: JSON -------------------------------------------------

    def _parse_from_next_data(
        self, script_text: str, date_str: str,
    ) -> Optional[ResultRace]:
        try:
            data = json.loads(script_text)
        except json.JSONDecodeError as exc:
            self.logger.debug("Invalid __NEXT_DATA__", error=str(exc))
            return None

        race_data = (
            data.get("props", {}).get("pageProps", {}).get("race", {})
        )
        if not race_data:
            return None

        summary    = race_data.get("race_summary", {})
        venue      = fortuna.normalize_venue_name(
            summary.get("course_name", "Unknown"),
        )
        race_num   = (
            race_data.get("race_number")
            or summary.get("race_number")
            or 1
        )
        date_val   = summary.get("date", date_str)
        start_time = build_start_time(date_val, summary.get("time"))

        runners = self._runners_from_json(race_data)
        if not runners:
            return None

        # Exotic payouts via recursive search
        trifecta_pay   = find_nested_value(race_data, "trifecta")
        superfecta_pay = find_nested_value(race_data, "superfecta")

        # Place payouts from CSV field
        self._apply_place_payouts_from_csv(
            race_data.get("place_win", ""), runners,
        )

        return ResultRace(
            id=self._make_race_id("sl_res", venue, date_val, race_num),
            venue=venue,
            race_number=race_num,
            start_time=start_time,
            runners=runners,
            trifecta_payout=trifecta_pay,
            superfecta_payout=superfecta_pay,
            source=self.SOURCE_NAME,
        )

    @staticmethod
    def _runners_from_json(race_data: dict) -> List[ResultRunner]:
        """Extract runners from rides (result pages) or runners."""
        items = race_data.get("rides") or race_data.get("runners", [])
        runners: List[ResultRunner] = []
        for item in items:
            horse = item.get("horse", {})
            name  = horse.get("name") or item.get("name")
            if not name:
                continue
            sp_raw = (
                item.get("starting_price")
                or item.get("sp")
                or item.get("betting", {}).get("current_odds", "")
            )
            runners.append(ResultRunner(
                name=name,
                number=(
                    item.get("cloth_number")
                    or item.get("saddle_cloth_number", 0)
                ),
                position=str(item.get("finish_position", item.get("position", ""))),
                final_win_odds=parse_fractional_odds(str(sp_raw)),
            ))
        return runners

    @staticmethod
    def _apply_place_payouts_from_csv(
        place_csv: str,
        runners: List[ResultRunner],
    ) -> None:
        """Map comma-separated place payouts to runners by finishing position."""
        if not isinstance(place_csv, str) or not place_csv:
            return
        pays = [parse_currency_value(p) for p in place_csv.split(",")]
        for runner in runners:
            pos = runner.position_numeric
            if pos and 1 <= pos <= len(pays):
                runner.place_payout = pays[pos - 1]

    # -- Strategy 2: HTML fallback ----------------------------------------

    def _parse_from_html(
        self, parser: HTMLParser, date_str: str,
    ) -> Optional[ResultRace]:
        header = parser.css_first("h1")
        if not header:
            return None

        match = re.match(
            r"(\d{1,2}:\d{2})\s+(.+)\s+Result",
            clean_text(header.text()),
        )
        if not match:
            return None

        time_str   = match.group(1)
        venue      = normalize_venue_name(match.group(2))
        start_time = build_start_time(date_str, time_str)

        runners: List[ResultRunner] = []
        for row in parser.css(
            'div[class*="ResultRunner__StyledResultRunnerWrapper"]',
        ):
            name_node = row.css_first(
                'a[class*="ResultRunner__StyledHorseName"]',
            )
            if not name_node:
                continue
            pos_node = row.css_first(
                'div[class*="ResultRunner__StyledRunnerPositionContainer"]',
            )
            runners.append(ResultRunner(
                name=clean_text(name_node.text()),
                number=0,
                position=(
                    clean_text(pos_node.text()) if pos_node else None
                ),
            ))

        if not runners:
            return None

        return ResultRace(
            id=self._make_race_id("sl_res", venue, date_str, 1),
            venue=venue,
            race_number=1,
            start_time=start_time,
            runners=runners,
            source=self.SOURCE_NAME,
        )
