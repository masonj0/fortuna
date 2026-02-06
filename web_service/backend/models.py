# python_service/models.py

from datetime import datetime, date, timezone
from decimal import Decimal
from typing import Annotated, Any, Callable, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, WrapSerializer


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

class ResultRunner(FortunaBaseModel):
    """Extended runner with result information."""
    name: str
    number: int = 0
    position: Optional[str] = None
    position_numeric: Optional[int] = None
    scratched: bool = False
    final_win_odds: Optional[float] = None
    win_payout: Optional[float] = None
    place_payout: Optional[float] = None
    show_payout: Optional[float] = None


class ResultRace(FortunaBaseModel):
    """Race with full result data."""
    id: str
    venue: str
    race_number: int = Field(..., alias="raceNumber")
    start_time: datetime = Field(..., alias="startTime")
    source: str
    discipline: Optional[str] = None
    runners: List[ResultRunner] = Field(default_factory=list)
    official_dividends: Dict[str, float] = Field(default_factory=dict)
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
    audit_timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
