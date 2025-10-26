# python_service/api.py

import os
from contextlib import asynccontextmanager
from datetime import date
from datetime import datetime
from datetime import timedelta
from typing import List
from typing import Optional

import aiosqlite
import structlog
from fastapi import Depends
from fastapi import FastAPI
from fastapi import HTTPException
from fastapi import Query
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from .analyzer import AnalyzerEngine
from .config import get_settings
from .engine import FortunaEngine
from .health import router as health_router
from .logging_config import configure_logging
from .middleware.error_handler import validation_exception_handler
from .models import AggregatedResponse
from .models import QualifiedRacesResponse
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable

class UserFriendlyErrorMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable
    ):
        try:
            return await call_next(request)
        except Exception as e:
            # Log the exception here if you have a logger configured
            return JSONResponse(
                status_code=500,
                content={"detail": "An unexpected error occurred."},
            )
from .models import Race
from .models import TipsheetRace
from .security import verify_api_key

# --- PyInstaller Explicit Imports ---
# These imports are not used directly in this file but are required
# to ensure PyInstaller bundles all necessary adapter modules.
from .adapters import *
# ------------------------------------

log = structlog.get_logger()


# Define the lifespan context manager for robust startup/shutdown
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage the application's lifespan. On startup, it initializes the OddsEngine
    with validated settings and attaches it to the app state. On shutdown, it
    properly closes the engine's resources.
    """
    configure_logging()
    log.info("Server startup sequence initiated.")
    try:
        settings = get_settings()
        app.state.engine = FortunaEngine(config=settings)
        app.state.analyzer_engine = AnalyzerEngine()
        log.info("Server startup: Configuration validated and FortunaEngine initialized successfully.")
    except Exception as e:
        log.critical("FATAL: Failed to initialize FortunaEngine during server startup.", exc_info=True)
        # Re-raise the exception to ensure FastAPI's startup failure handling is triggered
        raise e

    yield

    # Clean up the engine resources
    if hasattr(app.state, 'engine') and app.state.engine:
        log.info("Server shutdown: Closing HTTP client resources.")
        await app.state.engine.close()
    log.info("Server shutdown sequence complete.")


limiter = Limiter(key_func=get_remote_address)

# Pass the lifespan manager to the FastAPI app
app = FastAPI(
    title="Fortuna Faucet API",
    version="2.1",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# Add the new error handling middleware FIRST, to catch exceptions from all other middleware
app.add_middleware(SlowAPIMiddleware)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

settings = get_settings()

# Add middlewares (order can be important)
app.include_router(health_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)


# Dependency function to get the engine instance from the app state
def get_engine(request: Request) -> FortunaEngine:
    return request.app.state.engine


@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.get("/api/adapters/status")
@limiter.limit("60/minute")
async def get_all_adapter_statuses(
    request: Request, engine: FortunaEngine = Depends(get_engine), _=Depends(verify_api_key)
):
    """Provides a list of health statuses for all adapters, required by the new frontend blueprint."""
    try:
        statuses = engine.get_all_adapter_statuses()
        return statuses
    except Exception:
        log.error("Error in /api/adapters/status", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


@app.get(
    "/api/races/qualified/{analyzer_name}",
    response_model=QualifiedRacesResponse,
    description=(
        "Fetch and analyze races from all configured data sources, returning a list of races "
        "that meet the specified analyzer's criteria."
    ),
    responses={
        200: {
            "description": "A list of qualified races with their scores.",
            "content": {
                "application/json": {
                    "example": {
                        "races": [
                            {
                                "id": "12345_2025-10-14_1",
                                "venue": "Santa Anita",
                                "race_number": 1,
                                "start_time": "2025-10-14T20:30:00Z",
                                "runners": [{"number": 1, "name": "Speedy Gonzalez", "odds": "5/2"}],
                                "source": "TVG",
                                "qualification_score": 95.5,
                            }
                        ],
                        "analyzer": "trifecta_analyzer",
                    }
                }
            },
        },
        404: {"description": "The specified analyzer was not found."},
    },
)
@limiter.limit("120/minute")
async def get_qualified_races(
    analyzer_name: str,
    request: Request,
    race_date: Optional[date] = None,
    engine: FortunaEngine = Depends(get_engine),
    _=Depends(verify_api_key),
    # --- Dynamic Analyzer Parameters ---
    max_field_size: int = Query(10, ge=3, le=20),
    min_favorite_odds: float = Query(2.5, ge=1.0, le=100.0),
    min_second_favorite_odds: float = Query(4.0, ge=1.0, le=100.0),
):
    """
    Gets all races for a given date, filters them for qualified betting
    opportunities, and returns the qualified races.
    """
    try:
        if race_date is None:
            race_date = datetime.now().date()
        date_str = race_date.strftime("%Y-%m-%d")
        background_tasks = set()  # Dummy background tasks
        aggregated_data = await engine.get_races(date_str, background_tasks)

        races = aggregated_data.get("races", [])

        analyzer_engine = request.app.state.analyzer_engine
        custom_params = {
            "max_field_size": max_field_size,
            "min_favorite_odds": min_favorite_odds,
            "min_second_favorite_odds": min_second_favorite_odds
        }

        analyzer = analyzer_engine.get_analyzer(analyzer_name, **custom_params)
        result = analyzer.qualify_races(races)
        return QualifiedRacesResponse(**result)
    except ValueError as e:
        log.warning("Requested analyzer not found", analyzer_name=analyzer_name)
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        log.error("Error in /api/races/qualified", error=str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


@app.get("/api/races/filter-suggestions")
async def get_filter_suggestions(engine: FortunaEngine = Depends(get_engine)):
    """
    Returns historical statistics to help users choose appropriate filter values.
    """
    try:
        # Fetch races for the past day
        date_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        aggregated = await engine.get_races(date_str, background_tasks=set())

        if not aggregated or not aggregated.get("races"):
            return {
                "suggestions": {
                    "max_field_size": {"min": 2, "max": 20, "recommended": 10},
                    "min_favorite_odds": {"min": 1.5, "max": 5, "recommended": 2.5},
                    "min_second_favorite_odds": {"min": 2.0, "max": 8, "recommended": 4.0},
                }
            }

        # Analyze field sizes
        field_sizes = [len(r["runners"]) for r in aggregated["races"]]

        # Analyze odds
        favorite_odds = []
        second_favorite_odds = []

        for race_data in aggregated["races"]:
            race = Race(**race_data) # Convert dict to Race model
            runners = race.runners
            if len(runners) >= 2:
                odds_list = []
                for runner in runners:
                    if not runner.scratched and runner.odds:
                        # Find the best (lowest) win odd from any source for the runner
                        best_odd = min(
                            (
                                o.win
                                for o in runner.odds.values()
                                if o.win is not None
                            ),
                            default=None,
                        )
                        if best_odd is not None:
                            odds_list.append(float(best_odd))

                if len(odds_list) >= 2:
                    odds_list.sort()
                    favorite_odds.append(odds_list[0])
                    second_favorite_odds.append(odds_list[1])

        return {
            "suggestions": {
                "max_field_size": {
                    "min": 2,
                    "max": 20,
                    "recommended": int(sum(field_sizes) / len(field_sizes)) if field_sizes else 10,
                    "average": sum(field_sizes) / len(field_sizes) if field_sizes else 0,
                },
                "min_favorite_odds": {
                    "min": 1.5,
                    "max": 5,
                    "recommended": 2.5,
                    "average": sum(favorite_odds) / len(favorite_odds) if favorite_odds else 0,
                },
                "min_second_favorite_odds": {
                    "min": 2.0,
                    "max": 8,
                    "recommended": 4.0,
                    "average": sum(second_favorite_odds) / len(second_favorite_odds) if second_favorite_odds else 0,
                },
            }
        }
    except Exception as e:
        log.error(f"Error generating filter suggestions: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate suggestions")


@app.get("/api/races", response_model=AggregatedResponse)
@limiter.limit("30/minute")
async def get_races(
    request: Request,
    race_date: Optional[date] = None,
    source: Optional[str] = None,
    engine: FortunaEngine = Depends(get_engine),
    _=Depends(verify_api_key),
):
    try:
        if race_date is None:
            race_date = datetime.now().date()
        date_str = race_date.strftime("%Y-%m-%d")
        background_tasks = set()  # Dummy background tasks
        aggregated_data = await engine.get_races(date_str, background_tasks, source)
        return aggregated_data
    except Exception:
        log.error("Error in /api/races", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")


DB_PATH = "fortuna.db"


def get_current_date() -> date:
    return datetime.now().date()


@app.get("/api/tipsheet", response_model=List[TipsheetRace])
@limiter.limit("30/minute")
async def get_tipsheet_endpoint(request: Request, date: date = Depends(get_current_date)):
    """Fetches the generated tipsheet from the database asynchronously."""
    results = []
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            db.row_factory = aiosqlite.Row
            query = "SELECT * FROM tipsheet WHERE date(post_time) = ? ORDER BY post_time ASC"
            async with db.execute(query, (date.isoformat(),)) as cursor:
                async for row in cursor:
                    results.append(dict(row))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    return results


@app.get("/health/legacy", tags=["Health"], summary="Check for Deprecated Legacy Components")
async def check_legacy_files():
    """
    Checks for the presence of known legacy files and returns a warning if they exist.
    This helps operators identify and clean up obsolete parts of the codebase.
    """
    legacy_files = ["checkmate_service.py", "checkmate_web/main.py"]
    present_files = [f for f in legacy_files if os.path.exists(f)]

    if present_files:
        return {
            "status": "WARNING",
            "message": "Legacy files detected. These are obsolete and should be removed.",
            "detected_files": present_files
        }

    return {"status": "CLEAN", "message": "No known legacy files detected."}
