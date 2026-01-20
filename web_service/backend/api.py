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
from fastapi.responses import FileResponse
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
# The check is now more robust, looking for any truthy value.
is_ci = os.environ.get("CI", "false").lower() in ("true", "1", "yes")
if not is_ci:
    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
else:
    # In CI, we don't want rate limiting, so we provide a no-op limiter.
    # The limiter instance is still required by endpoints even if not used.
    log.info("CI environment detected. Rate limiting is disabled.")
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


# Add other endpoints as needed, following the pattern above.

app.include_router(router, prefix="/api")

# Mount static files (frontend)
# This logic ensures that the frontend is served both in development and in the frozen executable.
static_dir = None
if getattr(sys, 'frozen', False):
    # Running in a PyInstaller bundle
    static_dir = Path(sys.executable).parent / "public"
else:
    # Running in a normal Python environment
    static_dir = Path(__file__).parent.parent.joinpath("frontend", "public")

if static_dir and static_dir.exists():
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

    @app.middleware("http")
    async def spa_middleware(request: Request, call_next):
        """
        Middleware to handle SPA routing. If a request is not for an API endpoint
        and the file is not found, it serves index.html. This is crucial for
        letting the frontend handle routing.
        """
        response = await call_next(request)
        # If a 404 is returned for a non-API, non-file path, serve the SPA index.
        if response.status_code == 404 and not request.url.path.startswith("/api/"):
            # A simple check to avoid redirecting file requests (e.g. for .css, .js)
            if "." not in request.url.path.split("/")[-1]:
                return FileResponse(static_dir / "index.html")
        return response
else:
    log.warning(f"Static frontend directory not found at '{static_dir}'. The frontend will not be served.")


# --- Adapter Management Endpoints (v3.0.0) ---

from typing import Dict, Any

adapter_router = APIRouter()

@adapter_router.get("/adapters/status", response_model=List[Dict[str, Any]])
async def get_adapter_status_v3(
    request: Request,
    engine: OddsEngine = Depends(get_engine),
):
    """
    Get status of all adapters, including whether they require API keys.
    This version is designed to be called by the adapter-aware script.
    """
    try:
        statuses = []
        for name, adapter in engine.adapters.items():
            statuses.append({
                "name": name,
                "adapter_name": name,
                "status": "active",
                "enabled": True,
                "requires_api_key": _adapter_requires_key(adapter),
                "api_key_required": _adapter_requires_key(adapter),
            })
        return statuses
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching adapter status: {str(e)}")

@adapter_router.post("/adapters/disable", response_model=Dict[str, Any])
async def disable_adapter(
    payload: Dict[str, str],
    request: Request,
    engine: OddsEngine = Depends(get_engine),
):
    """
    Disable a specific adapter at runtime.
    """
    adapter_name = payload.get("adapter_name")
    if not adapter_name:
        raise HTTPException(status_code=400, detail="adapter_name is required")

    if adapter_name not in engine.adapters:
        raise HTTPException(status_code=404, detail=f"Adapter '{adapter_name}' not found")

    if not hasattr(engine, 'disabled_adapters'):
        engine.disabled_adapters = set()
    engine.disabled_adapters.add(adapter_name)

    return {"success": True, "message": f"Adapter '{adapter_name}' disabled"}

def _adapter_requires_key(adapter) -> bool:
    """
    Helper to determine if an adapter requires an API key.
    Checks for common attributes and class name patterns.
    """
    if not adapter or not hasattr(adapter, '__class__'):
        return False

    for attr in ['api_key_required', 'requires_api_key', 'requires_key']:
        if hasattr(adapter, attr) and getattr(adapter, attr):
            return True

    key_indicators = ['betfair', 'tvg', 'equibase']
    adapter_class_name = adapter.__class__.__name__.lower()
    if any(indicator in adapter_class_name for indicator in key_indicators):
        return True

    return False

# Include the new adapter router
router.include_router(adapter_router)

# Export app for Uvicorn
__all__ = ["app"]
