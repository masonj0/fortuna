# python_service/api.py

import os
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from typing import List, Optional

import aiosqlite
import structlog
from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable
from pydantic import BaseModel

from .analyzer import AnalyzerEngine
from .config import get_settings
from .core.exceptions import AdapterHttpError, AdapterConfigError
from .engine import OddsEngine
from .health import router as health_router
from .logging_config import configure_logging
from .middleware.error_handler import validation_exception_handler, user_friendly_exception_handler, UserFriendlyException
from .models import AggregatedResponse, QualifiedRacesResponse, Race, TipsheetRace
from .security import verify_api_key
from .manual_override_manager import ManualOverrideManager

# --- PyInstaller Explicit Imports ---
from .adapters import *
# ------------------------------------

log = structlog.get_logger()

# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    log.info("Server startup sequence initiated.")
    try:
        settings = get_settings()

        # Initialize manual override manager
        manual_override_manager = ManualOverrideManager()

        # Initialize engine with manual override support
        engine = OddsEngine(config=settings)
        for adapter in engine.adapters:
            if (hasattr(adapter, 'supports_manual_override') and
                    adapter.supports_manual_override and
                    hasattr(adapter, 'enable_manual_override')):
                adapter.enable_manual_override(manual_override_manager)

        app.state.engine = engine
        app.state.analyzer_engine = AnalyzerEngine()
        app.state.manual_override_manager = manual_override_manager

        log.info("Server startup: Configuration validated and OddsEngine initialized successfully.")
    except Exception as e:
        log.critical("FATAL: Failed to initialize OddsEngine during server startup.", exc_info=True)
        raise e
    yield
    if hasattr(app.state, 'engine') and app.state.engine:
        log.info("Server shutdown: Closing HTTP client resources.")
        await app.state.engine.close()
    log.info("Server shutdown sequence complete.")

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(
    title="Fortuna Faucet API",
    version="2.1",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

app.add_middleware(SlowAPIMiddleware)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(UserFriendlyException, user_friendly_exception_handler)
app.include_router(health_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

def get_engine(request: Request) -> OddsEngine:
    return request.app.state.engine

@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

@app.get("/api/adapters/status")
@limiter.limit("60/minute")
async def get_all_adapter_statuses(
    request: Request, engine: OddsEngine = Depends(get_engine), _=Depends(verify_api_key)
):
    try:
        return engine.get_all_adapter_statuses()
    except Exception:
        log.error("Error in /api/adapters/status", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal Server Error")

@app.get("/api/races/qualified/{analyzer_name}", response_model=QualifiedRacesResponse)
@limiter.limit("120/minute")
async def get_qualified_races(
    analyzer_name: str,
    request: Request,
    race_date: Optional[date] = Query(
        default=None,
        description="Date of the races in YYYY-MM-DD format. Defaults to today.",
    ),
    engine: OddsEngine = Depends(get_engine),
    _=Depends(verify_api_key),
    max_field_size: int = Query(10, ge=3, le=20),
    min_favorite_odds: float = Query(2.5, ge=1.0, le=100.0),
    min_second_favorite_odds: float = Query(4.0, ge=1.0, le=100.0),
):
    try:
        date_obj = race_date or datetime.now().date()
        date_str = date_obj.strftime("%Y-%m-%d")
        aggregated_data = await engine.fetch_all_odds(date_str)
        races = [Race(**r) for r in aggregated_data.get("races", [])]
        analyzer_engine = request.app.state.analyzer_engine
        custom_params = {
            "max_field_size": max_field_size,
            "min_favorite_odds": min_favorite_odds,
            "min_second_favorite_odds": min_second_favorite_odds,
        }
        analyzer = analyzer_engine.get_analyzer(analyzer_name, **custom_params)
        result = analyzer.qualify_races(races)
        return QualifiedRacesResponse(**result)
    except ValueError as e:
        log.warning("Requested analyzer not found", analyzer_name=analyzer_name)
        raise HTTPException(status_code=404, detail=str(e))
    except (AdapterHttpError, AdapterConfigError) as e:
        raise UserFriendlyException(error_key=e.__class__.__name__, details=str(e))
    except Exception:
        log.error("Error in /api/races/qualified", exc_info=True)
        raise UserFriendlyException(error_key="default")

@app.get("/api/races/filter-suggestions")
async def get_filter_suggestions(engine: OddsEngine = Depends(get_engine)):
    try:
        date_str = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        aggregated = await engine.fetch_all_odds(date_str)
        if not aggregated or not aggregated.get("races"):
            return {"suggestions": {}}
        field_sizes = [len(r["runners"]) for r in aggregated["races"]]
        favorite_odds, second_favorite_odds = [], []
        for race_data in aggregated["races"]:
            race = Race(**race_data)
            runners = race.runners
            if len(runners) >= 2:
                odds_list = []
                for runner in runners:
                    if not runner.scratched and runner.odds:
                        best_odd = min((o.win for o in runner.odds.values() if o.win is not None), default=None)
                        if best_odd is not None:
                            odds_list.append(float(best_odd))
                if len(odds_list) >= 2:
                    odds_list.sort()
                    favorite_odds.append(odds_list[0])
                    second_favorite_odds.append(odds_list[1])
        return {
            "suggestions": {
                "max_field_size": {"recommended": int(sum(field_sizes) / len(field_sizes)) if field_sizes else 10},
                "min_favorite_odds": {"recommended": 2.5},
                "min_second_favorite_odds": {"recommended": 4.0},
            }
        }
    except Exception:
        log.error("Error generating filter suggestions", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate suggestions")

@app.get("/api/races", response_model=AggregatedResponse)
@limiter.limit("30/minute")
async def get_races(
    request: Request,
    race_date: Optional[date] = Query(
        default=None,
        description="Date of the races in YYYY-MM-DD format. Defaults to today.",
    ),
    source: Optional[str] = None,
    engine: OddsEngine = Depends(get_engine),
    _=Depends(verify_api_key),
):
    try:
        date_obj = race_date or datetime.now().date()
        date_str = date_obj.strftime("%Y-%m-%d")
        return await engine.fetch_all_odds(date_str, source)
    except (AdapterHttpError, AdapterConfigError) as e:
        raise UserFriendlyException(error_key=e.__class__.__name__, details=str(e))
    except Exception:
        log.error("Error in /api/races", exc_info=True)
        raise UserFriendlyException(error_key="default")

DB_PATH = "fortuna.db"

def get_current_date() -> date:
    return datetime.now().date()

@app.get("/api/tipsheet", response_model=List[TipsheetRace])
@limiter.limit("30/minute")
async def get_tipsheet_endpoint(request: Request, date: date = Depends(get_current_date)):
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
    legacy_files = ["checkmate_service.py", "checkmate_web/main.py"]
    present_files = [f for f in legacy_files if os.path.exists(f)]
    if present_files:
        return {"status": "WARNING", "message": "Legacy files detected.", "detected_files": present_files}
    return {"status": "CLEAN", "message": "No known legacy files detected."}

# API Models
class ManualDataSubmission(BaseModel):
    request_id: str
    content: str
    content_type: str = "html"

# New endpoints
@app.get("/api/manual-overrides/pending")
async def get_pending_overrides(
    api_key: str = Depends(verify_api_key),
    manager: ManualOverrideManager = Depends(lambda: app.state.manual_override_manager)
):
    """Get all pending manual override requests"""
    pending = manager.get_pending_requests()
    return {"pending_requests": [req.model_dump() for req in pending]}

@app.post("/api/manual-overrides/submit")
async def submit_manual_data(
    submission: ManualDataSubmission,
    api_key: str = Depends(verify_api_key),
    manager: ManualOverrideManager = Depends(lambda: app.state.manual_override_manager)
):
    """Submit manually-provided data for a failed fetch"""
    success = manager.submit_manual_data(
        request_id=submission.request_id,
        raw_content=submission.content,
        content_type=submission.content_type
    )

    if success:
        return {"status": "success", "message": "Manual data submitted"}
    else:
        raise HTTPException(status_code=404, detail="Request not found")

@app.post("/api/manual-overrides/skip/{request_id}")
async def skip_manual_override(
    request_id: str,
    api_key: str = Depends(verify_api_key),
    manager: ManualOverrideManager = Depends(lambda: app.state.manual_override_manager)
):
    """Skip a manual override request"""
    success = manager.skip_request(request_id)

    if success:
        return {"status": "success", "message": "Request skipped"}
    else:
        raise HTTPException(status_code=404, detail="Request not found")

@app.post("/api/manual-overrides/cleanup")
async def cleanup_old_overrides(
    max_age_hours: int = 24,
    api_key: str = Depends(verify_api_key),
    manager: ManualOverrideManager = Depends(lambda: app.state.manual_override_manager)
):
    """Clean up old manual override requests"""
    manager.clear_old_requests(max_age_hours)
    return {"status": "success", "message": "Old requests cleaned"}
