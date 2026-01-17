# web_service/backend/api.py
# Reconstructed by Jules to merge features from python_service with web_service structure.

import asyncio
import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from typing import List, Optional

import structlog
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request, WebSocket
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.websockets import WebSocketDisconnect

# Corrected imports for web_service.backend
from .config import get_settings
from .engine import OddsEngine
from .health import router as health_router
from .logging_config import configure_logging
from .middleware.error_handler import UserFriendlyException, user_friendly_exception_handler, validation_exception_handler
from .models import AggregatedResponse, QualifiedRacesResponse, Race
from .security import verify_api_key

log = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manages application startup and shutdown events."""
    configure_logging()
    log.info("Lifespan: Startup sequence initiated.")

    settings = get_settings()
    engine = OddsEngine(config=settings)
    app.state.engine = engine

    log.info("Lifespan: Engine initialized successfully. Startup complete.")
    yield
    log.info("Lifespan: Shutdown sequence initiated.")
    if hasattr(app.state, "engine") and app.state.engine:
        await app.state.engine.close()
    log.info("Lifespan: Shutdown sequence complete.")

# --- FastAPI App Initialization ---
router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(
    title="Fortuna Faucet Web Service API",
    version="3.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# Conditionally apply rate limiting middleware, disable in CI
if os.environ.get("CI") != "true":
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
else:
    # In CI, we don't want rate limiting, so we provide a no-op limiter.
    # The limiter instance is still required by endpoints even if not used.
    app.state.limiter = Limiter(key_func=get_remote_address, enabled=False)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(UserFriendlyException, user_friendly_exception_handler)
router.include_router(health_router)

# Add CORS middleware for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Dependency Injection ---
def get_engine(request: Request) -> OddsEngine:
    if not hasattr(request.app.state, "engine") or request.app.state.engine is None:
        raise HTTPException(status_code=503, detail="The OddsEngine is not available.")
    return request.app.state.engine

# --- API Endpoints (Restored and Adapted) ---

@router.get("/races", response_model=AggregatedResponse)
@limiter.limit("30/minute")
async def get_races(
    request: Request,
    race_date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format."),
    source: Optional[str] = None,
    engine: OddsEngine = Depends(get_engine),
    _=Depends(verify_api_key),
):
    """Fetches all race data for a given date from all or a specific source."""
    return await engine.fetch_all_odds(race_date, source)

@router.get("/races/qualified/tiny_field_trifecta", response_model=QualifiedRacesResponse)
@limiter.limit("120/minute")
async def get_tiny_field_trifecta_races(
    request: Request,
    race_date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format."),
    engine: OddsEngine = Depends(get_engine),
    _=Depends(verify_api_key),
):
    """Fetches all race data and runs the tiny_field_trifecta analyzer to find qualified races."""
    response = await engine.fetch_all_odds(race_date)
    races = [Race(**r) for r in response.get("races", [])]

    analyzer = engine.analyzer_engine.get_analyzer("tiny_field_trifecta")
    result = analyzer.qualify_races(races)

    return QualifiedRacesResponse(qualified_races=result.get("races", []), analysis_metadata=result.get("criteria", {}))

@router.get("/races/qualified/{analyzer_name}", response_model=QualifiedRacesResponse)
@limiter.limit("120/minute")
async def get_qualified_races(
    analyzer_name: str,
    request: Request,
    race_date: Optional[str] = Query(None, description="Date in YYYY-MM-DD format."),
    engine: OddsEngine = Depends(get_engine),
    _=Depends(verify_api_key),
    # Example query parameters for an analyzer
    max_field_size: int = Query(10, ge=3, le=20),
    min_odds: float = Query(2.0, ge=1.0),
):
    """Fetches all race data and runs a specific analyzer to find qualified races."""
    response = await engine.fetch_all_odds(race_date)
    races = [Race(**r) for r in response.get("races", [])]

    try:
        analyzer = engine.analyzer_engine.get_analyzer(analyzer_name, max_field_size=max_field_size, min_odds=min_odds)
        result = analyzer.qualify_races(races)
        return QualifiedRacesResponse(qualified_races=result.get("races", []), analysis_metadata=result.get("criteria", {}))
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Analyzer '{analyzer_name}' not found.")

@router.get("/adapters/status")
@limiter.limit("60/minute")
async def get_all_adapter_statuses(
    request: Request,
    engine: OddsEngine = Depends(get_engine),
    _=Depends(verify_api_key),
):
    """Gets the current status of all configured data adapters."""
    return engine.get_all_adapter_statuses()

# Add other endpoints as needed, following the pattern above.

app.include_router(router, prefix="/api")

# Mount static files (frontend)
try:
    if getattr(sys, 'frozen', False):
        # Running as executable
        ui_path = Path(sys.executable).parent / "ui"
    else:
        ui_path = Path(__file__).parent.parent.parent / "web_service" / "frontend" / "out"

    if ui_path.exists():
        app.mount("/", StaticFiles(directory=str(ui_path), html=True), name="static")
except Exception as e:
    print(f"⚠️  Could not mount static files: {e}")

# Export app for Uvicorn
__all__ = ["app"]
