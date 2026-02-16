# web_service/backend/core/auditor.py

import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import structlog

from ..models import ResultRace, ResultRunner, get_canonical_venue
from .database import FortunaDB, EASTERN

STANDARD_BET = 2.00

def get_places_paid(field_size: int) -> int:
    if field_size <= 4:
        return 1  # win only
    if field_size <= 7:
        return 2  # top 2
    return 3      # top 3

class AuditorEngine:
    """Matches predicted tips against actual race results using SQLite storage."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self.db = FortunaDB(db_path)
        self.logger = structlog.get_logger(self.__class__.__name__)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.close()

    async def close(self) -> None:
        await self.db.close()

    # -- data access -------------------------------------------------------

    async def get_unverified_tips(self, lookback_hours: int = 48) -> List[Dict[str, Any]]:
        return await self.db.get_unverified_tips(lookback_hours)

    async def get_all_audited_tips(self) -> List[Dict[str, Any]]:
        return await self.db.get_all_audited_tips()

    async def get_recent_tips(self, limit: int = 20) -> List[Dict[str, Any]]:
        return await self.db.get_recent_tips(limit)

    # -- audit pipeline ----------------------------------------------------

    async def audit_races(
        self,
        results: List[ResultRace],
        unverified: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        results_map = self._build_results_map(results)

        if unverified is None:
            unverified = await self.get_unverified_tips()

        audited: List[Dict[str, Any]] = []
        outcomes_to_batch: List[Tuple[str, Dict[str, Any]]] = []

        for tip in unverified:
            try:
                race_id = tip.get("race_id")
                if not race_id:
                    continue

                tip_key = self._tip_canonical_key(tip)
                if not tip_key:
                    continue

                result = self._match_tip_to_result(tip_key, results_map, race_id)
                if not result:
                    continue

                outcome = self._evaluate_tip(tip, result)
                outcomes_to_batch.append((race_id, outcome))
                audited.append({**tip, **outcome, "audit_completed": True})

            except Exception as exc:
                self.logger.error("Error during audit", tip_id=tip.get("race_id"), error=str(exc))

        if outcomes_to_batch:
            self.logger.info("Updating audit results", count=len(outcomes_to_batch))
            await self.db.update_audit_results_batch(outcomes_to_batch)

        return audited

    @staticmethod
    def _build_results_map(results: List[ResultRace]) -> Dict[str, ResultRace]:
        mapping: Dict[str, ResultRace] = {}
        for r in results:
            mapping[r.canonical_key] = r
            if r.relaxed_key != r.canonical_key:
                if r.relaxed_key not in mapping:
                    mapping[r.relaxed_key] = r
        return mapping

    def _match_tip_to_result(
        self,
        tip_key: str,
        results_map: Dict[str, ResultRace],
        race_id: str,
    ) -> Optional[ResultRace]:
        # Exact match
        result = results_map.get(tip_key)
        if result:
            return result

        parts = tip_key.split("|")

        # Fallback 1: drop time (keep discipline)
        if len(parts) >= 5:
            relaxed = f"{parts[0]}|{parts[1]}|{parts[2]}|{parts[4]}"
            result = results_map.get(relaxed)
            if result:
                return result

        # Fallback 2: drop discipline (keep time)
        if len(parts) >= 4:
            prefix = "|".join(parts[:4])
            matches = [obj for key, obj in results_map.items() if key.startswith(prefix)]
            if matches:
                return matches[0]

        return None

    @staticmethod
    def _tip_canonical_key(tip: Dict[str, Any]) -> Optional[str]:
        venue = tip.get("venue")
        race_number = tip.get("race_number")
        start_raw = tip.get("start_time")
        disc = (tip.get("discipline") or "T")[:1].upper()

        if not all([venue, race_number, start_raw]):
            return None
        try:
            st = datetime.fromisoformat(str(start_raw).replace("Z", "+00:00"))
            return (
                f"{get_canonical_venue(venue)}"
                f"|{race_number}"
                f"|{st.strftime('%Y%m%d')}"
                f"|{st.strftime('%H%M')}"
                f"|{disc}"
            )
        except (ValueError, TypeError):
            return None

    def _evaluate_tip(self, tip: Dict[str, Any], result: ResultRace) -> Dict[str, Any]:
        selection_num = self._extract_selection_number(tip)
        selection_name = tip.get("selection_name")

        top_finishers = result.get_top_finishers(5)
        actual_top_5 = [str(r.number) for r in top_finishers]

        top1_place = top_finishers[0].place_payout if len(top_finishers) >= 1 else None
        top2_place = top_finishers[1].place_payout if len(top_finishers) >= 2 else None

        actual_2nd_fav_odds = self._find_actual_2nd_fav_odds(result)

        # Find our selection in result runners
        sel_result = self._find_selection_runner(result, selection_num, selection_name)

        verdict, profit = self._compute_verdict(sel_result, result)

        return {
            "actual_top_5": ", ".join(actual_top_5),
            "actual_2nd_fav_odds": actual_2nd_fav_odds,
            "verdict": verdict,
            "net_profit": round(profit, 2),
            "selection_position": sel_result.position_numeric if sel_result else None,
            "audit_timestamp": datetime.now(EASTERN).isoformat(),
            "trifecta_payout": result.trifecta_payout,
            "trifecta_combination": result.trifecta_combination,
            "superfecta_payout": result.superfecta_payout,
            "superfecta_combination": result.superfecta_combination,
            "top1_place_payout": top1_place,
            "top2_place_payout": top2_place,
        }

    @staticmethod
    def _find_actual_2nd_fav_odds(result: ResultRace) -> Optional[float]:
        runners_list = sorted(
            (r for r in result.runners if r.final_win_odds and r.final_win_odds > 0 and not r.scratched),
            key=lambda r: r.final_win_odds,
        )
        if len(runners_list) < 2:
            return None
        fav_odds = runners_list[0].final_win_odds
        higher = [r for r in runners_list if r.final_win_odds > fav_odds]
        return higher[0].final_win_odds if higher else None

    @staticmethod
    def _find_selection_runner(
        result: ResultRace,
        number: Optional[int],
        name: Optional[str],
    ) -> Optional[ResultRunner]:
        if number is not None:
            by_num = next((r for r in result.runners if r.number == number), None)
            if by_num: return by_num
        if name:
            return next((r for r in result.runners if r.name.lower() == name.lower()), None)
        return None

    @staticmethod
    def _compute_verdict(sel: Optional[ResultRunner], result: ResultRace) -> Tuple[str, float]:
        if sel is None:
            return "VOID", 0.0
        if sel.position_numeric is None:
            return "BURNED", -STANDARD_BET

        active = [r for r in result.runners if not r.scratched]
        places_paid = get_places_paid(len(active))

        if sel.position_numeric > places_paid:
            return "BURNED", -STANDARD_BET

        # CASHED — calculate profit
        if sel.place_payout and sel.place_payout > 0:
            return "CASHED", sel.place_payout - STANDARD_BET

        # Heuristic fallback if payout missing
        odds = sel.final_win_odds or 2.75
        place_roi = max(0.1, (odds - 1.0) / 5.0)
        return "CASHED_ESTIMATED", place_roi * STANDARD_BET

    @staticmethod
    def _extract_selection_number(tip: Dict[str, Any]) -> Optional[int]:
        sel = tip.get("selection_number")
        if sel is not None:
            try:
                return int(sel)
            except (ValueError, TypeError): pass
        top_five = tip.get("top_five", "")
        if top_five:
            first = str(top_five).split(",")[0].strip()
            try:
                return int(first)
            except (ValueError, TypeError): pass
        return None
