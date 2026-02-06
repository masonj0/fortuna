import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import structlog

from ..models import ResultRace, ResultRunner, AuditResult
from ..utils.text import normalize_venue_name

DEFAULT_DB_PATH = os.environ.get("FORTUNA_DB_PATH", "hot_tips_db.json")

PLACE_POSITIONS_BY_FIELD_SIZE = {
    4: 1,   # 4 or fewer runners: only win counts
    7: 2,   # 5-7 runners: top 2
    999: 3, # 8+ runners: top 3
}


def get_canonical_venue(venue: str) -> str:
    """Normalize venue name for matching."""
    if not venue:
        return ""
    # Remove parentheticals, normalize case, strip whitespace
    canonical = re.sub(r'\s*\([^)]*\)\s*', '', venue)
    canonical = re.sub(r'[^a-zA-Z0-9]', '', canonical).lower()
    return canonical


def get_places_paid(field_size: int) -> int:
    """Determine how many places are paid based on field size."""
    for max_size, places in sorted(PLACE_POSITIONS_BY_FIELD_SIZE.items()):
        if field_size <= max_size:
            return places
    return 3  # Default


class AuditorEngine:
    """
    Matches tips from history against actual race results.
    """

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = Path(db_path)
        self.logger = structlog.get_logger(self.__class__.__name__)
        self.history: List[Dict[str, Any]] = []
        self._load_history()

    def _load_history(self) -> None:
        """Load tip history from JSON file."""
        if not self.db_path.exists():
            self.logger.info("No existing history file", path=str(self.db_path))
            return

        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                self.history = json.load(f)
            self.logger.info("Loaded tip history", count=len(self.history))
        except json.JSONDecodeError as e:
            self.logger.error("Invalid JSON in history file", error=str(e))
            self.history = []
        except IOError as e:
            self.logger.error("Failed to read history file", error=str(e))
            self.history = []

    def _save_history(self) -> None:
        """Persist tip history to JSON file."""
        try:
            # Write to temp file first, then rename (atomic operation)
            temp_path = self.db_path.with_suffix('.tmp')
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(self.history, f, indent=2, default=str)
            temp_path.replace(self.db_path)
            self.logger.debug("Saved tip history", count=len(self.history))
        except IOError as e:
            self.logger.error("Failed to save history", error=str(e))

    def get_unverified_tips(self, lookback_hours: int = 48) -> List[Dict[str, Any]]:
        """
        Returns tips that haven't been successfully audited yet.
        """
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=lookback_hours)

        unverified = []
        for tip in self.history:
            if tip.get("audit_completed"):
                continue

            start_time_raw = tip.get("start_time")
            if not start_time_raw:
                continue

            try:
                start_time = datetime.fromisoformat(str(start_time_raw))
                if start_time.tzinfo is None:
                    start_time = start_time.replace(tzinfo=timezone.utc)
            except (ValueError, TypeError):
                self.logger.warning("Invalid start_time in tip", tip_id=tip.get("race_id"))
                continue

            if cutoff < start_time < now:
                unverified.append(tip)

        return unverified

    async def audit_races(self, results: List[ResultRace]) -> List[Dict[str, Any]]:
        """
        Match results to history and update audit status.
        """
        results_map: Dict[str, ResultRace] = {}
        for r in results:
            key = self._get_race_canonical_key(r)
            results_map[key] = r

        self.logger.debug("Built results map", count=len(results_map))

        audited_tips = []
        updated = False

        for tip in self.history:
            if tip.get("audit_completed"):
                continue

            try:
                tip_key = self._get_tip_canonical_key(tip)
                if not tip_key or tip_key not in results_map:
                    continue

                result = results_map[tip_key]
                self.logger.info(
                    "Auditing tip",
                    venue=tip.get('venue'),
                    race=tip.get('race_number')
                )

                outcome = self._evaluate_tip(tip, result)
                tip.update(outcome)
                tip["audit_completed"] = True
                audited_tips.append(tip)
                updated = True

            except Exception as e:
                self.logger.error(
                    "Error during audit",
                    tip_id=tip.get("race_id"),
                    error=str(e),
                    exc_info=True
                )

        if updated:
            self._save_history()

        return audited_tips

    def _get_race_canonical_key(self, race: ResultRace) -> str:
        date_str = race.start_time.strftime('%Y%m%d')
        return f"{get_canonical_venue(race.venue)}|{date_str}|{race.race_number}"

    def _get_tip_canonical_key(self, tip: Dict[str, Any]) -> Optional[str]:
        venue = tip.get("venue")
        race_number = tip.get("race_number")
        start_time_raw = tip.get("start_time")

        if not all([venue, race_number, start_time_raw]):
            return None

        try:
            st = datetime.fromisoformat(str(start_time_raw))
            date_str = st.strftime('%Y%m%d')
            return f"{get_canonical_venue(venue)}|{date_str}|{race_number}"
        except (ValueError, TypeError):
            return None

    def _evaluate_tip(self, tip: Dict[str, Any], result: ResultRace) -> Dict[str, Any]:
        """Compare predicted selection with actual result."""
        selection_num = self._extract_selection_number(tip)

        with_position = [r for r in result.runners if r.position_numeric is not None]
        top_finishers = sorted(with_position, key=lambda x: x.position_numeric)[:5]
        actual_top_5 = [str(r.number) for r in top_finishers]

        runners_with_odds = [r for r in result.runners if r.final_win_odds is not None and r.final_win_odds > 0]
        runners_with_odds.sort(key=lambda x: x.final_win_odds)
        actual_2nd_fav_odds = (runners_with_odds[1].final_win_odds if len(runners_with_odds) >= 2 else None)

        verdict = "BURNED"
        profit = -2.00

        selection_result = next((r for r in result.runners if r.number == selection_num), None)

        if selection_result is None:
            verdict = "VOID"
            profit = 0.0
        elif selection_result.position_numeric is not None:
            active_runners = [r for r in result.runners if not r.scratched]
            places_paid = get_places_paid(len(active_runners))

            if selection_result.position_numeric <= places_paid:
                verdict = "CASHED"
                if selection_result.place_payout and selection_result.place_payout > 0:
                    profit = selection_result.place_payout - 2.00
                else:
                    odds = selection_result.final_win_odds or 2.0
                    profit = ((odds - 1.0) / 5.0) * 2.0

        return {
            "actual_top_5": ", ".join(actual_top_5),
            "actual_2nd_fav_odds": actual_2nd_fav_odds,
            "verdict": verdict,
            "net_profit": round(profit, 2),
            "selection_position": (selection_result.position_numeric if selection_result else None),
            "audit_timestamp": datetime.now(timezone.utc).isoformat(),
            "trifecta_payout": result.trifecta_payout,
            "trifecta_combination": result.trifecta_combination,
        }

    def _extract_selection_number(self, tip: Dict[str, Any]) -> Optional[int]:
        selection = tip.get("selection_number")
        if selection is not None:
            try:
                return int(selection)
            except (ValueError, TypeError):
                pass

        top_five = tip.get("top_five", "")
        if top_five:
            first = str(top_five).split(",")[0].strip()
            try:
                return int(first)
            except (ValueError, TypeError):
                pass

        return None


def generate_analytics_report(audited_tips: List[Dict[str, Any]]) -> str:
    """Generate a human-readable analytics report."""
    lines = [
        "=" * 60,
        "FORTUNA PERFORMANCE ANALYTICS REPORT",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
        "=" * 60,
        "",
    ]

    if not audited_tips:
        lines.append("No tips were audited in this run.")
        return "\n".join(lines)

    total = len(audited_tips)
    cashed = sum(1 for t in audited_tips if t.get("verdict") == "CASHED")
    burned = sum(1 for t in audited_tips if t.get("verdict") == "BURNED")
    voided = sum(1 for t in audited_tips if t.get("verdict") == "VOID")
    total_profit = sum(t.get("net_profit", 0.0) for t in audited_tips)

    strike_rate = (cashed / total * 100) if total > 0 else 0.0
    roi = (total_profit / (total * 2.0) * 100) if total > 0 else 0.0

    lines.extend([
        "SUMMARY STATISTICS",
        "-" * 40,
        f"Total Audited:    {total}",
        f"  ✅ Cashed:      {cashed}",
        f"  ❌ Burned:      {burned}",
        f"  ⚪ Voided:      {voided}",
        f"Strike Rate:      {strike_rate:.1f}%",
        f"Net Profit:       ${total_profit:+.2f} (unit $2.00)",
        f"ROI:              {roi:+.1f}%",
        "",
    ])

    tri_races = [t for t in audited_tips if t.get("trifecta_payout")]
    lines.extend([
        "TRIFECTA TRACKING",
        "-" * 40,
        f"Races with trifecta data: {len(tri_races)}",
    ])

    if tri_races:
        avg_tri = sum(t["trifecta_payout"] for t in tri_races) / len(tri_races)
        max_tri = max(t["trifecta_payout"] for t in tri_races)
        lines.extend([
            f"Average Payout:   ${avg_tri:.2f}",
            f"Maximum Payout:   ${max_tri:.2f}",
        ])
    lines.append("")

    lines.extend([
        "DETAILED AUDIT LOG",
        "-" * 40,
    ])

    for tip in sorted(audited_tips, key=lambda x: x.get("start_time", "")):
        report_date = str(tip.get("report_date", "N/A"))[:10]
        venue = tip.get("venue", "Unknown")
        race_num = tip.get("race_number", "?")
        verdict = tip.get("verdict", "?")
        profit = tip.get("net_profit", 0.0)

        emoji = "✅" if verdict == "CASHED" else "❌" if verdict == "BURNED" else "⚪"

        lines.extend([
            f"{emoji} {report_date} | {venue} R{race_num}",
            f"   Verdict: {verdict} | Profit: ${profit:+.2f}",
            f"   Actual Top 5: [{tip.get('actual_top_5', 'N/A')}]",
        ])

        if tip.get("trifecta_payout"):
            lines.append(
                f"   Trifecta: {tip.get('trifecta_combination')} paid ${tip['trifecta_payout']:.2f}"
            )
        lines.append("")

    return "\n".join(lines)
