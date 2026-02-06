from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import json

from .base_adapter_v3 import BaseAdapterV3
from ..models import Race, Runner, OddsData
from ..utils.text import normalize_venue_name
from ..core.smart_fetcher import FetchStrategy, BrowserEngine


class TabAdapter(BaseAdapterV3):
    SOURCE_NAME = "TAB"
    BASE_URL = "https://api.beta.tab.com.au/v1/tab-info-service/racing"

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(source_name=self.SOURCE_NAME, base_url=self.BASE_URL, config=config, rate_limit=2.0)

    def _configure_fetch_strategy(self) -> FetchStrategy:
        return FetchStrategy(primary_engine=BrowserEngine.PLAYWRIGHT, enable_js=True, stealth_mode="fast", timeout=45)

    async def _fetch_data(self, date: str) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}/dates/{date}/meetings"
        headers = {
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        }
        resp = await self.make_request("GET", url, headers=headers)
        if not resp:
            return None
        try:
            data = resp.json() if hasattr(resp, "json") else json.loads(resp.text)
        except:
            return None
        if not data or "meetings" not in data:
            return None
        return {"meetings": data["meetings"], "date": date}

    def _parse_races(self, raw_data: Any) -> List[Race]:
        if not raw_data or "meetings" not in raw_data:
            return []
        races: List[Race] = []
        for m in raw_data["meetings"]:
            vn = normalize_venue_name(m.get("meetingName"))
            mt = m.get("meetingType", "R")
            disc = {"R": "Thoroughbred", "H": "Harness", "G": "Greyhound"}.get(mt, "Thoroughbred")
            for rd in m.get("races", []):
                rn = rd.get("raceNumber")
                rst = rd.get("raceStartTime")
                if not rst:
                    continue
                try:
                    st = datetime.fromisoformat(rst.replace("Z", "+00:00"))
                except:
                    continue

                # TAB API sometimes provides runners in the meeting/race data or requires another call.
                # In the fortuna.py version, it just creates races with empty runners.
                # I'll follow that for now, but maybe we can do better if the data is there.
                runners = []

                races.append(Race(
                    id=f"tab_{vn.lower().replace(' ', '')}_{st:%Y%m%d}_R{rn}",
                    venue=vn,
                    race_number=rn,
                    start_time=st,
                    runners=runners,
                    discipline=disc,
                    source=self.SOURCE_NAME,
                    metadata={"available_bets": []}
                ))
        return races
