from typing import Any, Dict, List, Optional
from datetime import datetime, timezone, date
import re
from selectolax.parser import HTMLParser

from .base_adapter_v3 import BaseAdapterV3
from .mixins import BrowserHeadersMixin, DebugMixin
from ..models import Race, Runner, OddsData
from ..utils.text import normalize_venue_name, clean_text
from ..core.smart_fetcher import FetchStrategy, BrowserEngine


class BoyleSportsAdapter(BrowserHeadersMixin, DebugMixin, BaseAdapterV3):
    SOURCE_NAME = "BoyleSports"
    BASE_URL = "https://www.boylesports.com"

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(source_name=self.SOURCE_NAME, base_url=self.BASE_URL, config=config)

    def _configure_fetch_strategy(self) -> FetchStrategy:
        return FetchStrategy(primary_engine=BrowserEngine.HTTPX, enable_js=False, timeout=30)

    def _get_headers(self) -> Dict[str, str]:
        return self._get_browser_headers(host="www.boylesports.com", referer="https://www.boylesports.com/sports/horse-racing")

    async def _fetch_data(self, date: str) -> Optional[Dict[str, Any]]:
        url = "/sports/horse-racing/race-card"
        resp = await self.make_request("GET", url, headers=self._get_headers())
        if not resp or not resp.text:
            return None
        self._save_debug_snapshot(resp.text, f"boylesports_index_{date}")
        return {"pages": [{"url": url, "html": resp.text}], "date": date}

    def _parse_races(self, raw_data: Any) -> List[Race]:
        if not raw_data or not raw_data.get("pages"):
            return []
        try:
            race_date = datetime.strptime(raw_data["date"], "%Y-%m-%d").date()
        except:
            race_date = datetime.now(timezone.utc).date()

        item = raw_data["pages"][0]
        parser = HTMLParser(item.get("html", ""))
        races: List[Race] = []
        meeting_groups = parser.css('.meeting-group') or parser.css('.race-meeting') or parser.css('div[class*="meeting"]')

        for meeting in meeting_groups:
            tnn = meeting.css_first('.meeting-name') or meeting.css_first('h2') or meeting.css_first('.title')
            if not tnn:
                continue
            trw = clean_text(tnn.text())
            track_name = normalize_venue_name(trw)
            if not track_name:
                continue

            m_harness = any(kw in trw.lower() for kw in ['harness', 'trot', 'pace', 'standardbred'])
            is_grey = any(kw in trw.lower() for kw in ['greyhound', 'dog'])

            race_nodes = meeting.css('.race-time-row') or meeting.css('.race-details') or meeting.css('a[href*="/race/"]')
            for i, rn in enumerate(race_nodes):
                txt = clean_text(rn.text())
                r_harness = m_harness or any(kw in txt.lower() for kw in ['trot', 'pace', 'attele', 'mounted'])
                tm = re.search(r'(\d{1,2}:\d{2})', txt)
                if not tm:
                    continue

                fm = re.search(r'\((\d+)\s+runners\)', txt, re.I)
                fs = int(fm.group(1)) if fm else 0
                dm = re.search(r'(\d+(?:\.\d+)?\s*[kmf]|1\s*mile)', txt, re.I)
                dist = dm.group(1) if dm else None

                try:
                    st = datetime.combine(race_date, datetime.strptime(tm.group(1), "%H:%M").time())
                    st = st.replace(tzinfo=timezone.utc)
                except:
                    continue

                runners = [Runner(number=j+1, name=f"Runner {j+1}", scratched=False, odds={}) for j in range(fs)]
                disc = "Harness" if r_harness else "Greyhound" if is_grey else "Thoroughbred"

                ab = []
                if 'superfecta' in txt.lower():
                    ab.append('Superfecta')
                elif r_harness or ' (us)' in trw.lower():
                    if fs >= 6:
                        ab.append('Superfecta')

                races.append(Race(
                    id=f"boyle_{track_name.lower().replace(' ', '')}_{st:%Y%m%d_%H%M}",
                    venue=track_name,
                    race_number=i + 1,
                    start_time=st,
                    runners=runners,
                    distance=dist,
                    source=self.SOURCE_NAME,
                    discipline=disc,
                    metadata={"available_bets": ab}
                ))
        return races
