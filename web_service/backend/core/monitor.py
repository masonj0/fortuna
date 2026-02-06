import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

import structlog

from ..models import Race, Runner
from ..utils.text import normalize_venue_name, get_canonical_venue
from ..analyzer import _get_best_win_odds
from .smart_fetcher import GlobalResourceManager

@dataclass
class RaceSummary:
    """Summary of a single race for display."""
    discipline: str  # T/H/G
    track: str
    race_number: int
    field_size: int
    superfecta_offered: bool
    adapter: str
    start_time: datetime
    mtp: Optional[int] = None  # Minutes to post
    second_fav_odds: Optional[float] = None
    second_fav_name: Optional[str] = None
    favorite_odds: Optional[float] = None
    favorite_name: Optional[str] = None
    top_five_numbers: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "discipline": self.discipline,
            "track": self.track,
            "race_number": self.race_number,
            "field_size": self.field_size,
            "superfecta_offered": self.superfecta_offered,
            "adapter": self.adapter,
            "start_time": self.start_time.isoformat(),
            "mtp": self.mtp,
            "second_fav_odds": self.second_fav_odds,
            "second_fav_name": self.second_fav_name,
            "favorite_odds": self.favorite_odds,
            "favorite_name": self.favorite_name,
            "top_five_numbers": self.top_five_numbers,
        }


class FavoriteToPlaceMonitor:
    """Monitor for favorite-to-place betting opportunities."""

    def __init__(self, engine: Any, target_dates: Optional[List[str]] = None, refresh_interval: int = 30):
        if target_dates:
            self.target_dates = target_dates
        else:
            today = datetime.now(timezone.utc)
            tomorrow = today + timedelta(days=1)
            self.target_dates = [today.strftime("%Y-%m-%d"), tomorrow.strftime("%Y-%m-%d")]

        self.refresh_interval = refresh_interval
        self.engine = engine
        self.all_races: List[RaceSummary] = []
        self.logger = structlog.get_logger(self.__class__.__name__)

    async def fetch_and_build(self):
        """Fetch races from all adapters and build summaries."""
        self.logger.info("Fetching races for monitor", dates=self.target_dates)

        all_races_raw = []
        for date_str in self.target_dates:
            # engine.fetch_all_odds returns a dict with 'races' list
            result = await self.engine.fetch_all_odds(date_str)
            races = result.get('races', [])
            all_races_raw.extend(races)

        self.logger.info("Total races fetched for monitor", count=len(all_races_raw))
        await self._build_race_summaries(all_races_raw)

    async def _build_race_summaries(self, races: List[Race]):
        """Build and deduplicate summary list."""
        race_map = {}
        for race in races:
            try:
                summary = self._create_race_summary(race)
                canonical_venue = get_canonical_venue(summary.track)
                # key = f"{canonical_venue}|{summary.race_number}"
                # Better key including date
                date_str = summary.start_time.strftime('%Y%m%d')
                key = f"{canonical_venue}|{summary.race_number}|{date_str}"

                if key not in race_map:
                    race_map[key] = summary
                else:
                    existing = race_map[key]
                    if summary.second_fav_odds and not existing.second_fav_odds:
                        race_map[key] = summary
                    elif summary.superfecta_offered and not existing.superfecta_offered:
                        race_map[key] = summary
            except:
                pass

        self.all_races = list(race_map.values())

    def _create_race_summary(self, race: Race) -> RaceSummary:
        """Create a RaceSummary from a Race object."""
        # Get active runners with valid odds
        r_with_odds = []
        for r in race.runners:
            if r.scratched: continue
            wo = _get_best_win_odds(r)
            if wo is not None and wo > 1.0:
                r_with_odds.append((r, float(wo)))

        sorted_r = sorted(r_with_odds, key=lambda x: x[1])
        top_runners = [x[0] for x in sorted_r[:5]]

        favorite = top_runners[0] if len(top_runners) >= 1 else None
        second_fav = top_runners[1] if len(top_runners) >= 2 else None
        top_five_str = "|".join([str(r.number) for r in top_runners if r.number is not None])

        # Discipline detection
        disc = "T"
        if race.discipline:
            d = race.discipline.lower()
            if "harness" in d or "standardbred" in d: disc = "H"
            elif "greyhound" in d or "dog" in d: disc = "G"

        # Superfecta check
        ab = race.metadata.get('available_bets', [])
        has_super = "Superfecta" in ab

        return RaceSummary(
            discipline=disc,
            track=normalize_venue_name(race.venue),
            race_number=race.race_number,
            field_size=len([r for r in race.runners if not r.scratched]),
            superfecta_offered=has_super,
            adapter=race.source,
            start_time=race.start_time,
            mtp=self._calculate_mtp(race.start_time),
            second_fav_odds=sorted_r[1][1] if len(sorted_r) >= 2 else None,
            second_fav_name=second_fav.name if second_fav else None,
            favorite_odds=sorted_r[0][1] if len(sorted_r) >= 1 else None,
            favorite_name=favorite.name if favorite else None,
            top_five_numbers=top_five_str,
        )

    def _calculate_mtp(self, start_time: datetime) -> Optional[int]:
        """Calculate minutes to post."""
        if not start_time: return None
        now = datetime.now(timezone.utc)
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)
        delta = start_time - now
        return int(delta.total_seconds() / 60)

    def get_bet_now_races(self) -> List[RaceSummary]:
        """Get races meeting BET NOW criteria."""
        bet_now = [
            r for r in self.all_races
            if r.mtp is not None and 0 < r.mtp <= 20
            and r.second_fav_odds is not None and r.second_fav_odds >= 5.0
            and r.field_size <= 8
        ]
        bet_now.sort(key=lambda r: (not r.superfecta_offered, r.mtp))
        return bet_now

    def get_you_might_like_races(self) -> List[RaceSummary]:
        """Get 'You Might Like' races with relaxed criteria."""
        bet_now_keys = {(r.track, r.race_number) for r in self.get_bet_now_races()}
        yml = [
            r for r in self.all_races
            if r.mtp is not None and 0 < r.mtp <= 30
            and r.second_fav_odds is not None and r.second_fav_odds >= 4.0
            and r.field_size <= 8
            and (r.track, r.race_number) not in bet_now_keys
        ]
        yml.sort(key=lambda r: r.mtp)
        return yml[:5]

    def save_to_json(self, filename: str = "race_data.json"):
        """Export to JSON and log to history."""
        bn = self.get_bet_now_races()
        yml = self.get_you_might_like_races()
        data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "target_dates": self.target_dates,
            "total_races": len(self.all_races),
            "bet_now_count": len(bn),
            "you_might_like_count": len(yml),
            "all_races": [r.to_dict() for r in self.all_races],
            "bet_now_races": [r.to_dict() for r in bn],
            "you_might_like_races": [r.to_dict() for r in yml],
        }
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)

        self._append_to_history(bn + yml)

    def _append_to_history(self, races: List[RaceSummary]):
        """Append races to persistent history."""
        if not races: return
        history_file = "prediction_history.jsonl"
        timestamp = datetime.now(timezone.utc).isoformat()
        try:
            with open(history_file, 'a') as f:
                for r in races:
                    record = r.to_dict()
                    record["logged_at"] = timestamp
                    f.write(json.dumps(record) + "\n")
        except Exception as e:
            self.logger.error("History logging failed", error=str(e))
