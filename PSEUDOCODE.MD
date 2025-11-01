# 🐎 Fortuna Faucet - Complete Pseudocode Blueprint

**Status:** Comprehensive System Specification
**Version:** 2.1.0
**Last Updated:** November 1, 2025

---

## TABLE OF CONTENTS

1. System Overview
2. Architecture Pillars
3. Backend Engine (Python)
4. Frontend Interface (TypeScript/React)
5. Electron Wrapper & Windows Integration
6. Data Models & Contracts
7. API Specification
8. Deployment & Automation
9. End-to-End Workflows

---

## 1. SYSTEM OVERVIEW

```
╔════════════════════════════════════════════════════════════════╗
║         FORTUNA FAUCET - Racing Analysis Platform             ║
║  Unifying global horse/greyhound/harness racing intelligence   ║
╚════════════════════════════════════════════════════════════════╝

MISSION:
  • Acquire race data from 20+ global sources (APIs + web scraping)
  • Normalize and deduplicate into a canonical Race format
  • Apply analytical filters (TrifectaAnalyzer) to surface opportunities
  • Serve results via a secure REST API to an interactive web dashboard
  • Operate as a professional, standalone, native Windows application

CORE TENETS:
  • Resilience: Each adapter failure is isolated; others continue fetching
  • Standardization: All adapters follow the BaseAdapterV3 pattern
  • Clarity: Every component has a single, well-defined responsibility
  • Automation: Development and deployment are streamlined via scripts and CI/CD

STAKEHOLDERS:
  • End User: Receives a professional MSI installer for one-click launch
  • Developer: Works with clean, separated Python and TypeScript stacks
```

---

## 2. ARCHITECTURE PILLARS

### Pillar 1: Backend Engine (Python)

```
PYTHON_BACKEND:
  ├─ api.py
  │  └─ FastAPI HTTP server
  │     ├─ GET /health (unauthenticated)
  │     ├─ GET /api/adapters/status (rate: 60/min)
  │     ├─ GET /api/races (aggregated data, rate: 30/min)
  │     └─ GET /api/races/qualified/{analyzer} (filtered, rate: 120/min)
  │
  ├─ engine.py
  │  └─ OddsEngine orchestrator
  │     ├─ Manages adapter fleet (instantiation, lifecycle)
  │     ├─ Parallel fetch coordination via asyncio.gather with Semaphore
  │     ├─ Race deduplication & odds merging logic
  │     └─ Shares a single httpx.AsyncClient with all adapters
  │
  ├─ cache_manager.py
  │  └─ Redis caching layer via @cache_async_result decorator
  │
  ├─ models.py
  │  └─ Pydantic data contracts (Race, Runner, OddsData)
  │
  ├─ analyzer.py
  │  └─ Analysis framework (BaseAnalyzer, TrifectaAnalyzer)
  │
  ├─ adapters/
  │  ├─ base_v3.py (BaseAdapterV3 abstract pattern: _fetch_data, _parse_races)
  │  └─ [20+ specific adapter implementations]
  │
  ├─ config.py
  │  └─ Pydantic settings management from environment variables
  │
  └─ requirements.txt
     └─ Dependencies: fastapi, uvicorn, httpx, pydantic, redis, structlog
```

### Pillar 2: Frontend Interface (TypeScript/React)

```
FRONTEND:
  ├─ next.config.mjs
  │  └─ Next.js config with `output: 'export'` for static generation
  │
  ├─ app/page.tsx
  │  └─ Main route, dynamically loads the main dashboard component
  │
  ├─ src/components/
  │  ├─ LiveRaceDashboard.tsx (main interactive component)
  │  │  ├─ State: races[], connectionStatus, errorDetails, filterParams
  │  │  ├─ Effects: Listens for backend status via IPC, fetches data on 'online'
  │  │  ├─ fetchQualifiedRaces() -> calls backend API with filter params
  │  │  └─ Renders child components based on state (skeletons, race cards, error states)
  │  │
  │  ├─ RaceCard.tsx (displays a single race)
  │  ├─ RaceFilters.tsx (user controls for filtering)
  │  └─ ManualOverridePanel.tsx (handles adapter failures)
  │
  └─ src/types/
     └─ racing.ts (TypeScript interfaces matching backend Pydantic models)
```

### Pillar 3: Electron Wrapper & Windows Integration

```
ELECTRON_WRAPPER:
  ├─ main.js (Electron main process)
  │  ├─ Creates BrowserWindow, loads static frontend (`index.html`)
  │  ├─ Spawns and manages the backend executable (`api.exe`) as a child process
  │  ├─ Creates a system tray icon for background operation
  │  ├─ Sends backend status ('online'/'offline') to frontend via IPC
  │  └─ Exposes a secure API key retrieval mechanism via IPC
  │
  ├─ preload.js (Secure IPC bridge)
  │  └─ Uses contextBridge to expose `window.electronAPI` to the frontend
  │
  ├─ package.json (electron-builder configuration)
  │  └─ Defines build settings for the MSI installer
  │
  └─ .github/workflows/build-msi.yml
     └─ GitHub Actions CI/CD pipeline for automated MSI builds
```

---

## 3. BACKEND ENGINE (PYTHON) - DETAILED

### 3.1 Configuration & Environment

```
PSEUDOCODE get_settings():
  IMPORT Settings from pydantic_settings

  DEFINE Settings class:
    - API_KEY: str (no default; must exist, min_length=16)
    - BETFAIR_USERNAME, BETFAIR_PASSWORD: Optional[str]
    - TVG_API_KEY: Optional[str]
    - REDIS_URL: str (default: "redis://localhost:6379")
    - ALLOWED_ORIGINS: List[str] (default: ["http://localhost:3000", "http://localhost:3001"])
    - MAX_CONCURRENT_REQUESTS: int (default: 10)
    - HTTP_POOL_CONNECTIONS: int (default: 100)
    - HTTP_MAX_KEEPALIVE: int (default: 20)

  RETURN Settings instance (uses lru_cache for singleton pattern)
```

### 3.2 Adapter Framework

```
ABSTRACT CLASS BaseAdapterV3(source_name, base_url):
  INIT():
    self.source_name ← source_name
    self.base_url ← base_url
    self.http_client ← None  // Injected by OddsEngine
    self.logger ← structlog.get_logger()

  ASYNC FUNCTION make_request(method, url, **kwargs):
    // Simplified for brevity: performs an HTTP request with error handling
    TRY:
      response ← await self.http_client.request(method, full_url, **kwargs)
      response.raise_for_status()
      RETURN response
    CATCH HTTPStatusError e:
      RAISE AdapterHttpError(status_code=e.response.status_code, url=full_url)
    CATCH RequestError e:
      RAISE AdapterHttpError(url=full_url)

  ASYNC ABSTRACT FUNCTION _fetch_data(date: str) → Any:
    """Performs all network operations; returns raw data (e.g., HTML/JSON)."""
    PASS

  ABSTRACT FUNCTION _parse_races(raw_data: Any) → List[Race]:
    """A pure function that parses raw data into Race objects; no side effects."""
    PASS

  ASYNC GENERATOR FUNCTION get_races(date: str):
    """Public interface: orchestrates the fetch → parse pipeline."""
    TRY:
      raw_data ← await _fetch_data(date)
      IF raw_data IS NOT None:
        parsed_races ← _parse_races(raw_data)
        FOR race IN parsed_races:
          YIELD race
    CATCH Exception e:
      logger.error(f"Pipeline error for {source_name}", exc_info=True)
      // Exception is caught and logged by the OddsEngine
      RAISE
```

### 3.3 Engine Orchestration

```
CLASS OddsEngine:
  INIT(config):
    self.config ← config
    self.adapters ← [List of all adapter instances]
    self.http_client ← httpx.AsyncClient(...)
    self.semaphore ← asyncio.Semaphore(config.MAX_CONCURRENT_REQUESTS)

    // Inject shared HTTP client into each adapter
    FOR adapter IN self.adapters:
      adapter.http_client ← self.http_client

  ASYNC FUNCTION close():
    AWAIT self.http_client.aclose()

  ASYNC FUNCTION _fetch_with_semaphore(adapter, date):
    ASYNC WITH self.semaphore:
      RETURN await _time_adapter_fetch(adapter, date)

  ASYNC FUNCTION _time_adapter_fetch(adapter, date) -> Tuple[str, dict, float]:
    // Wraps adapter.get_races to handle errors and record performance
    TRY:
      races ← [race async for race in adapter.get_races(date)]
      // Build success payload
    CATCH Exception e:
      // Build failure payload
    RETURN (adapter.source_name, payload, duration)

  FUNCTION _dedupe_races(races: List[Race]) → List[Race]:
    // Merges races with the same key (venue|race_number|start_time)
    // Aggregates runner odds from different sources for the same race
    PASS

  @cache_async_result(ttl_seconds=300)
  ASYNC FUNCTION fetch_all_odds(date_str, source_filter=None):
    // Determine which adapters to run based on source_filter
    target_adapters ← ...

    // Create concurrent fetching tasks
    tasks ← [_fetch_with_semaphore(adapter, date_str) FOR adapter in target_adapters]
    results ← AWAIT asyncio.gather(*tasks, return_exceptions=True)

    // Process results: separate successful from failed, collect all races
    all_races ← ...
    source_infos ← ...

    // Deduplicate and merge the collected races
    deduped_races ← _dedupe_races(all_races)

    // Build and return the final AggregatedResponse object
    RETURN AggregatedResponse(...)
```

### 3.4 API Layer (FastAPI)

```
// --- Lifespan Management ---
ASYNC FUNCTION lifespan(app):
  // Startup:
  configure_logging()
  settings ← get_settings()
  engine ← OddsEngine(config=settings)
  app.state.engine ← engine
  app.state.analyzer_engine ← AnalyzerEngine()
  // ... other initializations

  YIELD

  // Shutdown:
  AWAIT app.state.engine.close()


// --- Main Application ---
APP ← FastAPI(lifespan=lifespan)
// Add middleware for CORS, Rate Limiting, Error Handling


// --- Dependencies ---
FUNCTION verify_api_key(x_api_key: str = Header(...)):
  // Compares provided key with settings.API_KEY using secrets.compare_digest
  PASS

DEPENDENCY get_engine(request):
  RETURN request.app.state.engine


// --- Routes ---
@app.get("/api/races/qualified/{analyzer_name}")
ASYNC FUNCTION get_qualified_races(
  analyzer_name: str,
  race_date: Optional[date],
  engine = Depends(get_engine),
  verified = Depends(verify_api_key),
  // Filter parameters from Query (max_field_size, etc.)
):
  date_str ← race_date or today

  // 1. Fetch data
  aggregated_data ← AWAIT engine.fetch_all_odds(date_str)
  races ← aggregated_data["races"]

  // 2. Get and configure analyzer
  analyzer_engine ← request.app.state.analyzer_engine
  analyzer ← analyzer_engine.get_analyzer(analyzer_name, **custom_params)

  // 3. Analyze and return results
  result ← analyzer.qualify_races(races)
  RETURN result
```

---

## 4. FRONTEND INTERFACE (TYPESCRIPT/REACT) - DETAILED

### 4.1 LiveRaceDashboard Component

```
COMPONENT LiveRaceDashboard (client-side):

  STATE:
    races: Race[] ← []
    connectionStatus: 'connecting' | 'online' | 'offline' ← 'connecting'
    errorDetails: string | null ← null
    params: RaceFilterParams ← { defaults }

  EFFECT on mount:
    // Listen for backend status updates from the Electron main process
    IF window.electronAPI exists:
      window.electronAPI.onBackendStatus((update) => {
        setConnectionStatus(update.status)
        IF update.status === 'offline':
          setErrorDetails(update.error)
        ELSE IF update.status === 'online':
          fetchQualifiedRaces() // Trigger fetch when backend comes online
      })

    // Set up a periodic refresh interval
    interval ← setInterval(() => {
      IF connectionStatus === 'online':
        fetchQualifiedRaces()
    }, 30000)

    CLEANUP: clearInterval(interval)

  ASYNC FUNCTION fetchQualifiedRaces():
    setConnectionStatus('connecting')

    TRY:
      // Securely get the API key via IPC call to the main process
      apiKey ← AWAIT window.electronAPI.getApiKey()
      IF NOT apiKey:
        RAISE new Error("API key could not be retrieved.")

      // Build query and fetch data from the backend API
      queryParams ← new URLSearchParams(params)
      response ← AWAIT fetch(`/api/races/qualified/trifecta?${queryParams}`, {
        headers: { "X-API-Key": apiKey }
      })

      IF NOT response.ok:
        RAISE new Error(`Backend returned status ${response.status}`)

      data ← AWAIT response.json()
      setRaces(data.races)
      setConnectionStatus('online')

    CATCH e:
      setErrorDetails(e.message)
      setConnectionStatus('offline')

  FUNCTION RENDER:
    <div className="dashboard">
      <Header />
      <RaceFilters onParamsChange={handleParamChange} />

      IF connectionStatus === 'offline':
        <EmptyState message={errorDetails} />
      ELSE IF connectionStatus === 'connecting':
        <RaceCardSkeleton count={4} />
      ELSE IF races.length === 0:
        <EmptyState message="No races matched your filters." />
      ELSE:
        <div className="race-grid">
          {races.map(race => <RaceCard key={race.id} race={race} />)}
        </div>
    </div>
```

---

## 5. ELECTRON WRAPPER & WINDOWS INTEGRATION - DETAILED

### 5.1 Main Process (`main.js`)

```
CLASS FortunaDesktopApp:
  INIT():
    self.mainWindow ← null
    self.backendProcess ← null

  FUNCTION createMainWindow():
    self.mainWindow ← new BrowserWindow({
      // ... window settings ...
      webPreferences: {
        preload: path.join(__dirname, 'preload.js') // CRITICAL for security
      }
    })

    // Load static frontend files in production
    IF isDev:
      mainWindow.loadURL('http://localhost:3000')
    ELSE:
      mainWindow.loadFile(path.join(__dirname, 'web-ui-build', 'out', 'index.html'))

  ASYNC FUNCTION startBackend():
    // Determine path to backend executable (api.exe in production)
    backendExecutable ← isDev ? '.venv/Scripts/python.exe' : './api.exe'
    backendArgs ← isDev ? ['run_backend.py'] : []

    // Spawn the backend as a child process
    self.backendProcess ← spawn(backendExecutable, backendArgs)

    // Listen to stdout for the startup signal
    backendProcess.stdout.on('data', (data) => {
      IF data.toString().includes("Backend ready"):
        // Notify frontend that the backend is online
        mainWindow.webContents.send('backend-status', { status: 'online' })
    })

    // Listen for errors or premature exit
    backendProcess.on('error', (error) => {
      mainWindow.webContents.send('backend-status', { status: 'offline', error: error.message })
    })
    backendProcess.on('close', (code) => {
      IF processDidNotStartSuccessfully:
        mainWindow.webContents.send('backend-status', { status: 'offline', error: `Process exited with code ${code}` })
    })

  FUNCTION initialize():
    // UI-First: Create and show the window immediately
    createMainWindow()
    createSystemTray()

    // Asynchronously start the backend without blocking the UI
    startBackend().catch(error => { /* Errors are handled by listeners */ })

// --- IPC Handlers (Main Process) ---
app.whenReady().then(() => {
  // Handler for the frontend's request for the API key
  ipcMain.handle('get-api-key', async () => {
    TRY:
      // This logic would securely fetch the key (e.g., from Windows Credential Manager)
      apiKey ← await getApiKeyFromCredentials()
      RETURN apiKey
    CATCH error:
      RETURN null
  })

  // Initialize and run the application
  fortunaApp = new FortunaDesktopApp()
  fortunaApp.initialize()
})
```

### 5.2 Preload Script (`preload.js`)

```
// Expose specific, secure functions to the frontend (renderer process)
contextBridge.exposeInMainWorld('electronAPI', {
  // Function for the frontend to call to get the API key
  getApiKey: () => ipcRenderer.invoke('get-api-key'),

  // Function for the frontend to set up a listener for backend status updates
  onBackendStatus: (callback) => ipcRenderer.on('backend-status', (_event, value) => callback(value))
})
```

---

## 6. END-TO-END WORKFLOWS

### 6.1 Production Startup Workflow

```
WORKFLOW user_launches_application:
  STEP 1: User executes Fortuna Faucet.exe
    - Electron main.js process starts

  STEP 2: UI Initialization (UI-First)
    - A BrowserWindow is created immediately
    - The window begins loading the static index.html file
    - User sees the application window and loading state instantly

  STEP 3: Backend Startup (Asynchronous)
    - The main process spawns the `api.exe` backend executable as a background child process
    - The main process listens to the stdout of the `api.exe` process

  STEP 4: Frontend Waits for Backend
    - The `LiveRaceDashboard` component mounts in the renderer process (the window)
    - It uses the `window.electronAPI.onBackendStatus` listener to wait for a signal

  STEP 5: Backend Becomes Ready
    - `api.exe` finishes its startup and prints "Backend ready" to stdout
    - The main process detects this message
    - The main process sends an IPC message `backend-status: { status: 'online' }` to the frontend

  STEP 6: Data Fetch is Triggered
    - The frontend's `onBackendStatus` listener receives the 'online' signal
    - It calls the `fetchQualifiedRaces()` function

  STEP 7: Secure API Key Retrieval
    - `fetchQualifiedRaces()` calls `await window.electronAPI.getApiKey()`
    - The preload script bridges this call to the `ipcMain.handle('get-api-key', ...)` handler in the main process
    - The handler securely retrieves the key and returns it to the frontend

  STEP 8: API Call and Render
    - The frontend makes the `fetch` request to the backend API, including the retrieved key
    - The backend processes the request and returns data
    - The frontend renders the race cards

  RESULT: User sees the live race dashboard populated with data. The entire process from launch to data display is orchestrated and secure.
```

---

*This concludes the refined pseudocode blueprint, updated to reflect the true architecture and logic of the Fortuna Faucet application.*
