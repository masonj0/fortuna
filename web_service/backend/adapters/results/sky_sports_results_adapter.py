from typing import Any, Dict, List, Optional, Set, Tuple
from datetime import datetime, timezone
import re
from selectolax.parser import HTMLParser, Node

from .base import (
    PageFetchingResultsAdapter,
    extract_exotic_payouts,
    parse_fractional_odds,
    build_start_time,
    _extract_race_number_from_text
)
from ...models import ResultRace, ResultRunner
from ...utils.text import normalize_venue_name, clean_text
from ...core.smart_fetcher import FetchStrategy, BrowserEngine
import fortuna


class SkySportsResultsAdapter(PageFetchingResultsAdapter):
    """Sky Sports Racing results (UK / IRE)."""

    SOURCE_NAME = "SkySportsResults"
    BASE_URL    = "https://www.skysports.com"
    HOST        = "www.skysports.com"
    IMPERSONATE = "chrome120"
    TIMEOUT     = 45

    # -- link discovery ----------------------------------------------------

    async def _discover_result_links(self, date_str: str) -> Set[str]:
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            url_dates = [dt.strftime("%d-%m-%Y")]
        except ValueError:
            url_dates = [date_str]

        links: set = set()
        for url_date in url_dates:
            try:
                resp = await self.make_request(
                    "GET", f"/racing/results/{url_date}", headers=self._get_headers(),
                )
                if not resp or not resp.text:
                    continue
                self._save_debug_snapshot(resp.text, f"sky_results_index_{url_date}")
                parser = HTMLParser(resp.text)
                links.update(self._extract_sky_links(parser, date_str, url_date))
            except Exception as exc:
                self.logger.debug("Sky index fetch failed", url_date=url_date, error=str(exc))

        return links

    def _extract_sky_links(self, parser: HTMLParser, date_str: str, url_date: str) -> set:
        links: set = set()
        # Broad selectors for SkySports results (Council of Superbrains Directive)
        for a in (parser.css("a[href*='/racing/results/']") + parser.css("a[href*='/full-result/']")):
            href = a.attributes.get("href", "")
            if not href: continue
            if not self._venue_matches(a.text(), href):
                continue

            # Match various result path patterns
            has_race_path = any(
                p in href for p in ("/full-result/", "/race-result/", "/results/full-result/")
            ) or re.search(r"/\d{6,}/", href)

            # Check if link belongs to requested date or is generally a result link
            has_date = date_str in href or url_date in href or re.search(r"/\d{6,}/", href)

            if has_race_path and has_date:
                links.add(href)
        return links

    # -- page parsing ------------------------------------------------------

    def _parse_race_page(
        self, html: str, date_str: str, url: str,
    ) -> Optional[ResultRace]:
        parser = HTMLParser(html)

        header = parser.css_first(".sdc-site-racing-header__name")
        if not header:
            return None

        match = re.match(
            r"(\d{1,2}:\d{2})\s+(.+)",
            clean_text(header.text()),
        )
        if not match:
            return None

        time_str   = match.group(1)
        venue      = normalize_venue_name(match.group(2))
        start_time = build_start_time(date_str, time_str)

        runners = self._parse_sky_runners(parser)
        if not runners:
            return None

        exotics  = extract_exotic_payouts(parser.css("table"))
        race_num = self._extract_sky_race_number(parser, url)

        tri = exotics.get("trifecta", (None, None))
        sup = exotics.get("superfecta", (None, None))

        return ResultRace(
            id=self._make_race_id("sky_res", venue, date_str, race_num),
            venue=venue,
            race_number=race_num,
            start_time=start_time,
            runners=runners,
            trifecta_payout=tri[0],
            superfecta_payout=sup[0],
            source=self.SOURCE_NAME,
        )

    @staticmethod
    def _parse_sky_runners(parser: HTMLParser) -> List[ResultRunner]:
        runners: List[ResultRunner] = []
        for row in parser.css(".sdc-site-racing-card__item"):
            name_node = row.css_first(".sdc-site-racing-card__name")
            if not name_node:
                continue

            pos_node    = row.css_first(".sdc-site-racing-card__position")
            number_node = row.css_first(".sdc-site-racing-card__number")
            odds_node   = row.css_first(".sdc-site-racing-card__odds")

            number = 0
            if number_node:
                try:
                    number = int(re.sub(r"\D", "", number_node.text()))
                except (ValueError, TypeError):
                    pass

            runners.append(ResultRunner(
                name=clean_text(name_node.text()),
                number=number,
                position=(
                    clean_text(pos_node.text()) if pos_node else None
                ),
                final_win_odds=parse_fractional_odds(
                    clean_text(odds_node.text()) if odds_node else "",
                ),
            ))
        return runners

    @staticmethod
    def _extract_sky_race_number(parser: HTMLParser, url: str) -> int:
        """Try navigation index, then URL ID, then text fallback."""
        url_match = re.search(r"/(\d+)/", url)
        if url_match:
            nav_links = parser.css("a[href*='/racing/results/']")
            for i, link in enumerate(nav_links):
                if url_match.group(0) in (
                    link.attributes.get("href") or ""
                ):
                    return i + 1

        return _extract_race_number_from_text(parser, url) or 1
