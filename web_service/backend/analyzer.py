from abc import ABC
from abc import abstractmethod
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type
import re
import structlog
from zoneinfo import ZoneInfo

from .models import Race, Runner, get_canonical_venue
from .utils.text import normalize_venue_name

try:
    # winsound is a built-in Windows library
    import winsound
except (ImportError, RuntimeError):
    winsound = None

EASTERN = ZoneInfo("America/New_York")
DEFAULT_ODDS_FALLBACK = 2.75

log = structlog.get_logger(__name__)


def is_placeholder_odds(value: Optional[Decimal]) -> bool:
    """Detects if odds value is a known placeholder or default."""
    if value is None:
        return True
    try:
        val_float = round(float(value), 2)
        return val_float in {2.75}
    except (ValueError, TypeError):
        return True


def is_valid_odds(odds: Any) -> bool:
    if odds is None: return False
    try:
        odds_float = float(odds)
        if not (1.01 <= odds_float < 1000.0):
            return False
        return not is_placeholder_odds(Decimal(str(odds_float)))
    except Exception: return False


def _get_best_win_odds(runner: Runner) -> Optional[Decimal]:
    """Gets the best win odds for a runner, filtering out invalid or placeholder values."""
    if not runner.odds:
        if runner.win_odds and is_valid_odds(runner.win_odds):
            return Decimal(str(runner.win_odds))

    valid_odds = []
    for source_data in runner.odds.values():
        if isinstance(source_data, dict):
            win = source_data.get('win')
        elif hasattr(source_data, 'win'):
            win = source_data.win
        else:
            win = source_data

        if is_valid_odds(win):
            valid_odds.append(Decimal(str(win)))

    if valid_odds:
        return min(valid_odds)

    if runner.win_odds and is_valid_odds(runner.win_odds):
        return Decimal(str(runner.win_odds))

    return None


class BaseAnalyzer(ABC):
    """The abstract interface for all future analyzer plugins."""

    def __init__(self, config: Optional[Dict[str, Any]] = None, **kwargs):
        self.logger = structlog.get_logger(self.__class__.__name__)
        self.config = config or {}

    @abstractmethod
    def qualify_races(self, races: List[Race]) -> Dict[str, Any]:
        """The core method every analyzer must implement."""
        pass


class TrifectaAnalyzer(BaseAnalyzer):
    """Analyzes races and assigns a qualification score based on the 'Trifecta of Factors'."""

    @property
    def name(self) -> str:
        return "trifecta_analyzer"

    def __init__(
        self,
        max_field_size: int = 14,
        min_favorite_odds: float = 0.01,
        min_second_favorite_odds: float = 0.01,
        **kwargs
    ):
        super().__init__(**kwargs)
        self.max_field_size = max_field_size
        self.min_favorite_odds = Decimal(str(min_favorite_odds))
        self.min_second_favorite_odds = Decimal(str(min_second_favorite_odds))

    def is_race_qualified(self, race: Race) -> bool:
        """A race is qualified for a trifecta if it has at least 3 non-scratched runners."""
        if not race or not race.runners:
            return False

        # Timing check: Only audit races within a reasonable window around post time
        st = race.start_time
        if st.tzinfo is None:
            # For tests/naive data, compare against naive now
            now = datetime.now()
        else:
            # For production/aware data, compare against Eastern now
            now = datetime.now(EASTERN)
            if st.tzinfo != EASTERN:
                st = st.astimezone(EASTERN)

        past_cutoff = now - timedelta(minutes=45)
        future_cutoff = now + timedelta(minutes=120)

        if st < past_cutoff or st > future_cutoff:
            return False

        active_runners = sum(1 for r in race.runners if not r.scratched)
        return active_runners >= 3

    def qualify_races(self, races: List[Race]) -> Dict[str, Any]:
        """Scores all races and returns a dictionary with criteria and a sorted list."""
        qualified_races = []
        TRUSTWORTHY_RATIO_MIN = self.config.get("analysis", {}).get("trustworthy_ratio_min", 0.7)

        for race in races:
            if not self.is_race_qualified(race):
                continue

            active_runners = [r for r in race.runners if not r.scratched]
            total_active = len(active_runners)

            if total_active > 0:
                trustworthy_count = sum(1 for r in active_runners if r.metadata.get("odds_source_trustworthy", True))
                if trustworthy_count / total_active < TRUSTWORTHY_RATIO_MIN:
                    continue

            score = self._evaluate_race(race)
            if score > 0:
                race.qualification_score = score
                qualified_races.append(race)

        qualified_races.sort(key=lambda r: r.qualification_score, reverse=True)

        criteria = {
            "max_field_size": self.max_field_size,
            "min_favorite_odds": float(self.min_favorite_odds),
            "min_second_favorite_odds": float(self.min_second_favorite_odds),
        }

        return {"criteria": criteria, "races": qualified_races}

    def _evaluate_race(self, race: Race) -> float:
        """Evaluates a single race and returns a qualification score."""
        FAV_ODDS_NORMALIZATION = 10.0
        SEC_FAV_ODDS_NORMALIZATION = 15.0
        FAV_ODDS_WEIGHT = 0.6
        SEC_FAV_ODDS_WEIGHT = 0.4
        FIELD_SIZE_SCORE_WEIGHT = 0.3
        ODDS_SCORE_WEIGHT = 0.7

        active_runners = [r for r in race.runners if not r.scratched]

        runners_with_odds = []
        for runner in active_runners:
            best_odds = _get_best_win_odds(runner)
            if best_odds is not None:
                runners_with_odds.append((runner, best_odds))

        if len(runners_with_odds) < 2:
            return 0.0

        runners_with_odds.sort(key=lambda x: x[1])
        favorite_odds = runners_with_odds[0][1]
        second_favorite_odds = runners_with_odds[1][1]

        if (
            len(active_runners) > self.max_field_size
            or favorite_odds < Decimal("2.0")
            or favorite_odds < self.min_favorite_odds
            or second_favorite_odds < self.min_second_favorite_odds
        ):
            return 0.0

        field_score = (self.max_field_size - len(active_runners)) / self.max_field_size
        fav_odds_score = min(float(favorite_odds) / FAV_ODDS_NORMALIZATION, 1.0)
        sec_fav_odds_score = min(float(second_favorite_odds) / SEC_FAV_ODDS_NORMALIZATION, 1.0)

        odds_score = (fav_odds_score * FAV_ODDS_WEIGHT) + (sec_fav_odds_score * SEC_FAV_ODDS_WEIGHT)
        final_score = (field_score * FIELD_SIZE_SCORE_WEIGHT) + (odds_score * ODDS_SCORE_WEIGHT)

        score = round(final_score * 100, 2)
        race.qualification_score = score
        return score


class TinyFieldTrifectaAnalyzer(TrifectaAnalyzer):
    """A specialized TrifectaAnalyzer that only considers races with 6 or fewer runners."""

    def __init__(self, **kwargs):
        # Override the max_field_size to 6 for "tiny field" analysis
        # Set low odds thresholds to "let them through" as per user request
        super().__init__(max_field_size=6, min_favorite_odds=0.01, min_second_favorite_odds=0.01, **kwargs)

    @property
    def name(self) -> str:
        return "tiny_field_trifecta_analyzer"


class SimplySuccessAnalyzer(BaseAnalyzer):
    """An analyzer that qualifies every race to show maximum successes (HTTP 200)."""

    @property
    def name(self) -> str:
        return "simply_success"

    def qualify_races(self, races: List[Race]) -> Dict[str, Any]:
        """Returns races with a perfect score, applying global timing and chalk filters."""
        qualified = []
        TRUSTWORTHY_RATIO_MIN = self.config.get("analysis", {}).get("trustworthy_ratio_min", 0.7)

        for race in races:
            active_runners = [r for r in race.runners if not r.scratched]
            total_active = len(active_runners)

            if total_active > 0:
                trustworthy_count = sum(1 for r in active_runners if r.metadata.get("odds_source_trustworthy", True))
                if trustworthy_count / total_active < TRUSTWORTHY_RATIO_MIN:
                    continue

            all_odds = []
            for runner in active_runners:
                odds = _get_best_win_odds(runner)
                if odds is not None:
                    runner.win_odds = float(odds)
                    all_odds.append(odds)

            all_odds.sort()

            if len(all_odds) >= 3 and len(set(all_odds)) == 1:
                continue

            if len(active_runners) < 2:
                continue

            valid_r_with_odds = sorted(
                [(r, Decimal(str(r.win_odds))) for r in active_runners if r.win_odds is not None],
                key=lambda x: x[1]
            )
            race.top_five_numbers = ", ".join([str(r[0].number or '?') for r in valid_r_with_odds[:5]])

            is_goldmine = False
            is_best_bet = False
            gap12 = 0.0

            if len(all_odds) >= 2:
                fav, sec = all_odds[0], all_odds[1]
                gap12 = round(float(sec - fav), 2)

                if gap12 > 0.25:
                    if len(active_runners) <= 11 and sec >= Decimal("4.5"):
                        is_goldmine = True
                    if len(active_runners) <= 11 and sec >= Decimal("3.5"):
                        is_best_bet = True

                race.metadata['predicted_2nd_fav_odds'] = float(sec)
                sec_fav = valid_r_with_odds[1][0]
                race.metadata['selection_number'] = sec_fav.number
                race.metadata['selection_name'] = sec_fav.name

            race.metadata['is_goldmine'] = is_goldmine
            race.metadata['is_best_bet'] = is_best_bet
            race.metadata['1Gap2'] = gap12
            race.qualification_score = 100.0
            qualified.append(race)

        return {
            "criteria": {
                "mode": "simply_success",
                "timing_filter": "45m_past_to_120m_future",
                "chalk_filter": "disabled",
                "goldmine_threshold": 4.5
            },
            "races": qualified
        }


def get_track_category(races_at_track: List[Any]) -> str:
    """Categorize the track as T (Thoroughbred), H (Harness), or G (Greyhounds)."""
    if not races_at_track:
        return 'T'

    has_large_field = False
    for r in races_at_track:
        runners = r.runners
        active_runners = len([run for run in runners if not run.scratched])
        if active_runners > 7:
            has_large_field = True
            break

    for race in races_at_track:
        source = race.source or ""
        race_id = (race.id or "").lower()
        discipline = race.discipline or ""

        if discipline == "Harness" or '_h' in race_id: return 'H'
        if (discipline == "Greyhound" or '_g' in race_id) and not has_large_field:
            return 'G'

        source_lower = source.lower()
        if ("greyhound" in source_lower or source in ["GBGB", "Greyhound", "AtTheRacesGreyhound"]) and not has_large_field:
            return 'G'
        if source in ["USTrotting", "StandardbredCanada", "Harness"] or any(kw in source_lower for kw in ['harness', 'standardbred', 'trot', 'pace']):
            return 'H'

    return 'T'


def generate_fortuna_fives(races: List[Any], all_races: Optional[List[Any]] = None) -> str:
    """Generate the FORTUNA FIVES appendix."""
    lines = ["", "", "FORTUNA FIVES", "-------------"]
    fives = []
    for race in (all_races or races):
        runners = race.runners
        field_size = len([r for r in runners if not r.scratched])
        if field_size == 5:
            fives.append(race)

    if not fives:
        lines.append("No qualifying races.")
        return "\n".join(lines)

    track_odds_sums = defaultdict(float)
    track_odds_counts = defaultdict(int)
    stats_races = all_races if all_races is not None else races
    for race in stats_races:
        v = race.venue
        track = normalize_venue_name(v)
        for runner in race.runners:
            win_odds = runner.win_odds
            if not runner.scratched and win_odds:
                track_odds_sums[track] += float(win_odds)
                track_odds_counts[track] += 1

    track_avgs = {}
    for track, total in track_odds_sums.items():
        count = track_odds_counts[track]
        if count > 0:
            track_avgs[track] = str(int(total / count))

    track_to_nums = defaultdict(list)
    for r in fives:
        v = r.venue
        if v:
            track_to_nums[normalize_venue_name(v)].append(r.race_number)

    for track in sorted(track_to_nums.keys()):
        nums = sorted(list(set(track_to_nums[track])))
        avg_str = f" [{track_avgs[track]}]" if track in track_avgs else ""
        lines.append(f"{track}{avg_str}: {', '.join(map(str, nums))}")

    return "\n".join(lines)


def generate_goldmines(races: List[Any], all_races: Optional[List[Any]] = None) -> str:
    """Generate the GOLDMINE RACES appendix, filtered to Superfecta races."""
    lines = ["", "", "GOLDMINE RACES", "--------------"]

    track_categories = {}
    source_races_for_cat = all_races if all_races is not None else races
    races_by_track = defaultdict(list)
    for r in source_races_for_cat:
        v = r.venue
        track = normalize_venue_name(v)
        races_by_track[track].append(r)
    for track, tr_races in races_by_track.items():
        track_categories[track] = get_track_category(tr_races)

    def is_superfecta_effective(r):
        available_bets = r.available_bets or []
        metadata_bets = r.metadata.get('available_bets', [])
        if 'Superfecta' in available_bets or 'Superfecta' in metadata_bets:
            return True

        track = normalize_venue_name(r.venue)
        cat = track_categories.get(track, 'T')
        runners = r.runners
        field_size = len([run for run in runners if not run.scratched])
        if cat == 'T' and field_size >= 6:
            return True
        return False

    goldmines = [r for r in races if r.metadata.get('is_goldmine') and is_superfecta_effective(r)]

    if not goldmines:
        lines.append("No qualifying races.")
        return "\n".join(lines)

    track_to_nums = defaultdict(list)
    for r in goldmines:
        v = r.venue
        if v:
            track = normalize_venue_name(v)
            track_to_nums[track].append(r.race_number)

    cat_map = {'T': 3, 'H': 2, 'G': 1}
    formatted_tracks = []
    for track in track_to_nums.keys():
        cat = track_categories.get(track, 'T')
        display_name = f"{cat}~{track}"
        formatted_tracks.append((cat, track, display_name))

    formatted_tracks.sort(key=lambda x: (-cat_map.get(x[0], 0), x[1]))

    for cat, track, display_name in formatted_tracks:
        nums = sorted(list(set(track_to_nums[track])))
        lines.append(f"{display_name}: {', '.join(map(str, nums))}")
    return "\n".join(lines)


class AnalyzerEngine:
    """Discovers and manages all available analyzer plugins."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.analyzers: Dict[str, Type[BaseAnalyzer]] = {}
        self.config = config or {}
        self._discover_analyzers()

    def _discover_analyzers(self):
        # In a real plugin system, this would inspect a folder.
        # For now, we register them manually.
        self.register_analyzer("trifecta", TrifectaAnalyzer)
        self.register_analyzer("tiny_field_trifecta", TinyFieldTrifectaAnalyzer)
        self.register_analyzer("simply_success", SimplySuccessAnalyzer)
        log.info(
            "AnalyzerEngine discovered plugins",
            available_analyzers=list(self.analyzers.keys()),
        )

    def register_analyzer(self, name: str, analyzer_class: Type[BaseAnalyzer]):
        self.analyzers[name] = analyzer_class

    def get_analyzer(self, name: str, **kwargs) -> BaseAnalyzer:
        analyzer_class = self.analyzers.get(name)
        if not analyzer_class:
            log.error("Requested analyzer not found", requested_analyzer=name)
            raise ValueError(f"Analyzer '{name}' not found.")
        return analyzer_class(config=self.config, **kwargs)


class AudioAlertSystem:
    """Plays sound alerts for important events."""

    def __init__(self):
        self.sounds = {
            "high_value": Path(__file__).resolve().parent / "assets" / "sounds" / "alert_premium.wav",
        }
        self.enabled = winsound is not None

    def play(self, sound_type: str):
        if not self.enabled:
            return

        sound_file = self.sounds.get(sound_type)
        if sound_file and sound_file.exists():
            try:
                winsound.PlaySound(str(sound_file), winsound.SND_FILENAME | winsound.SND_ASYNC)
            except Exception as e:
                log.warning("Could not play sound", file=sound_file, error=e)


class RaceNotifier:
    """Handles sending native notifications and audio alerts for high-value races."""

    def __init__(self):
        # Using a simple check for DesktopNotifier as in fortuna.py
        try:
            from notifications import DesktopNotifier
            self.notifier = DesktopNotifier()
        except ImportError:
            self.notifier = None

        self.audio_system = AudioAlertSystem()
        self.notified_races = set()
        self.notifications_enabled = self.notifier is not None
        if not self.notifications_enabled:
            log.debug("Native notifications disabled (platform not supported or library missing)")

    def notify_qualified_race(self, race):
        if race.id in self.notified_races:
            return

        # Always log the high-value opportunity regardless of notification setting
        log.info(
            "High-value opportunity identified",
            venue=race.venue,
            race=race.race_number,
            score=race.qualification_score
        )

        if not self.notifications_enabled or self.notifier is None:
            return

        title = "🐎 High-Value Opportunity!"
        message = f"{race.venue} - Race {race.race_number}\nScore: {race.qualification_score:.0f}%\nPost Time: {race.start_time.strftime('%I:%M %p')}"

        try:
            self.notifier.send(
                title=title,
                message=message,
                urgency="high" if race.qualification_score >= 80 else "normal"
            )
            self.notified_races.add(race.id)
            self.audio_system.play("high_value")
            log.info("Notification and audio alert sent for high-value race", race_id=race.id)
        except Exception as e:
            log.error("Failed to send notification", error=str(e))
