from typing import Any, Dict, List, Optional, Set, Tuple
from datetime import datetime, timezone
import re
import asyncio
from selectolax.parser import HTMLParser, Node

from .base import (
    PageFetchingResultsAdapter,
    extract_exotic_payouts,
    parse_currency_value,
    parse_fractional_odds,
    build_start_time
)
from ...models import ResultRace, ResultRunner
from ...utils.text import normalize_venue_name, clean_text
from ...core.smart_fetcher import FetchStrategy, BrowserEngine
import fortuna


class AtTheRacesResultsAdapter(PageFetchingResultsAdapter):
    """At The Races results — UK / IRE."""

    SOURCE_NAME = "AtTheRacesResults"
    BASE_URL    = "https://www.attheraces.com"
    HOST        = "www.attheraces.com"
    IMPERSONATE = "chrome120"
    TIMEOUT     = 60

    def _configure_fetch_strategy(self) -> fortuna.FetchStrategy:
        strategy = super()._configure_fetch_strategy()
        # ATR uses Cloudflare; keep CURL_CFFI primary but ensure fallback (Project Hardening)
        strategy.primary_engine = fortuna.BrowserEngine.CURL_CFFI
        return strategy

    # -- link discovery (multi-URL index) ----------------------------------

    async def _discover_result_links(self, date_str: str) -> set:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        index_urls = [
            f"/results/{date_str}",
            f"/results/{dt.strftime('%d-%B-%Y')}",
            f"/results/international/{date_str}",
            f"/results/international/{dt.strftime('%d-%B-%Y')}",
        ]

        links: set = set()
        for url in index_urls:
            try:
                resp = await self.make_request(
                    "GET", url, headers=self._get_headers(),
                )
                if not resp or not resp.text:
                    continue
                self._save_debug_snapshot(
                    resp.text,
                    f"atr_index_{date_str}_{url.replace('/', '_')}",
                )
                links.update(self._extract_atr_links(resp.text))
            except Exception as exc:
                self.logger.debug(
                    "ATR index fetch failed", url=url, error=str(exc),
                )

        return links

    def _extract_atr_links(self, html: str) -> set:
        parser = HTMLParser(html)
        links: set = set()
        # Broad selectors for all possible result links (Council of Superbrains Directive)
        for selector in [
            "a[href*='/results/']",
            "a[data-test-selector*='result']",
            ".meeting-summary a",
            ".p-results__item a",
            ".p-meetings__item a",
            ".p-results-meeting a",
        ]:
            for a in parser.css(selector):
                href = a.attributes.get("href", "")
                if not href:
                    continue
                if not self._venue_matches(a.text(), href):
                    continue
                if self._is_atr_race_link(href):
                    links.add(
                        href if href.startswith("http")
                        else f"{self.BASE_URL}{href}"
                    )
        return links

    @staticmethod
    def _is_atr_race_link(href: str) -> bool:
        return bool(
            re.search(r"/results/.*?/\d{4}", href)
            or re.search(r"/results/\d{2}-.*?-\d{4}/", href)
            or re.search(r"/results/.*?/\d+$", href)
            or ("/results/" in href and len(href.split("/")) >= 4)
        )

    # -- single-race page parsing ------------------------------------------

    def _parse_race_page(
        self, html: str, date_str: str, url: str,
    ) -> Optional[ResultRace]:
        parser = HTMLParser(html)

        venue = self._extract_atr_venue(parser)
        if not venue:
            return None

        race_num = 1
        url_match = re.search(r"/R(\d+)$", url)
        if url_match:
            race_num = int(url_match.group(1))

        runners = self._parse_atr_runners(parser)

        # Dividends — use the shared exotic extractor on the
        # dedicated dividends table, then enrich with place payouts
        div_table = parser.css_first(".result-racecard__dividends-table")
        exotics: Dict[str, Tuple[Optional[float], Optional[str]]] = {}
        if div_table:
            exotics = extract_exotic_payouts([div_table])
            self._map_place_payouts(div_table, runners)

        if not runners:
            return None

        tri = exotics.get("trifecta", (None, None))
        sup = exotics.get("superfecta", (None, None))

        return ResultRace(
            id=self._make_race_id("atr_res", venue, date_str, race_num),
            venue=venue,
            race_number=race_num,
            start_time=build_start_time(date_str),
            runners=runners,
            trifecta_payout=tri[0],
            trifecta_combination=tri[1],
            superfecta_payout=sup[0],
            superfecta_combination=sup[1],
            source=self.SOURCE_NAME,
        )

    # -- ATR-specific helpers ----------------------------------------------

    @staticmethod
    def _extract_atr_venue(parser: HTMLParser) -> Optional[str]:
        header = (
            parser.css_first(".race-header__details--primary")
            or parser.css_first(".racecard-header")
            or parser.css_first(".race-header")
        )
        if not header:
            return None
        venue_node = (
            header.css_first("h2")
            or header.css_first("h1")
            or header.css_first(".track-name")
        )
        if not venue_node:
            return None
        return normalize_venue_name(venue_node.text(strip=True))

    def _parse_atr_runners(
        self, parser: HTMLParser,
    ) -> List[ResultRunner]:
        rows = (
            parser.css(".result-racecard__row")
            or parser.css(".card-cell--horse")
            or parser.css("atr-result-horse")
            or parser.css("div[class*='RacecardResultItem']")
            or parser.css(".p-results__item")
        )

        runners: List[ResultRunner] = []
        for row in rows:
            try:
                name_node = (
                    row.css_first(".result-racecard__horse-name a")
                    or row.css_first(".horse-name a")
                    or row.css_first("a[href*='/horse/']")
                    or row.css_first("[class*='HorseName']")
                )
                if not name_node:
                    continue
                name = clean_text(name_node.text())

                pos_node = (
                    row.css_first(".result-racecard__pos")
                    or row.css_first(".pos")
                    or row.css_first(".position")
                    or row.css_first("[class*='Position']")
                )
                pos = (
                    clean_text(pos_node.text()) if pos_node else None
                )

                num_node = row.css_first(
                    ".result-racecard__saddle-cloth",
                )
                number = 0
                if num_node:
                    try:
                        number = int(clean_text(num_node.text()))
                    except ValueError:
                        pass

                odds_node = row.css_first(".result-racecard__odds")
                final_odds = 0.0
                if odds_node:
                    final_odds = parse_fractional_odds(
                        clean_text(odds_node.text()),
                    )

                runners.append(ResultRunner(
                    name=name,
                    number=number,
                    position=pos,
                    final_win_odds=final_odds,
                ))
            except Exception:
                continue
        return runners

    @staticmethod
    def _map_place_payouts(
        div_table: Node,
        runners: List[ResultRunner],
    ) -> None:
        """Enrich runners with place payouts from the dividends table."""
        for row in div_table.css("tr"):
            try:
                row_text = row.text().lower()
                if "place" not in row_text:
                    continue
                cols = row.css("td")
                if len(cols) < 2:
                    continue
                p_name = clean_text(
                    cols[0].text().replace("Place", "").strip(),
                )
                p_val = parse_currency_value(cols[1].text())
                for runner in runners:
                    if (
                        runner.name.lower() in p_name.lower()
                        or p_name.lower() in runner.name.lower()
                    ):
                        runner.place_payout = p_val
            except Exception:
                continue
