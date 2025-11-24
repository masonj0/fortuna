# web_service/backend/api.py
# Reconstructed by Jules to merge features from python_service with web_service structure.

import asyncio
import os
import sys
from contextlib import asynccontextmanager
from typing import List, Optional

import structlog
from fastapi import Depends, FastAPI, HTTPException, Query, Request, WebSocket
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
limiter = Limiter(key_func=get_remote_address)
app = FastAPI(
    title="Fortuna Faucet Web Service API",
    version="3.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(UserFriendlyException, user_friendly_exception_handler)
app.include_router(health_router)

# Add CORS middleware for frontend development
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().ALLOWED_ORIGINS.split(','),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Robust Pathing for Frozen Executables ---
def resource_path(relative_path: str) -> str:
    """ Get absolute path to resource, works for dev and for PyInstaller """
    if getattr(sys, 'frozen', False):
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    else:
        # In development, the base path is the project root.
        # This assumes the script is run from the project root.
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


# --- Static File Serving Logic (Corrected for PyInstaller) ---
if os.getenv("FORTUNA_MODE") == "webservice":
    log.info("Application starting in 'webservice' mode, attempting to serve static files.")

    # Use the robust resource_path function to find the 'ui' directory.
    # The spec file bundles 'web_service/frontend/out' into the 'ui' folder in the executable's root.
    static_dir_key = "ui" if getattr(sys, 'frozen', False) else "web_service/frontend/out"
    static_dir = resource_path(static_dir_key)
    log.info("Resolved static files directory", path=static_dir)

    if not os.path.isdir(static_dir):
        log.error("Static files directory not found! Frontend will not be served.", path=static_dir)
    else:
        log.info("Mounting StaticFiles to serve the frontend.")
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
else:
    log.info("FORTUNA_MODE is not 'webservice', static files will not be served by this API.")


# --- Dependency Injection ---
def get_engine(request: Request) -> OddsEngine:
    if not hasattr(request.app.state, "engine") or request.app.state.engine is None:
        raise HTTPException(status_code=503, detail="The OddsEngine is not available.")
    return request.app.state.engine

# --- API Endpoints (Restored and Adapted) ---

@app.get("/api/races", response_model=AggregatedResponse)
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

@app.get("/api/races/qualified/{analyzer_name}", response_model=QualifiedRacesResponse)
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
    # This is a simplified version; a real implementation would have a dynamic analyzer engine.
    # For now, we'll just fetch and return all races as "qualified".
    response = await engine.fetch_all_odds(race_date)
    races = [Race(**r) for r in response.get("races", [])]
    return QualifiedRacesResponse(qualified_races=races, analysis_metadata={"analyzer": analyzer_name})

@app.get("/api/adapters/status")
@limiter.limit("60/minute")
async def get_all_adapter_statuses(
    request: Request,
    engine: OddsEngine = Depends(get_engine),
    _=Depends(verify_api_key),
):
    """Gets the current status of all configured data adapters."""
    return engine.get_all_adapter_statuses()

# Add other endpoints as needed, following the pattern above.
