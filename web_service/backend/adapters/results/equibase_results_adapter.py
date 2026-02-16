from typing import Any, Dict, List, Optional, Tuple, Set
from datetime import datetime, timezone
import re
import asyncio
from selectolax.parser import HTMLParser, Node

from .base import (
    PageFetchingResultsAdapter,
    extract_exotic_payouts,
    parse_currency_value,
    build_start_time,
    EASTERN
)
from ...models import ResultRace, ResultRunner
from ...utils.text import normalize_venue_name, clean_text
from ...utils.odds import parse_odds_to_decimal
from ...core.smart_fetcher import FetchStrategy, BrowserEngine


class EquibaseResultsAdapter(PageFetchingResultsAdapter):
    """Equibase summary charts — primary US thoroughbred results source."""

    SOURCE_NAME = "EquibaseResults"
    BASE_URL    = "https://www.equibase.com"
    HOST        = "www.equibase.com"
    IMPERSONATE = "chrome120"
    TIMEOUT     = 60

    def _configure_fetch_strategy(self) -> FetchStrategy:
        # Equibase uses Instart Logic / Imperva; PLAYWRIGHT_LEGACY with network_idle is robust
        return FetchStrategy(
            primary_engine=BrowserEngine.PLAYWRIGHT, # Changed from PLAYWRIGHT_LEGACY to PLAYWRIGHT as per current project availability
            enable_js=True,
            stealth_mode="camouflage",
            timeout=self.TIMEOUT,
        )

    def _get_headers(self) -> dict:
        return {"Referer": "https://www.equibase.com/"}

    async def _discover_result_links(self, date_str: str) -> set:
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            self.logger.error("Invalid date format", date=date_str)
            return set()

        index_urls = [
            f"/static/chart/summary/index.html?SAP=TN",
            f"/static/chart/summary/index.html?date={dt.strftime('%m/%d/%Y')}",
            f"/static/chart/summary/{dt.strftime('%m%d%y')}sum.html",
            f"/static/chart/summary/{dt.strftime('%Y%m%d')}sum.html",
        ]

        resp = None
        for url in index_urls:
            # Try multiple impersonations to bypass Imperva/Cloudflare
            for imp in ["chrome120", "chrome110", "safari15_5"]:
                try:
                    resp = await self.make_request(
                        "GET", url, headers=self._get_headers(), impersonate=imp
                    )
                    if (
                        resp and resp.text
                        and len(resp.text) > 2000 # Increased threshold for real content
                        and "Pardon Our Interruption" not in resp.text
                        and "<table" in resp.text.lower() # Verify presence of data tables
                    ):
                        break
                    else:
                        resp = None
                except Exception:
                    continue
            if resp:
                break

        if not resp or not resp.text:
            self.logger.warning("No response from Equibase index", date=date_str)
            return set()

        self._save_debug_snapshot(resp.text, f"eqb_results_index_{date_str}")
        initial_links = self._extract_track_links(resp.text, dt)

        # Resolve any RaceCardIndex links to actual sum.html files
        resolved_links = set()
        index_links = [ln for ln in initial_links if "RaceCardIndex" in ln]
        sum_links = [ln for ln in initial_links if "RaceCardIndex" not in ln]

        resolved_links.update(sum_links)

        if index_links:
            self.logger.info("Resolving track indices", count=len(index_links))
            metadata = [{"url": ln, "race_number": 0} for ln in index_links]
            index_pages = await self._fetch_race_pages_concurrent(
                metadata, self._get_headers(),
            )
            for p in index_pages:
                html = p.get("html")
                if not html: continue
                # Extract all sum.html links from this track index
                date_short = dt.strftime("%m%d%y")
                for m in re.findall(r'href="([^"]+)"', html):
                    normalised = m.replace("\\/", "/").replace("\\", "/")
                    if date_short in normalised and "sum.html" in normalised:
                        resolved_links.add(self._normalise_eqb_link(normalised))
                for m in re.findall(r'"URL":"([^"]+)"', html):
                    normalised = m.replace("\\/", "/").replace("\\", "/")
                    if date_short in normalised and "sum.html" in normalised:
                        resolved_links.add(self._normalise_eqb_link(normalised))

        return resolved_links

    def _extract_track_links(self, html: str, dt: datetime) -> set:
        """Pull track-summary URLs from the index page."""
        parser = HTMLParser(html)
        raw_links: set = set()
        date_short = dt.strftime("%m%d%y")

        # Source 1 — inline JSON in <script> tags
        for url_match in re.findall(r'"URL":"([^"]+)"', html):
            normalised = url_match.replace("\\/", "/").replace("\\", "/")
            if date_short in normalised and (
                "sum.html" in normalised or "EQB.html" in normalised or "RaceCardIndex" in normalised
            ):
                raw_links.add(normalised)

        # Source 2 — <a> tags matching known patterns
        selectors_and_patterns = [
            ('table.display a[href*="sum.html"]', None),
            ('a[href*="/static/chart/summary/"]', lambda h: "index.html" not in h and "calendar.html" not in h),
            ("a", lambda h: (
                re.search(r"[A-Z]{3}\d{6}(?:sum|EQB)\.html", h)
                or (date_short in h and ("sum.html" in h.lower() or "eqb.html" in h.lower()))
            ) and "index.html" not in h and "calendar.html" not in h),
        ]
        for selector, extra_filter in selectors_and_patterns:
            for a in parser.css(selector):
                href = (a.attributes.get("href") or "").replace("\\", "/")
                if not href:
                    continue
                if extra_filter and not extra_filter(href):
                    continue
                if not self._venue_matches(a.text(), href):
                    continue
                raw_links.add(href)

        if not raw_links:
            self.logger.warning("No track links found in index", date=str(dt.date()))
            return set()

        self.logger.info("Track links extracted", count=len(raw_links))
        return {self._normalise_eqb_link(lnk) for lnk in raw_links}

    def _normalise_eqb_link(self, link: str) -> str:
        """Turn a relative Equibase link into an absolute URL."""
        if link.startswith("http"):
            return link
        path = link.lstrip("/")
        if "static/chart/summary/" not in path:
            if path.startswith("../"):
                path = "static/chart/" + path.replace("../", "")
            elif not path.startswith("static/"):
                path = f"static/chart/summary/{path}"
        path = re.sub(r"/+", "/", path)
        return f"{self.BASE_URL}/{path}"

    # -- multi-race page parsing -------------------------------------------

    def _parse_page(
        self, html: str, date_str: str, url: str,
    ) -> List[ResultRace]:
        """A track summary page contains multiple race tables."""
        parser = HTMLParser(html)

        # Venue from page header
        track_node = parser.css_first("h3") or parser.css_first("h2")
        if not track_node:
            self.logger.debug("No track header found", url=url)
            return []
        venue = normalize_venue_name(track_node.text(strip=True))
        if not venue:
            return []

        # Identify race tables and their indices among ALL tables
        all_tables = parser.css("table")
        indexed_race_tables: List[Tuple[int, Node]] = []
        for i, table in enumerate(all_tables):
            header = table.css_first("thead tr th")
            if header and "Race" in header.text():
                indexed_race_tables.append((i, table))

        races: List[ResultRace] = []
        for j, (idx, race_table) in enumerate(indexed_race_tables):
            try:
                # Dividend tables sit between this race and the next
                next_idx = (
                    indexed_race_tables[j + 1][0]
                    if j + 1 < len(indexed_race_tables)
                    else len(all_tables)
                )
                dividend_tables = all_tables[idx + 1 : next_idx]
                exotics = extract_exotic_payouts(dividend_tables)

                race = self._parse_race_table(
                    race_table, venue, date_str, exotics,
                )
                if race:
                    races.append(race)
            except Exception as exc:
                self.logger.debug(
                    "Failed to parse race table", error=str(exc),
                )
        return races

    def _parse_race_table(
        self,
        table: Node,
        venue: str,
        date_str: str,
        exotics: Dict[str, Tuple[Optional[float], Optional[str]]],
    ) -> Optional[ResultRace]:
        header = table.css_first("thead tr th")
        if not header:
            return None
        header_text = header.text()

        race_match = re.search(r"Race\s+(\d+)", header_text)
        if not race_match:
            return None
        race_num = int(race_match.group(1))

        # Start time from header or fallback
        start_time = self._parse_header_time(header_text, date_str)

        runners = [
            r for row in table.css("tbody tr")
            if (r := self._parse_runner_row(row)) is not None
        ]
        if not runners:
            return None

        tri = exotics.get("trifecta", (None, None))
        exa = exotics.get("exacta", (None, None))
        sup = exotics.get("superfecta", (None, None))

        return ResultRace(
            id=self._make_race_id("eqb_res", venue, date_str, race_num),
            venue=venue,
            race_number=race_num,
            start_time=start_time,
            runners=runners,
            source=self.SOURCE_NAME,
            is_fully_parsed=True,
            trifecta_payout=tri[0],
            trifecta_combination=tri[1],
            exacta_payout=exa[0],
            exacta_combination=exa[1],
            superfecta_payout=sup[0],
            superfecta_combination=sup[1],
        )

    @staticmethod
    def _parse_header_time(header_text: str, date_str: str) -> datetime:
        m = re.search(r"(\d{1,2}:\d{2})\s*([APM]{2})", header_text, re.I)
        if m:
            try:
                t = datetime.strptime(
                    f"{m.group(1)} {m.group(2).upper()}", "%I:%M %p",
                ).time()
                d = datetime.strptime(date_str, "%Y-%m-%d")
                return datetime.combine(d, t).replace(tzinfo=EASTERN)
            except ValueError:
                pass
        return build_start_time(date_str)

    def _parse_runner_row(self, row: Node) -> Optional[ResultRunner]:
        try:
            cols = row.css("td")
            if len(cols) < 3:
                return None

            name = clean_text(cols[2].text())
            if not name or name.upper() in ("HORSE", "NAME", "RUNNER"):
                return None

            pos_text = clean_text(cols[0].text())
            num_text = clean_text(cols[1].text())
            number = int(num_text) if num_text.isdigit() else 0

            odds_text = (
                clean_text(cols[3].text()) if len(cols) > 3 else ""
            )
            final_odds = parse_odds_to_decimal(odds_text)

            win_pay = place_pay = show_pay = 0.0
            if len(cols) >= 7:
                win_pay   = parse_currency_value(cols[4].text())
                place_pay = parse_currency_value(cols[5].text())
                show_pay  = parse_currency_value(cols[6].text())

            return ResultRunner(
                name=name,
                number=number,
                position=pos_text,
                final_win_odds=final_odds,
                win_payout=win_pay,
                place_payout=place_pay,
                show_payout=show_pay,
            )
        except Exception as exc:
            self.logger.warning(
                "Failed parsing runner row", error=str(exc),
            )
            return None
