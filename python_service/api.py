# python_service/api.py

import asyncio
from concurrent.futures import ThreadPoolExecutor
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
from fastapi import WebSocket
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from slowapi import Limiter
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
from starlette.websockets import WebSocketDisconnect

# --- PyInstaller Explicit Imports ---
from .analyzer import AnalyzerEngine
from .cache_manager import cache_manager
from .config import get_settings
from .core.exceptions import AdapterConfigError
from .core.exceptions import AdapterHttpError
from .engine import OddsEngine
from .health import router as health_router
from .logging_config import configure_logging
from .manual_override_manager import ManualOverrideManager
from .middleware.error_handler import UserFriendlyException
from .middleware.error_handler import user_friendly_exception_handler
from .middleware.error_handler import validation_exception_handler
from .models import AggregatedResponse
from .models import QualifiedRacesResponse
from .models import Race
from .models import TipsheetRace
from .security import verify_api_key

# ------------------------------------

log = structlog.get_logger()

# Create a fixed thread pool for blocking calls at the module level
executor = ThreadPoolExecutor(max_workers=1)


def _initialize_heavy_resources_sync(app: FastAPI):
    """
    This synchronous function contains the blocking I/O and CPU-intensive
    initialization of the OddsEngine and its ~25 adapters. By isolating it,
    we can run it in a background thread without stalling the main Uvicorn event loop.
    """
    log.info("Background initialization of heavy resources started.")
    try:
        settings = get_settings()

        # Initialize WebSocket connection manager
        connection_manager = ConnectionManager()

        # Initialize manual override manager
        manual_override_manager = ManualOverrideManager()

        # Initialize engine with manual override and WebSocket support
        engine = OddsEngine(
            config=settings,
            manual_override_manager=manual_override_manager,
            connection_manager=connection_manager,
        )

        # Store the initialized components on the app state
        app.state.engine = engine
        app.state.analyzer_engine = AnalyzerEngine()
        app.state.manual_override_manager = manual_override_manager
        app.state.connection_manager = connection_manager
        log.info("Background initialization of heavy resources completed successfully.")
    except Exception:
        log.critical("CRITICAL: Background initialization failed.", exc_info=True)
        # In a real-world scenario, you might want a more robust way
        # to signal this failure to the main application.
        app.state.engine = None


class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []
        log.info("WebSocket ConnectionManager initialized.")

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        log.info("New WebSocket connection established.")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        log.info("WebSocket connection closed.")

    async def broadcast(self, message: dict):
        """Broadcasts a message to all connected clients."""
        if not self.active_connections:
            return

        log.info(
            "Broadcasting message to connected clients",
            client_count=len(self.active_connections),
        )
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                log.error("Error sending message to a WebSocket client.", exc_info=True)


# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    log.info("Uvicorn is online, starting lifespan hook.")

    # 1. Perform lightweight, non-blocking startup tasks
    settings = get_settings()
    await cache_manager.connect(settings.REDIS_URL)
    log.info("Fast, non-blocking startup tasks complete (Redis connected).")

    # 2. Schedule the heavy, synchronous initialization to run in a background thread
    loop = asyncio.get_event_loop()
    loop.run_in_executor(executor, _initialize_heavy_resources_sync, app)
    log.info("Heavy resource initialization has been scheduled in a background thread.")

    # 3. Yield control back to Uvicorn immediately. The server is now ready to accept requests
    #    while the OddsEngine initializes in the background.
    yield

    # --- Shutdown Sequence ---
    log.info("Server shutdown sequence initiated.")
    if hasattr(app.state, "engine") and app.state.engine:
        log.info("Closing HTTP client resources.")
        await app.state.engine.close()

    await cache_manager.disconnect()
    executor.shutdown(wait=False)
    log.info("Server shutdown sequence complete.")


limiter = Limiter(key_func=get_remote_address)
app = FastAPI(
    title="Fortuna Faucet API",
    version="2.1",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
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
    request: Request,
    engine: OddsEngine = Depends(get_engine),
    _=Depends(verify_api_key),
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
                        best_odd = min(
                            (o.win for o in runner.odds.values() if o.win is not None),
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
                "max_field_size": {"recommended": (int(sum(field_sizes) / len(field_sizes)) if field_sizes else 10)},
                "min_favorite_odds": {"recommended": 2.5},
                "min_second_favorite_odds": {"recommended": 4.0},
            }
        }
    except Exception:
        log.error("Error generating filter suggestions", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate suggestions")


@app.get("/api/races/source/{source_name}", response_model=AggregatedResponse)
@limiter.limit("60/minute")
async def get_races_by_source(
    source_name: str,
    request: Request,
    race_date: Optional[date] = Query(
        default=None,
        description="Date of the races in YYYY-MM-DD format. Defaults to today.",
    ),
    engine: OddsEngine = Depends(get_engine),
    _=Depends(verify_api_key),
):
    try:
        date_obj = race_date or datetime.now().date()
        date_str = date_obj.strftime("%Y-%m-%d")
        return await engine.fetch_all_odds(date_str, source=source_name)
    except (AdapterHttpError, AdapterConfigError) as e:
        raise UserFriendlyException(error_key=e.__class__.__name__, details=str(e))
    except Exception:
        log.error(f"Error in /api/races/source/{source_name}", exc_info=True)
        raise UserFriendlyException(error_key="default")


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


# API Models
class ManualDataSubmission(BaseModel):
    request_id: str
    content: str
    content_type: str = "html"


# New endpoints
@app.get("/api/manual-overrides/pending")
@limiter.limit("60/minute")
async def get_pending_overrides(
    request: Request,
    api_key: str = Depends(verify_api_key),
    manager: ManualOverrideManager = Depends(lambda: app.state.manual_override_manager),
):
    """Get all pending manual override requests"""
    pending = manager.get_pending_requests()
    return {"pending_requests": [req.model_dump() for req in pending]}


@app.post("/api/manual-overrides/submit")
@limiter.limit("30/minute")
async def submit_manual_data(
    request: Request,
    submission: ManualDataSubmission,
    api_key: str = Depends(verify_api_key),
    manager: ManualOverrideManager = Depends(lambda: app.state.manual_override_manager),
):
    """Submit manually-provided data for a failed fetch"""
    success = manager.submit_manual_data(
        request_id=submission.request_id,
        raw_content=submission.content,
        content_type=submission.content_type,
    )

    if success:
        return {"status": "success", "message": "Manual data submitted"}
    else:
        raise HTTPException(status_code=404, detail="Request not found")


@app.post("/api/manual-overrides/skip/{request_id}")
@limiter.limit("60/minute")
async def skip_manual_override(
    request: Request,
    request_id: str,
    api_key: str = Depends(verify_api_key),
    manager: ManualOverrideManager = Depends(lambda: app.state.manual_override_manager),
):
    """Skip a manual override request"""
    success = manager.skip_request(request_id)

    if success:
        return {"status": "success", "message": "Request skipped"}
    else:
        raise HTTPException(status_code=404, detail="Request not found")


@app.post("/api/manual-overrides/cleanup")
@limiter.limit("60/minute")
async def cleanup_old_overrides(
    request: Request,
    max_age_hours: int = 24,
    api_key: str = Depends(verify_api_key),
    manager: ManualOverrideManager = Depends(lambda: app.state.manual_override_manager),
):
    """Clean up old manual override requests"""
    manager.clear_old_requests(max_age_hours)
    return {"status": "success", "message": "Old requests cleaned"}


@app.websocket("/ws/live-updates")
async def websocket_endpoint(websocket: WebSocket, api_key: str = Query(...)):
    """WebSocket endpoint for live race updates."""
    try:
        # Use the existing API key verification logic
        # This is a synchronous call, which is fine for auth at the start.
        # In a real-world scenario with high connection rates, you might
        # want to make this check asynchronous if it involved I/O.
        verify_api_key(api_key)
    except HTTPException as e:
        log.warning("WebSocket connection rejected due to invalid API key.")
        await websocket.close(code=4001, reason=f"Authentication failed: {e.detail}")
        return

    manager = websocket.app.state.connection_manager
    await manager.connect(websocket)
    try:
        # Keep the connection alive, listening for messages (if any)
        while True:
            # You could implement logic here to handle incoming messages if needed
            # For now, it's just a broadcast-only connection
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        log.info("Client disconnected from WebSocket.")
