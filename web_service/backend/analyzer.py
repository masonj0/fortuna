from abc import ABC
from abc import abstractmethod
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple
from typing import Type
import re

import structlog

from .models import Race, Runner
from .utils.text import normalize_venue_name

try:
    # winsound is a built-in Windows library
    import winsound
except ImportError:
    winsound = None
try:
    from win10toast_py3 import ToastNotifier
except (ImportError, RuntimeError):
    # Fails gracefully on non-Windows systems
    ToastNotifier = None

log = structlog.get_logger(__name__)


def _get_best_win_odds(runner: Runner) -> Optional[Decimal]:
    """Gets the best win odds for a runner, filtering out invalid or placeholder values."""
    # Check if we have already calculated and cached a valid best odds in metadata
    if "best_win_odds_decimal" in runner.metadata:
        return runner.metadata["best_win_odds_decimal"]

    if not runner.odds:
        # Fallback to win_odds if available (if we add it to Runner model, but currently it's in OddsData)
        return None

    valid_odds = []
    for source_data in runner.odds.values():
        # Handle both dict and primitive formats
        if isinstance(source_data, dict):
            win = source_data.get('win')
        elif hasattr(source_data, 'win'):
            win = source_data.win
        else:
            win = source_data

        if win is not None and 0 < win < 999:
            valid_odds.append(Decimal(str(win)))

    res = min(valid_odds) if valid_odds else None
    if res is not None:
        runner.metadata["best_win_odds_decimal"] = res
    return res


class BaseAnalyzer(ABC):
    """The abstract interface for all future analyzer plugins."""

    def __init__(self, **kwargs):
        pass

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
    ):
        self.max_field_size = max_field_size
        self.min_favorite_odds = Decimal(str(min_favorite_odds))
        self.min_second_favorite_odds = Decimal(str(min_second_favorite_odds))
        self.notifier = RaceNotifier()

    def is_race_qualified(self, race: Race) -> bool:
        """A race is qualified for a trifecta if it has at least 3 non-scratched runners."""
        if not race or not race.runners:
            return False

        active_runners = sum(1 for r in race.runners if not r.scratched)
        return active_runners >= 3

    def qualify_races(self, races: List[Race]) -> Dict[str, Any]:
        """Scores all races and returns a dictionary with criteria and a sorted list."""
        qualified_races = []
        for race in races:
            if not self.is_race_qualified(race):
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

        log.info(
            "Universal scoring complete",
            total_races_scored=len(qualified_races),
            criteria=criteria,
        )

        for race in qualified_races:
            if race.qualification_score and race.qualification_score >= 85:
                self.notifier.notify_qualified_race(race)

        return {"criteria": criteria, "races": qualified_races}

    def _evaluate_race(self, race: Race) -> float:
        """Evaluates a single race and returns a qualification score."""
        # --- Constants for Scoring Logic ---
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

        # --- Calculate Qualification Score (as inspired by the TypeScript Genesis) ---
        field_score = (self.max_field_size - len(active_runners)) / self.max_field_size

        # Normalize odds scores - cap influence of extremely high odds
        fav_odds_score = min(float(favorite_odds) / FAV_ODDS_NORMALIZATION, 1.0)
        sec_fav_odds_score = min(float(second_favorite_odds) / SEC_FAV_ODDS_NORMALIZATION, 1.0)

        # Weighted average
        odds_score = (fav_odds_score * FAV_ODDS_WEIGHT) + (sec_fav_odds_score * SEC_FAV_ODDS_WEIGHT)
        final_score = (field_score * FIELD_SIZE_SCORE_WEIGHT) + (odds_score * ODDS_SCORE_WEIGHT)

        # --- Apply hard filters before scoring ---
        if (
            len(active_runners) > self.max_field_size
            or favorite_odds < self.min_favorite_odds
            or second_favorite_odds < self.min_second_favorite_odds
        ):
            return 0.0

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
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(minutes=30)

        for race in races:
            # 1. Timing Filter: Ignore races more than 30 minutes in the past
            st = race.start_time
            if st.tzinfo is None:
                st = st.replace(tzinfo=timezone.utc)

            if st < cutoff:
                log.debug("Excluding past race", venue=race.venue, start_time=st)
                continue

            # Goldmine Detection: 2nd favorite >= 4:1 (5.0 decimal)
            # A race cannot be a goldmine if field size is over 8
            is_goldmine = False
            active_runners = [r for r in race.runners if not r.scratched]
            gap12 = 0.0
            if active_runners:
                all_odds = []
                for runner in active_runners:
                    odds = _get_best_win_odds(runner)
                    if odds is not None:
                        all_odds.append(odds)
                if len(all_odds) >= 2:
                    all_odds.sort()
                    fav, sec = all_odds[0], all_odds[1]
                    gap12 = round(float(sec - fav), 2)
                    if len(active_runners) <= 8 and sec >= 5.0:
                        is_goldmine = True

                # Calculate Top 5 for all races
                valid_r_with_odds = []
                for r in active_runners:
                    wo = _get_best_win_odds(r)
                    if wo is not None:
                        valid_r_with_odds.append((r, wo))

                r_with_odds = sorted(valid_r_with_odds, key=lambda x: x[1])
                race.top_five_numbers = ", ".join([str(r[0].number or '?') for r in r_with_odds[:5]])

            race.metadata['is_goldmine'] = is_goldmine
            race.metadata['1Gap2'] = gap12
            race.qualification_score = 100.0
            qualified.append(race)

        return {
            "criteria": {
                "mode": "simply_success",
                "timing_filter": "30m_past_cutoff",
                "chalk_filter": "disabled",
                "goldmine_threshold": 5.0
            },
            "races": qualified
        }


class AnalyzerEngine:
    """Discovers and manages all available analyzer plugins."""

    def __init__(self):
        self.analyzers: Dict[str, Type[BaseAnalyzer]] = {}
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
        return analyzer_class(**kwargs)


class AudioAlertSystem:
    """Plays sound alerts for important events."""

    def __init__(self):
        self.sounds = {
            "high_value": Path(__file__).parent.parent.parent / "assets" / "sounds" / "alert_premium.wav",
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
    """Handles sending native Windows notifications and audio alerts for high-value races."""

    def __init__(self):
        self.toaster = ToastNotifier("Fortuna") if ToastNotifier else None
        self.audio_system = AudioAlertSystem()
        self.notified_races = set()
        self.notifications_enabled = self.toaster is not None
        if not self.notifications_enabled:
            log.warning("Notifications disabled: ToastNotifier not available")

    def notify_qualified_race(self, race):
        if race.id in self.notified_races:
            return

        if not self.notifications_enabled:
            log.debug("Skipping notification: disabled", race_id=race.id)
            return

        title = "🐎 High-Value Opportunity!"
        message = f"""{race.venue} - Race {race.race_number}
Score: {race.qualification_score:.0f}%
Post Time: {race.start_time.strftime("%I:%M %p")}"""

        try:
            # The `threaded=True` argument is crucial to prevent blocking the main application thread.
            self.toaster.show_toast(title, message, duration=10, threaded=True)
            self.notified_races.add(race.id)
            self.audio_system.play("high_value")
            log.info("Notification and audio alert sent for high-value race", race_id=race.id)
        except Exception as e:
            # Catch potential exceptions from the notification library itself
            log.error("Failed to send notification", error=str(e), exc_info=True)


# --- REPORT GENERATION UTILITIES ---

def get_field(obj: Any, field_name: str, default: Any = None) -> Any:
    """Helper to get a field from either an object or a dictionary."""
    if isinstance(obj, dict):
        return obj.get(field_name, default)
    return getattr(obj, field_name, default)


def get_track_category(races_at_track: List[Any]) -> str:
    """Categorize the track as T (Thoroughbred), H (Harness), or G (Greyhounds)."""
    if not races_at_track:
        return 'T'

    # Never allow any track with a field size above 7 to be G
    has_large_field = False
    for r in races_at_track:
        runners = get_field(r, 'runners', [])
        active_runners = len([run for run in runners if not get_field(run, 'scratched', False)])
        if active_runners > 7:
            has_large_field = True
            break

    for race in races_at_track:
        source = get_field(race, 'source', '') or ""
        race_id = (get_field(race, 'id', '') or "").lower()
        discipline = get_field(race, 'discipline', '') or ""

        if discipline == "Harness" or '_h' in race_id: return 'H'
        if (discipline == "Greyhound" or '_g' in race_id) and not has_large_field:
            return 'G'

        source_lower = source.lower()
        if ("greyhound" in source_lower or source in ["GBGB", "Greyhound", "AtTheRacesGreyhound"]) and not has_large_field:
            return 'G'
        if source in ["USTrotting", "StandardbredCanada", "Harness"] or any(kw in source_lower for kw in ['harness', 'standardbred', 'trot', 'pace']):
            return 'H'

    # Distance consistency check (4 or more times at that venue)
    dist_counts = defaultdict(int)
    for r in races_at_track:
        dist = get_field(r, 'distance')
        if dist:
            dist_counts[dist] += 1
    if dist_counts and max(dist_counts.values()) >= 4:
        return 'H'

    return 'T'


def generate_fortuna_fives(races: List[Any], all_races: Optional[List[Any]] = None) -> str:
    """Generate the FORTUNA FIVES appendix."""
    lines = ["", "", "FORTUNA FIVES", "-------------"]
    fives = []
    for race in races:
        runners = get_field(race, 'runners', [])
        field_size = len([r for r in runners if not get_field(r, 'scratched', False)])
        if field_size == 5:
            fives.append(race)

    if not fives:
        lines.append("No qualifying races.")
        return "\n".join(lines)

    track_odds_sums = defaultdict(float)
    track_odds_counts = defaultdict(int)
    stats_races = all_races if all_races is not None else races
    for race in stats_races:
        v = get_field(race, 'venue')
        track = normalize_venue_name(v)
        for runner in get_field(race, 'runners', []):
            win_odds = None
            if hasattr(runner, 'odds') and runner.odds:
                # Try to get best odds
                best_odds = _get_best_win_odds(runner)
                if best_odds:
                    win_odds = float(best_odds)

            if not get_field(runner, 'scratched') and win_odds:
                track_odds_sums[track] += win_odds
                track_odds_counts[track] += 1

    track_avgs = {}
    for track, total in track_odds_sums.items():
        count = track_odds_counts[track]
        if count > 0:
            track_avgs[track] = str(int(total / count))

    track_to_nums = defaultdict(list)
    for r in fives:
        v = get_field(r, 'venue')
        if v:
            track_to_nums[normalize_venue_name(v)].append(get_field(r, 'race_number'))

    for track in sorted(track_to_nums.keys()):
        nums = sorted(list(set(track_to_nums[track])))
        avg_str = f" [{track_avgs[track]}]" if track in track_avgs else ""
        lines.append(f"{track}{avg_str}: {', '.join(map(str, nums))}")

    return "\n".join(lines)


def generate_goldmines(races: List[Any], all_races: Optional[List[Any]] = None) -> str:
    """Generate the GOLDMINE RACES appendix, filtered to Superfecta races."""
    lines = ["", "", "GOLDMINE RACES", "--------------"]

    # Pre-calculate track categories
    track_categories = {}
    source_races_for_cat = all_races if all_races is not None else races
    races_by_track = defaultdict(list)
    for r in source_races_for_cat:
        v = get_field(r, 'venue')
        track = normalize_venue_name(v)
        races_by_track[track].append(r)
    for track, tr_races in races_by_track.items():
        track_categories[track] = get_track_category(tr_races)

    def is_superfecta_effective(r):
        available_bets = get_field(r, 'available_bets', [])
        metadata = get_field(r, 'metadata', {})
        metadata_bets = metadata.get('available_bets', [])
        if 'Superfecta' in available_bets or 'Superfecta' in metadata_bets:
            return True

        track = normalize_venue_name(get_field(r, 'venue'))
        cat = track_categories.get(track, 'T')
        runners = get_field(r, 'runners', [])
        field_size = len([run for run in runners if not get_field(run, 'scratched', False)])
        if cat == 'T' and field_size >= 6:
            return True
        return False

    goldmines = [r for r in races if get_field(r, 'metadata', {}).get('is_goldmine') and is_superfecta_effective(r)]

    if not goldmines:
        lines.append("No qualifying races.")
        return "\n".join(lines)

    track_to_nums = defaultdict(list)
    for r in goldmines:
        v = get_field(r, 'venue')
        if v:
            track = normalize_venue_name(v)
            track_to_nums[track].append(get_field(r, 'race_number'))

    # Sort tracks descending by category (T > H > G)
    cat_map = {'T': 3, 'H': 2, 'G': 1}

    formatted_tracks = []
    for track in track_to_nums.keys():
        cat = track_categories.get(track, 'T')
        display_name = f"{cat}~{track}"
        formatted_tracks.append((cat, track, display_name))

    # Sort: Category Descending, then Track Name Ascending
    formatted_tracks.sort(key=lambda x: (-cat_map.get(x[0], 0), x[1]))

    for cat, track, display_name in formatted_tracks:
        nums = sorted(list(set(track_to_nums[track])))
        lines.append(f"{display_name}: {', '.join(map(str, nums))}")
    return "\n".join(lines)


def generate_goldmine_report(races: List[Any], all_races: Optional[List[Any]] = None) -> str:
    """Generate a detailed report for Goldmine races."""
    # 1. Reuse category logic
    track_categories = {}
    source_races_for_cat = all_races if all_races is not None else races
    races_by_track = defaultdict(list)
    for r in source_races_for_cat:
        v = get_field(r, 'venue')
        track = normalize_venue_name(v)
        races_by_track[track].append(r)
    for track, tr_races in races_by_track.items():
        track_categories[track] = get_track_category(tr_races)

    def is_superfecta_available(r):
        available_bets = get_field(r, 'available_bets', [])
        metadata = get_field(r, 'metadata', {})
        metadata_bets = metadata.get('available_bets', [])
        if 'Superfecta' in available_bets or 'Superfecta' in metadata_bets:
            return True
        track = normalize_venue_name(get_field(r, 'venue'))
        cat = track_categories.get(track, 'T')
        runners = get_field(r, 'runners', [])
        field_size = len([run for run in runners if not get_field(run, 'scratched', False)])
        return cat == 'T' and field_size >= 6

    # Include all goldmines (2nd fav >= 5.0)
    goldmines = [r for r in races if get_field(r, 'metadata', {}).get('is_goldmine')]

    if not goldmines:
        return "No Goldmine races found."

    # Sort goldmines: Cat descending, Track asc, Race num asc
    cat_map = {'T': 3, 'H': 2, 'G': 1}
    def goldmine_sort_key(r):
        track = normalize_venue_name(get_field(r, 'venue'))
        cat = track_categories.get(track, 'T')
        return (-cat_map.get(cat, 0), track, get_field(r, 'race_number', 0))

    goldmines.sort(key=goldmine_sort_key)

    now = datetime.now(timezone.utc)
    immediate_gold_superfecta = []
    immediate_gold = []
    remaining_gold = []

    for r in goldmines:
        start_time = get_field(r, 'start_time')
        if isinstance(start_time, str):
            try:
                start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            except ValueError:
                remaining_gold.append(r)
                continue

        if start_time:
            if start_time.tzinfo is None:
                start_time = start_time.replace(tzinfo=timezone.utc)

            diff = (start_time - now).total_seconds() / 60
            if 0 <= diff <= 20:
                if is_superfecta_available(r):
                    immediate_gold_superfecta.append(r)
                else:
                    immediate_gold.append(r)
            else:
                remaining_gold.append(r)
        else:
            remaining_gold.append(r)

    report_lines = ["LIST OF BEST BETS - GOLDMINE REPORT", "==================================", ""]

    def render_races(races_to_render, label):
        if not races_to_render:
            return
        report_lines.append(f"--- {label.upper()} ---")
        report_lines.append("-" * (len(label) + 8))
        report_lines.append("")

        for r in races_to_render:
            track = normalize_venue_name(get_field(r, 'venue'))
            cat = track_categories.get(track, 'T')
            race_num = get_field(r, 'race_number')
            start_time = get_field(r, 'start_time')
            if isinstance(start_time, datetime):
                time_str = start_time.strftime("%H:%M UTC")
            else:
                time_str = str(start_time)

            # Identify Top 5
            runners = get_field(r, 'runners', [])
            active_with_odds = []
            for run in runners:
                if get_field(run, 'scratched'): continue
                wo = _get_best_win_odds(run)
                if wo: active_with_odds.append((run, wo))

            sorted_by_odds = sorted(active_with_odds, key=lambda x: x[1])
            top_5_nums = ", ".join([str(get_field(run[0], 'number') or '?') for run in sorted_by_odds[:5]])
            if hasattr(r, 'top_five_numbers'):
                r.top_five_numbers = top_5_nums

            gap12 = get_field(r, 'metadata', {}).get('1Gap2', 0.0)
            report_lines.append(f"{cat}~{track} - Race {race_num} ({time_str})")
            report_lines.append(f"PREDICTED TOP 5: [{top_5_nums}] | 1Gap2: {gap12:.2f}")
            report_lines.append("-" * 40)

            # Sort runners by number
            sorted_runners = sorted(runners, key=lambda x: get_field(x, 'number') or 0)

            for run in sorted_runners:
                if get_field(run, 'scratched'):
                    continue
                name = get_field(run, 'name')
                num = get_field(run, 'number')

                # Extract odds for display
                win_odds = None
                best_odds = _get_best_win_odds(run)
                if best_odds:
                    win_odds = float(best_odds)

                odds_str = f"{win_odds:.2f}" if win_odds else "N/A"
                report_lines.append(f"  #{num:<2} {name:<25}  ~ {odds_str}")

            report_lines.append("")

    if immediate_gold_superfecta:
        render_races(immediate_gold_superfecta, "Immediate Gold (superfecta)")

    if immediate_gold:
        render_races(immediate_gold, "Immediate Gold")

    if remaining_gold:
        render_races(remaining_gold, "All Remaining Goldmine Races")

    return "\n".join(report_lines)


def generate_next_to_jump(races: List[Any]) -> str:
    """Generate the NEXT TO JUMP section."""
    lines = ["", "", "NEXT TO JUMP", "------------"]
    now = datetime.now(timezone.utc)
    upcoming = []
    for r in races:
        r_time = get_field(r, 'start_time')
        if isinstance(r_time, str):
            try:
                r_time = datetime.fromisoformat(r_time.replace('Z', '+00:00'))
            except ValueError:
                continue

        if r_time:
            if r_time.tzinfo is None:
                r_time = r_time.replace(tzinfo=timezone.utc)
            if r_time > now:
                upcoming.append((r, r_time))

    if upcoming:
        next_r, next_r_time = min(upcoming, key=lambda x: x[1])
        diff = next_r_time - now
        minutes = int(diff.total_seconds() / 60)
        lines.append(f"{normalize_venue_name(get_field(next_r, 'venue'))} Race {get_field(next_r, 'race_number')} in {minutes}m")
    else:
        lines.append("All races complete for today.")

    return "\n".join(lines)


def num_to_alpha(n, is_goldmine=False):
    """Convert race number to alphabetic code. Goldmines are uppercase."""
    if not isinstance(n, int) or n < 1:
        return '?'
    letter = chr(ord('a') + n - 1) if n <= 26 else str(n)
    return letter.upper() if is_goldmine else letter


def wrap_text(text, width):
    """Wrap string into a list of fixed-width segments."""
    if not text:
        return [""]
    return [text[i:i+width] for i in range(0, len(text), width)]


def format_grid_code(race_info_list, wrap_width=4):
    """
    Standardizes the formatting of race code strings for the grid.
    Includes midpoint space for readability if length exceeds 5.

    Args:
        race_info_list: List of (race_num, is_goldmine) tuples
        wrap_width: Width to wrap at
    """
    if not race_info_list:
        return [""]

    code = "".join([num_to_alpha(n, gm) for n, gm in sorted(list(set(race_info_list)))])

    # Midpoint space logic for readability (Project Convention)
    if len(code) > 5:
        mid = len(code) // 2
        code = code[:mid] + " " + code[mid:]

    return wrap_text(code, wrap_width)


def generate_summary_grid(races: List[Any], all_races: Optional[List[Any]] = None) -> str:
    """
    Generates a tiered summary grid.
    Primary section: Races with Superfectas (Explicit or T-tracks with field > 6).
    Secondary section: All remaining races.
    """
    now = datetime.now(timezone.utc)

    def is_superfecta_explicit(r):
        available_bets = get_field(r, 'available_bets', [])
        metadata = get_field(r, 'metadata', {})
        metadata_bets = metadata.get('available_bets', [])
        return 'Superfecta' in available_bets or 'Superfecta' in metadata_bets

    track_categories = {}
    all_field_sizes = set()
    WRAP_WIDTH = 4

    # 1. Pre-calculate track categories
    races_by_track = defaultdict(list)
    source_races = all_races if all_races is not None else races
    for r in source_races:
        venue = get_field(r, 'venue')
        track = normalize_venue_name(venue)
        races_by_track[track].append(r)

    for track, tr_races in races_by_track.items():
        track_categories[track] = get_track_category(tr_races)

    # 2. Partition races based on explicit Superfecta OR T-track field size rule
    primary_stats = defaultdict(lambda: defaultdict(list))
    secondary_stats = defaultdict(lambda: defaultdict(list))

    for race in races:
        track = normalize_venue_name(get_field(race, 'venue'))
        runners = get_field(race, 'runners', [])
        field_size = len([r for r in runners if not get_field(r, 'scratched', False)])
        race_num = get_field(race, 'race_number') or 0
        metadata = get_field(race, 'metadata', {})
        is_goldmine = metadata.get('is_goldmine', False)

        all_field_sizes.add(field_size)
        cat = track_categories.get(track, 'T')

        is_primary = is_superfecta_explicit(race) or (cat == 'T' and field_size >= 6)

        if is_primary:
            primary_stats[track][field_size].append((race_num, is_goldmine))
        else:
            secondary_stats[track][field_size].append((race_num, is_goldmine))

    if not all_field_sizes:
        return "\nNo races found to display in grid."

    sorted_field_sizes = sorted(list(all_field_sizes))
    cat_map = {'T': 3, 'H': 2, 'G': 1}
    col_widths = {fs: max(len(str(fs)), WRAP_WIDTH) for fs in sorted_field_sizes}

    header_parts = [f"{'CATEG':<5}", f"{'Track':<25}"]
    for fs in sorted_field_sizes:
        header_parts.append(f"{str(fs):^{col_widths[fs]}}")

    header = " | ".join(header_parts)
    grid_lines = ["\n" + header, "-" * len(header)]

    def render_stats(stats_dict, label=None):
        if not stats_dict:
            return
        if label:
            label_row = f"--- {label.upper()} ---"
            grid_lines.append(f"{label_row:^{len(header)}}")
            grid_lines.append("-" * len(header))

        sorted_tracks = sorted(stats_dict.keys(), key=lambda t: (-cat_map.get(track_categories.get(t, 'T'), 0), t))
        for track in sorted_tracks:
            wrapped_stats = {}
            max_lines = 1
            for fs in sorted_field_sizes:
                wrapped = format_grid_code(stats_dict[track].get(fs, []), WRAP_WIDTH)
                wrapped_stats[fs] = wrapped
                max_lines = max(max_lines, len(wrapped))

            for line_idx in range(max_lines):
                if line_idx == 0:
                    row_prefix = f"{track_categories.get(track, 'T'):<5} | {track[:25]:<25} | "
                else:
                    row_prefix = f"{' ':<5} | {' ':<25} | "

                row_vals = []
                for fs in sorted_field_sizes:
                    wrapped = wrapped_stats[fs]
                    val = wrapped[line_idx] if line_idx < len(wrapped) else ""
                    row_vals.append(f"{val:^{col_widths[fs]}}")

                grid_lines.append(row_prefix + " | ".join(row_vals))
            grid_lines.append("-" * len(header))

    # 3. Identify Immediate Goldmine races for prime display
    immediate_gold_super_snippet = []
    immediate_gold_snippet = []

    # We need track categories for the goldmine partitioning check
    for race in races:
        metadata = get_field(race, 'metadata', {})
        if metadata.get('is_goldmine'):
            track = normalize_venue_name(get_field(race, 'venue'))
            cat = track_categories.get(track, 'T')

            # Use same Superfecta filter as generate_goldmine_report
            available_bets = get_field(race, 'available_bets', [])
            metadata_bets = metadata.get('available_bets', [])
            runners = get_field(race, 'runners', [])
            field_size = len([run for run in runners if not get_field(run, 'scratched', False)])

            is_super = 'Superfecta' in available_bets or 'Superfecta' in metadata_bets or (cat == 'T' and field_size >= 6)

            start_time = get_field(race, 'start_time')
            if isinstance(start_time, str):
                try:
                    start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
                except ValueError:
                    start_time = None

            if start_time:
                if start_time.tzinfo is None:
                    start_time = start_time.replace(tzinfo=timezone.utc)

                diff = (start_time - now).total_seconds() / 60
                if 0 <= diff <= 20:
                    # Calculate top 5 for the snippet
                    active_runners = [run for run in runners if not get_field(run, 'scratched')]
                    active_runners.sort(key=lambda x: float(_get_best_win_odds(x) or 999.0))
                    top_five = "|".join([str(get_field(run, 'number')) for run in active_runners[:5]])

                    entry = f"{cat}~{track} R{get_field(race, 'race_number')} in {int(diff)}m [{top_five}]"
                    if is_super:
                        immediate_gold_super_snippet.append(entry)
                    else:
                        immediate_gold_snippet.append(entry)

    final_grid_lines = []
    if immediate_gold_super_snippet:
        final_grid_lines.append("!!! IMMEDIATE GOLD (SUPERFECTA) !!!")
        final_grid_lines.extend(immediate_gold_super_snippet)
        final_grid_lines.append("")
    if immediate_gold_snippet:
        final_grid_lines.append("!!! IMMEDIATE GOLD !!!")
        final_grid_lines.extend(immediate_gold_snippet)
        final_grid_lines.append("")

    # Render sections BEFORE extending final_grid_lines with grid_lines
    if primary_stats:
        render_stats(primary_stats, label="Preferred Superfecta Races")

    if secondary_stats:
        # Use label if primary also existed
        label = "All Remaining Races" if primary_stats else None
        render_stats(secondary_stats, label=label)

    final_grid_lines.extend(grid_lines)

    appendix = generate_fortuna_fives(races, all_races=all_races)
    goldmines = generate_goldmines(races, all_races=all_races)
    next_to_jump = generate_next_to_jump(races)

    # Unified spacing management (Memory Directive Fix)
    full_report = "\n".join(final_grid_lines) + appendix + goldmines + next_to_jump

    return full_report
