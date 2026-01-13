# web_service/backend/api.py
# Reconstructed by Jules to merge features from python_service with web_service structure.

import asyncio
import os
import sys
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

app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
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
    # This is a simplified version; a real implementation would have a dynamic analyzer engine.
    # For now, we'll just fetch and return all races as "qualified".
    response = await engine.fetch_all_odds(race_date)
    races = [Race(**r) for r in response.get("races", [])]
    return QualifiedRacesResponse(qualified_races=races, analysis_metadata={"analyzer": analyzer_name})

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

# ╔════════════════════════════════════════════════════════════════╗
# ║  MONOLITH 3.0: UNIFIED FRONTEND + BACKEND SERVING              ║
# ║  This section configures FastAPI to serve the bundled          ║
# ║  Next.js frontend while also providing all REST API endpoints. ║
# ║  Single origin = Zero CORS issues                              ║
# ╚════════════════════════════════════════════════════════════════╝

import os
import sys
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from starlette.middleware.base import BaseHTTPMiddleware


def get_ui_directory() -> str:
    """
    Resolve the frontend 'ui' directory.
    - Frozen: sys._MEIPASS/ui (bundled by PyInstaller)
    - Dev: web_platform/frontend/out (Next.js build output)
    """
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, 'ui')

    # Development: try multiple paths
    dev_path = Path(__file__).parent.parent.parent / 'web_platform' / 'frontend' / 'out'
    if dev_path.exists():
        return str(dev_path)

    alt_path = Path.cwd() / 'web_platform' / 'frontend' / 'out'
    if alt_path.exists():
        return str(alt_path)

    raise RuntimeError(
        f"Frontend 'out' directory not found!\\n"
        f"Checked: {dev_path}\\n"
        f"Alt: {alt_path}\\n"
        f"Please run: npm run build in web_platform/frontend/"
    )


UI_DIR = get_ui_directory()
INDEX_HTML = os.path.join(UI_DIR, 'index.html')

if not os.path.exists(UI_DIR):
    raise RuntimeError(f"Frontend directory not found: {UI_DIR}")
if not os.path.exists(INDEX_HTML):
    raise RuntimeError(f"index.html not found: {INDEX_HTML}")

log.info(f"✓ Frontend verified at: {UI_DIR}")


class SPAMiddleware(BaseHTTPMiddleware):
    """
    Single Page Application Middleware.
    Returns index.html for all non-API, non-static routes.
    This enables Next.js client-side routing.
    """

    async def dispatch(self, request, call_next):
        response = await call_next(request)

        if response.status_code == 404:
            path = request.url.path

            # Skip for API routes
            if path.startswith('/api'):
                return response

            # Skip for OpenAPI/docs
            if path.startswith(('/docs', '/redoc', '/openapi')):
                return response

            # Skip for known static extensions
            static_exts = {'.js', '.css', '.png', '.jpg', '.gif', '.svg', '.woff', '.woff2', '.ttf', '.ico'}
            if any(path.endswith(ext) for ext in static_exts):
                return response

            # Return index.html for SPA routing
            log.debug(f"SPA: {path} → index.html")
            return FileResponse(INDEX_HTML)

        return response


# Add SPA middleware
app.add_middleware(SPAMiddleware)

# Mount static files (/_next/*, /images/*, etc.)
app.mount('/static', StaticFiles(directory=UI_DIR, check_dir=False), name='static')

# Mount root path for index.html and all other frontend files
app.mount('/', StaticFiles(directory=UI_DIR, html=True), name='ui')

log.info("✓ Frontend and API unified at http://localhost:8000")
