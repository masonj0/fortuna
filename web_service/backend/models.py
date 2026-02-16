# python_service/models.py

from datetime import datetime, date, timezone
from decimal import Decimal
import re
from typing import Annotated, Any, Callable, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, WrapSerializer, model_validator


def decimal_serializer(value: Decimal, handler: Callable[[Decimal], Any]) -> Any:
    """Custom serializer for Decimal to float conversion."""
    return float(value)


JsonDecimal = Annotated[Decimal, WrapSerializer(decimal_serializer, when_used="json")]


# --- Configuration for Aliases (BUG #4 Fix) ---
class FortunaBaseModel(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True,
    )


# --- Core Data Models ---
class OddsData(FortunaBaseModel):
    win: Optional[JsonDecimal] = None
    place: Optional[JsonDecimal] = None
    show: Optional[JsonDecimal] = None
    source: str
    last_updated: datetime


class Runner(FortunaBaseModel):
    id: Optional[str] = None
    name: str
    number: Optional[int] = Field(None, alias="saddleClothNumber")
    scratched: bool = False
    odds: Dict[str, OddsData] = Field(default_factory=dict)
    win_odds: Optional[float] = Field(None, alias="winOdds")
    jockey: Optional[str] = None
    trainer: Optional[str] = None
    metadata: Dict[str, Any] = {}


class Race(FortunaBaseModel):
    id: str
    venue: str
    race_number: int = Field(..., alias="raceNumber")
    start_time: datetime = Field(..., alias="startTime")
    runners: List[Runner]
    source: str
    field_size: Optional[int] = None
    qualification_score: Optional[float] = Field(None, alias="qualificationScore")
    favorite: Optional[Runner] = None
    race_name: Optional[str] = None
    distance: Optional[str] = None
    is_error_placeholder: bool = Field(False, alias="isErrorPlaceholder")
    error_message: Optional[str] = Field(None, alias="errorMessage")
    top_five_numbers: Optional[str] = Field(None, alias="topFiveNumbers")
    metadata: Dict[str, Any] = {}


class SourceInfo(FortunaBaseModel):
    name: str
    status: str
    races_fetched: int = Field(..., alias="racesFetched")
    fetch_duration: float = Field(..., alias="fetchDuration")
    error_message: Optional[str] = Field(None, alias="errorMessage")
    attempted_url: Optional[str] = Field(None, alias="attemptedUrl")


class AdapterError(FortunaBaseModel):
    adapter_name: str = Field(..., alias="adapterName")
    error_message: str = Field(..., alias="errorMessage")
    attempted_url: Optional[str] = Field(None, alias="attemptedUrl")


class AggregatedResponse(FortunaBaseModel):
    race_date: Optional[date] = Field(None, alias="date")
    races: List[Race]
    errors: List[AdapterError]
    source_info: List[SourceInfo] = Field(..., alias="sourceInfo")
    metadata: Dict[str, Any] = {}


class QualifiedRacesResponse(FortunaBaseModel):
    criteria: Dict[str, Any]
    races: List[Race]


class TipsheetRace(FortunaBaseModel):
    race_id: str = Field(..., alias="raceId")
    track_name: str = Field(..., alias="trackName")
    race_number: int = Field(..., alias="raceNumber")
    post_time: str = Field(..., alias="postTime")
    score: float
    factors: Any  # JSON string stored as Any


class ManualParseRequest(FortunaBaseModel):
    adapter_name: str
    html_content: str = Field(..., max_length=5_000_000)  # ~5MB limit


# --- Analytics Models ---

def get_canonical_venue(venue: str) -> str:
    """Normalize venue name for matching."""
    if not venue:
        return ""
    canonical = re.sub(r'\s*\([^)]*\)\s*', '', venue)
    canonical = re.sub(r'[^a-zA-Z0-9]', '', canonical).lower()
    return canonical


def parse_position(pos_str: Optional[str]) -> Optional[int]:
    """'1st' -> 1, '2/12' -> 2, 'W' -> 1, etc."""
    if not pos_str:
        return None
    s = str(pos_str).upper().strip()
    direct = {
        "W": 1, "1": 1, "1ST": 1,
        "P": 2, "2": 2, "2ND": 2,
        "S": 3, "3": 3, "3RD": 3,
        "4": 4, "4TH": 4,
        "5": 5, "5TH": 5,
    }
    if s in direct:
        return direct[s]
    m = re.search(r"^(\d+)", s)
    return int(m.group(1)) if m else None


class ResultRunner(Runner):
    """Extended runner with result information."""
    position: Optional[str] = None
    position_numeric: Optional[int] = None
    final_win_odds: Optional[float] = None
    win_payout: Optional[float] = None
    place_payout: Optional[float] = None
    show_payout: Optional[float] = None

    @model_validator(mode="after")
    def compute_position_numeric(self) -> "ResultRunner":
        if self.position and self.position_numeric is None:
            self.position_numeric = parse_position(self.position)
        return self


class ResultRace(Race):
    """Race with full result data."""
    runners: List[ResultRunner] = Field(default_factory=list)
    official_dividends: Dict[str, float] = Field(default_factory=dict)
    discipline: Optional[str] = None
    chart_url: Optional[str] = None
    is_fully_parsed: bool = False

    # Exotic bet payouts
    trifecta_payout: Optional[float] = None
    trifecta_cost: float = 1.00
    trifecta_combination: Optional[str] = None
    exacta_payout: Optional[float] = None
    exacta_combination: Optional[str] = None
    superfecta_payout: Optional[float] = None
    superfecta_combination: Optional[str] = None

    @property
    def canonical_key(self) -> str:
        d = self.start_time.strftime("%Y%m%d")
        t = self.start_time.strftime("%H%M")
        disc = (self.discipline or "T")[:1].upper()
        return f"{get_canonical_venue(self.venue)}|{self.race_number}|{d}|{t}|{disc}"

    @property
    def relaxed_key(self) -> str:
        d = self.start_time.strftime("%Y%m%d")
        disc = (self.discipline or "T")[:1].upper()
        return f"{get_canonical_venue(self.venue)}|{self.race_number}|{d}|{disc}"

    def get_top_finishers(self, n: int = 5) -> List[ResultRunner]:
        ranked = [r for r in self.runners if r.position_numeric is not None]
        ranked.sort(key=lambda r: r.position_numeric)
        return ranked[:n]


class AuditResult(FortunaBaseModel):
    """Result of auditing a tip against actual race results."""
    tip_id: str
    venue: str
    race_number: int
    verdict: str  # CASHED, BURNED, VOID, PENDING
    net_profit: float = 0.0
    selection_number: Optional[int] = None
    selection_position: Optional[int] = None
    actual_top_5: str = ""
    actual_2nd_fav_odds: Optional[float] = None
    trifecta_payout: Optional[float] = None
    trifecta_combination: Optional[str] = None
    superfecta_payout: Optional[float] = None
    superfecta_combination: Optional[str] = None
    top1_place_payout: Optional[float] = None
    top2_place_payout: Optional[float] = None
    audit_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
