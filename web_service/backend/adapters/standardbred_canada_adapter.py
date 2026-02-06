from typing import Any, Dict, List, Optional
from datetime import datetime, timezone, date, timedelta
import re
import asyncio
from selectolax.parser import HTMLParser

from .base_adapter_v3 import BaseAdapterV3
from .mixins import BrowserHeadersMixin, DebugMixin, RacePageFetcherMixin
from ..models import Race, Runner, OddsData
from ..utils.text import normalize_venue_name, clean_text
from ..utils.odds import parse_odds_to_decimal, SmartOddsExtractor
from ..core.smart_fetcher import FetchStrategy, BrowserEngine


class StandardbredCanadaAdapter(BrowserHeadersMixin, DebugMixin, RacePageFetcherMixin, BaseAdapterV3):
    SOURCE_NAME = "StandardbredCanada"
    BASE_URL = "https://standardbredcanada.ca"

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(source_name=self.SOURCE_NAME, base_url=self.BASE_URL, config=config)
        self._semaphore = asyncio.Semaphore(3)

    def _configure_fetch_strategy(self) -> FetchStrategy:
        return FetchStrategy(primary_engine=BrowserEngine.PLAYWRIGHT, enable_js=True, stealth_mode="fast", timeout=45)

    def _get_headers(self) -> Dict[str, str]:
        return self._get_browser_headers(host="standardbredcanada.ca", referer="https://standardbredcanada.ca/racing")

    async def _fetch_data(self, date_str: str) -> Optional[Dict[str, Any]]:
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            return None

        date_label = dt.strftime(f"%A %b {dt.day}, %Y")

        # We need playwright directly for the interactive elements if smart_fetcher's AsyncDynamicSession isn't enough
        # But let's try to use smart_fetcher first if possible, or just use playwright as fortuna.py did.
        # Given fortuna.py used playwright explicitly, I'll do the same to ensure it works.
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            self.logger.error("Playwright not installed, StandardbredCanadaAdapter cannot run.")
            return None

        index_html = None
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                try:
                    await page.goto(f"{self.base_url}/entries", wait_until="networkidle")
                    await page.evaluate("() => { document.querySelectorAll('details').forEach(d => d.open = true); }")
                    try:
                        await page.select_option("#edit-entries-track", label="View All Tracks")
                    except:
                        pass
                    try:
                        await page.select_option("#edit-entries-date", label=date_label)
                    except:
                        pass
                    try:
                        await page.click("#edit-custom-submit-entries", force=True, timeout=5000)
                    except:
                        pass
                    try:
                        await page.wait_for_selector("#entries-results-container a[href*='/entries/']", timeout=10000)
                    except:
                        pass
                    index_html = await page.content()
                finally:
                    await page.close()
                    await browser.close()
        except Exception as e:
            self.logger.error("Playwright failed in StandardbredCanadaAdapter", error=str(e))
            return None

        if not index_html:
            return None

        self._save_debug_snapshot(index_html, f"sc_index_{date_str}")
        parser = HTMLParser(index_html)
        metadata = []
        for container in parser.css("#entries-results-container .racing-results-ex-wrap > div"):
            tnn = container.css_first("h4.track-name")
            if not tnn:
                continue
            tn = clean_text(tnn.text()) or ""
            isf = "*" in tn or "*" in (clean_text(container.text()) or "")
            for link in container.css('a[href*="/entries/"]'):
                if u := link.attributes.get("href"):
                    metadata.append({"url": u, "venue": tn.replace("*", "").strip(), "finalized": isf})

        if not metadata:
            return None

        pages = await self._fetch_race_pages_concurrent(metadata, self._get_headers(), semaphore_limit=3)
        return {"pages": pages, "date": date_str}

    def _parse_races(self, raw_data: Any) -> List[Race]:
        if not raw_data or not raw_data.get("pages"):
            return []
        try:
            race_date = datetime.strptime(raw_data.get("date", ""), "%Y-%m-%d").date()
        except:
            race_date = datetime.now(timezone.utc).date()

        races: List[Race] = []
        for item in raw_data["pages"]:
            html_content = item.get("html")
            if not html_content or ("Final Changes Made" not in html_content and not item.get("finalized")):
                continue
            track_name = normalize_venue_name(item["venue"])
            for pre in HTMLParser(html_content).css("pre"):
                text = pre.text()
                race_chunks = re.split(r"(\d+)\s+--\s+", text)
                for i in range(1, len(race_chunks), 2):
                    try:
                        r = self._parse_single_race(race_chunks[i+1], int(race_chunks[i]), race_date, track_name)
                        if r:
                            races.append(r)
                    except:
                        continue
        return races

    def _parse_single_race(self, content: str, race_num: int, race_date: date, track_name: str) -> Optional[Race]:
        tm = re.search(r"Post\s+Time:\s*(\d{1,2}:\d{2}\s*[APM]{2})", content, re.I)
        st = None
        if tm:
            try:
                st = datetime.combine(race_date, datetime.strptime(tm.group(1), "%I:%M %p").time())
                st = st.replace(tzinfo=timezone.utc)
            except:
                pass
        if not st:
            st = datetime.combine(race_date, datetime.min.time()).replace(tzinfo=timezone.utc)

        # Available bets
        ab = []
        for kw in ["superfecta", "trifecta", "exacta", "quinella"]:
            if kw in content.lower():
                ab.append(kw.capitalize())

        dist = "1 Mile"
        dm = re.search(r"(\d+(?:/\d+)?\s+(?:MILE|MILES|KM|F))", content, re.I)
        if dm:
            dist = dm.group(1)

        runners = []
        for line in content.split("\n"):
            m = re.search(r"^\s*(\d+)\s+([^(]+)", line)
            if m:
                num, name = int(m.group(1)), m.group(2).strip()
                name = re.sub(r"\(L\)$|\(L\)\s+", "", name).strip()
                sc = "SCR" in line or "Scratched" in line
                # Try smarter odds extraction from the line
                wo = SmartOddsExtractor.extract_from_text(line)
                if wo is None:
                    om = re.search(r"(\d+-\d+|[0-9.]+)\s*$", line)
                    if om:
                        wo = parse_odds_to_decimal(om.group(1))

                odds_data = {}
                if wo:
                    odds_data[self.SOURCE_NAME] = OddsData(win=wo, source=self.SOURCE_NAME, last_updated=datetime.now(timezone.utc))

                runners.append(Runner(number=num, name=name, scratched=sc, odds=odds_data))

        if not runners:
            return None

        return Race(
            discipline="Harness",
            id=f"sc_{track_name.lower().replace(' ', '')}_{st:%Y%m%d_%H%M}",
            venue=track_name,
            race_number=race_num,
            start_time=st,
            runners=runners,
            distance=dist,
            source=self.SOURCE_NAME,
            metadata={"available_bets": ab}
        )
