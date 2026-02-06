from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone, date
import re
from selectolax.parser import HTMLParser

from .base_adapter_v3 import BaseAdapterV3
from .mixins import BrowserHeadersMixin, DebugMixin, RacePageFetcherMixin
from ..models import Race, Runner, OddsData
from ..utils.text import normalize_venue_name, clean_text
from ..utils.odds import parse_odds_to_decimal, SmartOddsExtractor
from ..core.smart_fetcher import FetchStrategy, BrowserEngine


class SkySportsAdapter(BrowserHeadersMixin, DebugMixin, RacePageFetcherMixin, BaseAdapterV3):
    SOURCE_NAME = "SkySports"
    BASE_URL = "https://www.skysports.com"

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(source_name=self.SOURCE_NAME, base_url=self.BASE_URL, config=config)

    def _configure_fetch_strategy(self) -> FetchStrategy:
        return FetchStrategy(primary_engine=BrowserEngine.HTTPX, enable_js=False, stealth_mode="fast", timeout=30)

    def _get_headers(self) -> Dict[str, str]:
        return self._get_browser_headers(host="www.skysports.com", referer="https://www.skysports.com/racing")

    async def _fetch_data(self, date: str) -> Optional[Dict[str, Any]]:
        try:
            dt = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            return None

        index_url = f"/racing/racecards/{dt.strftime('%d-%m-%Y')}"
        resp = await self.make_request("GET", index_url, headers=self._get_headers())
        if not resp or not resp.text:
            return None

        self._save_debug_snapshot(resp.text, f"skysports_index_{date}")
        parser = HTMLParser(resp.text)
        metadata = []
        meetings = parser.css(".sdc-site-concertina-block") or parser.css(".page-details__section") or parser.css(".racing-meetings__meeting")

        for meeting in meetings:
            hn = meeting.css_first(".sdc-site-concertina-block__title") or meeting.css_first(".racing-meetings__meeting-title")
            if not hn:
                continue
            vr = clean_text(hn.text()) or ""
            if "ABD:" in vr:
                continue
            for i, link in enumerate(meeting.css('a[href*="/racecards/"]')):
                if h := link.attributes.get("href"):
                    metadata.append({"url": h, "venue_raw": vr, "race_number": i + 1})

        if not metadata:
            return None

        pages = await self._fetch_race_pages_concurrent(metadata, self._get_headers(), semaphore_limit=10)
        return {"pages": pages, "date": date}

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
            if not html_content:
                continue
            parser = HTMLParser(html_content)
            h = parser.css_first(".sdc-site-racing-header__name")
            if not h:
                continue
            ht = clean_text(h.text()) or ""
            m = re.match(r"(\d{1,2}:\d{2})\s+(.+)", ht)
            if not m:
                tn, cn = parser.css_first(".sdc-site-racing-header__time"), parser.css_first(".sdc-site-racing-header__course")
                if tn and cn:
                    rts, tnr = clean_text(tn.text()) or "", clean_text(cn.text()) or ""
                else:
                    continue
            else:
                rts, tnr = m.group(1), m.group(2)

            track_name = normalize_venue_name(tnr)
            if not track_name:
                continue

            try:
                start_time = datetime.combine(race_date, datetime.strptime(rts, "%H:%M").time())
                start_time = start_time.replace(tzinfo=timezone.utc)
            except:
                continue

            dist = None
            for d in parser.css(".sdc-site-racing-header__detail-item"):
                dt = clean_text(d.text()) or ""
                if "Distance:" in dt:
                    dist = dt.replace("Distance:", "").strip()
                    break

            runners = []
            for i, node in enumerate(parser.css(".sdc-site-racing-card__item")):
                nn = node.css_first(".sdc-site-racing-card__name a")
                if not nn:
                    continue
                name = clean_text(nn.text())
                if not name:
                    continue

                nnode = node.css_first(".sdc-site-racing-card__number strong")
                number = i + 1
                if nnode:
                    nt = clean_text(nnode.text())
                    if nt:
                        try:
                            number = int(nt)
                        except:
                            pass

                onode = node.css_first(".sdc-site-racing-card__betting-odds")
                wo = parse_odds_to_decimal(clean_text(onode.text()) if onode else "")

                # Advanced heuristic fallback
                if wo is None:
                    wo = SmartOddsExtractor.extract_from_node(node)

                ntxt = clean_text(node.text()) or ""
                scratched = "NR" in ntxt or "Non-runner" in ntxt
                od = {}
                if wo:
                    od[self.SOURCE_NAME] = OddsData(win=wo, source=self.SOURCE_NAME, last_updated=datetime.now(timezone.utc))

                runners.append(Runner(number=number, name=name, scratched=scratched, odds=od))

            if not runners:
                continue

            # Detect discipline
            disc = "Thoroughbred"
            html_lower = html_content.lower()
            if any(kw in html_lower for kw in ["harness", "trotter", "pacer", "standardbred", "trot", "pace"]):
                disc = "Harness"
            elif any(kw in html_lower for kw in ["greyhound", "dog", "dogs"]):
                disc = "Greyhound"

            # Available bets
            ab = []
            for kw in ["superfecta", "trifecta", "exacta", "quinella"]:
                if kw in html_lower:
                    ab.append(kw.capitalize())

            if not ab and (disc == "Harness" or "(us)" in tnr.lower()) and len([r for r in runners if not r.scratched]) >= 6:
                ab.append("Superfecta")

            races.append(Race(
                id=f"sky_{track_name.lower().replace(' ', '')}_{start_time:%Y%m%d_%H%M}",
                venue=track_name,
                race_number=item.get("race_number", 0),
                start_time=start_time,
                runners=runners,
                distance=dist,
                discipline=disc,
                source=self.SOURCE_NAME,
                metadata={"available_bets": ab}
            ))
        return races
