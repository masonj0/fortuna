# 🐎 Fortuna Faucet - Complete Pseudocode Blueprint

**Status:** Comprehensive System Specification (Revised & Corrected)
**Version:** 2.2.0
**Last Updated:** November 7, 2025

---

## TABLE OF CONTENTS

1.  System Overview
2.  Architecture Pillars
3.  Backend Engine (Python) - Detailed
4.  Frontend Interface (TypeScript/React) - Detailed
5.  Electron Wrapper & Windows Integration - Detailed
6.  Data Models & API Specification
7.  Deployment & Automation (CI/CD)
8.  End-to-End Workflows

---

## 1. SYSTEM OVERVIEW

```
╔════════════════════════════════════════════════════════════════╗
║         FORTUNA FAUCET - Racing Analysis Platform             ║
║  Unifying global horse/greyhound/harness racing intelligence   ║
╚════════════════════════════════════════════════════════════════╝

MISSION:
  • Acquire race data from 20+ global sources (APIs + web scraping).
  • Normalize and deduplicate data into a canonical Race format.
  • Apply analytical filters to surface high-value betting opportunities.
  • Serve results via a secure, local REST API to an interactive dashboard.
  • Operate as a professional, standalone, native Windows application.

CORE TENETS:
  • UI-First Experience: The user interface is always responsive, even during backend startup or restarts.
  • Resilient Process Management: The backend executable's lifecycle is robustly managed, with timeouts and crash detection.
  • Asynchronous Initialization: The backend server starts instantly, deferring heavy, blocking I/O to background threads.
  • Secure by Design: Communication between the frontend and the privileged main process is secured via a context-aware preload script.
  • Automated & Repeatable Builds: The entire application is built, tested, and packaged via a deterministic CI/CD pipeline.

STAKEHOLDERS:
  • End User: Receives a professional MSI installer for a one-click, dependency-free launch.
  • Developer: Works with clean, separated Python and TypeScript stacks, governed by this specification.
```

---

## 2. ARCHITECTURE PILLARS

### Pillar 1: Backend Engine (Python)

```
PYTHON_BACKEND:
  ├─ main.py
  │  └─ Entry point for PyInstaller executable; starts the Uvicorn server.
  │
  ├─ api.py
  │  └─ FastAPI application definition.
  │     ├─ Lifespan Hook: Manages async startup/shutdown logic.
  │     ├─ API Routes: /health, /api/status, /api/races, etc.
  │     └─ Dependency Injection: Provides engine and security dependencies.
  │
  ├─ engine.py
  │  └─ OddsEngine: Orchestrates all data fetching and processing.
  │
  ├─ adapters/
  │  ├─ base_v3.py (Abstract Base Class for all data sources)
  │  └─ [20+ specific adapter implementations]
  │
  ├─ config.py
  │  └─ Pydantic settings management from .env file.
  │
  └─ requirements.txt
     └─ Clean, de-duplicated, and conflict-free list of all Python dependencies.
```

### Pillar 2: Frontend Interface (TypeScript/React)

```
FRONTEND:
  ├─ next.config.mjs
  │  └─ Next.js config with `output: 'export'` for 100% static generation.
  │
  ├─ app/page.tsx
  │  └─ Main application shell.
  │
  ├─ src/components/
  │  ├─ LiveRaceDashboard.tsx (Main stateful component)
  │  │  ├─ Manages connection state ('connecting', 'online', 'error').
  │  │  ├─ Polls Electron main process for backend status via secure IPC.
  │  │  └─ Fetches data from the local Python API when online.
  │  │
  │  ├─ RaceCard.tsx (Displays a single race)
  │  └─ StatusIndicator.tsx (Shows backend connection status)
  │
  └─ src/types/
     └─ racing.ts (TypeScript interfaces matching backend Pydantic models)
```

### Pillar 3: Electron Wrapper & Windows Integration

```
ELECTRON_WRAPPER:
  ├─ main.js (Electron main process)
  │  ├─ Creates the BrowserWindow and loads the static frontend.
  │  ├─ Implements robust lifecycle management for the backend executable.
  │  ├─ Provides secure IPC handlers for status checks and restarts.
  │  └─ Creates a system tray icon for background operation.
  │
  ├─ preload.js (Secure IPC Bridge)
  │  └─ Uses `contextBridge` to safely expose specific functions to the frontend.
  │
  ├─ package.json
  │  └─ Defines Node.js dependencies and build scripts.
  │
  ├─ electron-builder-config.yml
  │  └─ Defines the configuration for creating the final MSI installer.
  │
  └─ .github/workflows/build-msi.yml
     └─ GitHub Actions pipeline that automates the entire build, test, and package process.
```

---

## 3. BACKEND ENGINE (PYTHON) - DETAILED

### 3.1 Entry Point & Server Startup (`main.py`)

```pseudocode
// This is the script executed by fortuna-backend.exe

PROCEDURE Main_Python_Entry_Point
  // Guard required for PyInstaller and multiprocessing on Windows
  IF this script is the main entry point:
    CALL multiprocessing.freeze_support()

    // Programmatically launch the FastAPI application using Uvicorn
    // This call blocks and runs the server until the process is terminated
    CALL uvicorn.run(
      app="python_service.api:app",
      host="0.0.0.0",
      port=8000
    )
END PROCEDURE
```

### 3.2 Asynchronous Application Lifecycle (`api.py`)

```pseudocode
// --- Lifespan Management (The key to a non-blocking startup) ---
ASYNC FUNCTION lifespan_manager(app: FastAPI):
  // === ON STARTUP ===
  LOG "Uvicorn server is online. Starting lifespan initialization."

  // 1. Perform immediate, non-blocking tasks
  CONNECT to Redis cache

  // 2. Defer slow, blocking tasks to a background thread
  //    This allows the server to start accepting requests instantly.
  SCHEDULE function "initialize_heavy_resources(app)" to run in a ThreadPoolExecutor

  LOG "Heavy resource initialization scheduled. Server is now responsive."

  // 3. Yield control back to Uvicorn. The server is now live.
  YIELD

  // === ON SHUTDOWN ===
  LOG "Shutdown signal received."
  AWAIT app.state.engine.close() // Gracefully close HTTP client connections
  DISCONNECT from Redis
  SHUTDOWN ThreadPoolExecutor

// --- Heavy Initialization (Runs in Background) ---
FUNCTION initialize_heavy_resources(app: FastAPI):
  TRY
    LOG "Background initialization of OddsEngine has started."
    settings <- get_settings_from_config()
    engine <- create new OddsEngine(config=settings)
    // This part is slow: it loads all ~25 adapters
    app.state.engine <- engine
    LOG "Background initialization complete. OddsEngine is now available."
  CATCH Exception as e:
    LOG_CRITICAL "Failed to initialize OddsEngine in the background.", error=e
    app.state.engine <- null // Ensure the app knows initialization failed
```

### 3.3 Engine Orchestration (`engine.py`)

```pseudocode
CLASS OddsEngine:
  INIT(config):
    self.config <- config
    self.adapters <- [List of all adapter instances]
    self.http_client <- httpx.AsyncClient(...)
    self.semaphore <- asyncio.Semaphore(config.MAX_CONCURRENT_REQUESTS)

    // Inject the shared, persistent HTTP client into each adapter
    FOR adapter IN self.adapters:
      adapter.http_client <- self.http_client

  @cache_async_result(ttl_seconds=300)
  ASYNC FUNCTION fetch_all_odds(date_str):
    // Create a list of concurrent fetching tasks, wrapped in the semaphore
    tasks <- [self._fetch_with_semaphore(adapter, date_str) FOR adapter in self.adapters]
    results <- AWAIT asyncio.gather(*tasks, return_exceptions=True)

    // Process results, separating successes from failures
    all_races <- []
    FOR result IN results:
      IF result is a success:
        all_races.extend(result.races)

    // Deduplicate and merge races from different sources
    deduped_races <- self._dedupe_races(all_races)

    RETURN AggregatedResponse(races=deduped_races, source_statuses=...)
```

---

## 4. FRONTEND INTERFACE (TYPESCRIPT/REACT) - DETAILED

### 4.1 LiveRaceDashboard Component

```pseudocode
COMPONENT LiveRaceDashboard (client-side):

  STATE:
    races: Race[] <- []
    backendStatus: 'connecting' | 'online' | 'error' <- 'connecting'
    lastLogs: string[] <- []

  EFFECT on mount:
    // Use the secure API exposed by preload.js
    IF window.electronAPI exists:
      // Set up a listener for status updates from the main process
      window.electronAPI.onBackendStatus((update) => {
        setBackendStatus(update.state)
        setLastLogs(update.logs)
      })

    // Immediately request the current status
    window.electronAPI.getBackendStatus().then((status) => {
      setBackendStatus(status.state)
      setLastLogs(status.logs)
    })

    // Set up a polling interval to keep status fresh
    interval <- setInterval(() => {
      window.electronAPI.getBackendStatus().then((status) => {
        setBackendStatus(status.state)
        setLastLogs(status.logs)
      })
    }, 3000) // Poll every 3 seconds

    CLEANUP: clearInterval(interval)

  EFFECT when backendStatus changes to 'online':
    // Trigger data fetch only when the backend is confirmed to be running
    fetchQualifiedRaces()

  ASYNC FUNCTION fetchQualifiedRaces():
    TRY:
      // Make a standard HTTP call to the local Python server
      response <- AWAIT fetch("http://127.0.0.1:8000/api/races/qualified/trifecta")
      IF NOT response.ok:
        RAISE new Error(`API returned status ${response.status}`)

      data <- AWAIT response.json()
      setRaces(data.races)

    CATCH e:
      // If the API call fails, update the status
      setBackendStatus('error')
      setLastLogs([...lastLogs, `API Fetch Error: ${e.message}`])

  FUNCTION RENDER:
    <div className="dashboard">
      <StatusIndicator status={backendStatus} />
      <RaceFilters />

      IF backendStatus === 'error':
        <ErrorDisplay logs={lastLogs} />
      ELSE IF backendStatus === 'connecting':
        <LoadingSkeleton />
      ELSE IF races.length === 0:
        <EmptyState message="No races matched your filters." />
      ELSE:
        <RaceGrid races={races} />
    </div>
```

---

## 5. ELECTRON WRAPPER & WINDOWS INTEGRATION - DETAILED

### 5.1 Main Process (`main.js`) - With Robust Lifecycle Management

```pseudocode
CLASS FortunaDesktopApp:
  INIT():
    self.mainWindow <- null
    self.backendState <- 'stopped'
    self.backendLogs <- []
    self.backendProcess <- null

  FUNCTION createMainWindow():
    // ... create BrowserWindow, load static frontend ...

  FUNCTION startBackend():
    IF self.backendProcess is not null:
      self.backendProcess.kill()

    self.backendState <- 'starting'
    self.backendLogs <- ['Attempting to start backend...']
    self.sendBackendStatusUpdate() // Notify UI

    // Get path to the packaged executable
    exePath <- path.join(process.resourcesPath, 'fortuna-backend', 'fortuna-backend.exe')

    IF file at exePath does NOT exist:
      self.backendState <- 'error'
      self.backendLogs.push(`FATAL: Executable not found at ${exePath}`)
      self.sendBackendStatusUpdate()
      dialog.showErrorBox("Critical Error", "Backend is missing. Please reinstall.")
      RETURN

    // Spawn the process
    self.backendProcess <- spawn(exePath, [], { stdio: ['ignore', 'pipe', 'pipe'] })

    // --- CRITICAL: Resiliency Logic ---
    startupTimeout <- setTimeout(() => {
      IF self.backendState === 'starting':
        self.backendState <- 'error'
        self.backendLogs.push('Error: Backend startup timed out after 30 seconds.')
        self.backendProcess.kill()
        self.sendBackendStatusUpdate()
    }, 30000) // 30-second timeout

    self.backendProcess.stdout.on('data', (data) => {
      self.backendLogs.push(data.toString())
      // A more robust check would be a successful health check poll
      IF data.toString().includes("Uvicorn running"):
        self.backendState <- 'online'
        clearTimeout(startupTimeout)
        self.sendBackendStatusUpdate()
    })

    self.backendProcess.stderr.on('data', (data) => {
      self.backendLogs.push(`[STDERR] ${data.toString()}`)
    })

    self.backendProcess.on('exit', (code) => {
      clearTimeout(startupTimeout)
      IF self.backendState is not 'error': // Avoid duplicate error messages
        self.backendState <- 'error'
        self.backendLogs.push(`Backend process exited unexpectedly with code: ${code}`)
        self.sendBackendStatusUpdate()
    })

  FUNCTION sendBackendStatusUpdate():
    // Send the latest status to the frontend renderer process
    IF self.mainWindow is not null:
      self.mainWindow.webContents.send('backend-status-update', {
        state: self.backendState,
        logs: self.backendLogs.slice(-20) // Send last 20 log lines
      })

// --- IPC Handlers (Securely Defined) ---
ipcMain.handle('get-backend-status', (event) => {
  // SECURITY: Ensure the request is from our main window
  IF event.sender is NOT self.mainWindow.webContents:
    RETURN null

  RETURN { state: self.backendState, logs: self.backendLogs.slice(-20) }
})

ipcMain.on('restart-backend', (event) => {
  // SECURITY: Ensure the request is from our main window
  IF event.sender is NOT self.mainWindow.webContents:
    RETURN

  self.startBackend()
})
```

### 5.2 Preload Script (`preload.js`)

```pseudocode
// Expose a limited, secure API to the frontend renderer process
contextBridge.exposeInMainWorld('electronAPI', {
  getBackendStatus: () => ipcRenderer.invoke('get-backend-status'),
  restartBackend: () => ipcRenderer.send('restart-backend'),
  onBackendStatus: (callback) => ipcRenderer.on('backend-status-update', (_event, value) => callback(value))
})
```

---

## 6. DATA MODELS & API SPECIFICATION

### 6.1 Core Data Models (Pydantic/TypeScript)

```
MODEL Race:
  id: str (unique identifier, e.g., "Betfair_USA_Aqueduct_2025-11-07_R1")
  venue: str
  race_number: int
  start_time: datetime
  runners: List[Runner]
  source: str

MODEL Runner:
  name: str
  odds: Optional[float]
```

### 6.2 Primary API Endpoints

```
ENDPOINT GET /health
  Description: Simple health check, requires no authentication.
  Response (200 OK): {"status": "ok"}

ENDPOINT GET /api/races/qualified/trifecta
  Description: Fetches all race data, runs the Trifecta analyzer, and returns qualified races.
  Headers:
    - X-API-Key: (Required, not used in this local setup but good practice)
  Query Params:
    - max_field_size: int
    - min_odds: float
  Response (200 OK):
    {
      "qualified_races": List[Race],
      "analysis_metadata": { ... }
    }
```

---

## 7. DEPLOYMENT & AUTOMATION (CI/CD)

```pseudocode
WORKFLOW Build_MSI_Installer_on_GitHub_Actions:
  // Phase 1: Setup
  SETUP Node.js and Python environments

  // Phase 2: Build Frontend
  RUN "npm ci" and "npm run build" in /web_platform/frontend
  COPY static output to /electron/web-ui-build/out

  // Phase 3: Build Backend
  RUN "pip install -r python_service/requirements.txt"
  // CRITICAL: Use PyInstaller with a spec file or CLI flags that include
  // necessary hidden imports to prevent runtime crashes.
  // e.g., --hidden-import=keyring.backends.fail.Keyring
  EXECUTE PyInstaller to create fortuna-backend.exe
  PLACE executable in /electron/resources/fortuna-backend

  // Phase 4: Deep Integration Test
  START fortuna-backend.exe in the background
  POLL http://127.0.0.1:8000/health until it responds with 200 OK or times out
  IF timeout or crash THEN FAIL the build

  // Phase 5: Package
  RUN "npm ci" in /electron
  EXECUTE "npx electron-builder" to create the MSI installer

  // Phase 6: Publish
  UPLOAD MSI as a build artifact
  IF build was triggered by a git tag THEN CREATE a new GitHub Release
```

---

## 8. END-TO-END WORKFLOWS

### 8.1 Production Startup Workflow (Resilient)

```
WORKFLOW user_launches_application:
  STEP 1: User executes Fortuna Faucet.exe -> Electron main.js starts.
  STEP 2: UI appears instantly. The main process creates the BrowserWindow and loads the static index.html. The UI shows a 'connecting' state.
  STEP 3: Backend starts asynchronously. The main process calls the robust `startBackend()` function.
  STEP 4: `startBackend()` spawns `fortuna-backend.exe` and starts a 30-second timeout.
  STEP 5: The frontend UI polls for status every 3 seconds via the secure `window.electronAPI.getBackendStatus()`.
  STEP 6: The backend `.exe` starts, its `lifespan` hook runs, and the Uvicorn server comes online within seconds.
  STEP 7: The main process detects the "Uvicorn running" message (or a successful health poll) and updates its internal state to 'online'. The startup timeout is cleared.
  STEP 8: On its next poll, the frontend receives the 'online' status.
  STEP 9: The frontend's state changes, triggering the `fetchQualifiedRaces()` API call to `localhost:8000`.
  STEP 10: Data is returned from the now fully-initialized backend and rendered in the UI.

  FAILURE SCENARIO (Backend Crash):
  STEP 6a: The backend `.exe` crashes on startup.
  STEP 7a: The `on('exit')` handler in `main.js` fires. The state is set to 'error' with the exit code.
  STEP 8a: On its next poll, the frontend receives the 'error' status and relevant logs.
  STEP 9a: The UI renders an error message and a "Restart Backend" button.
```

---
*This concludes the revised and definitive blueprint for the Fortuna Faucet application.*

---

## 9. OPERATION: THE AUDITOR (REAL-TIME VERIFICATION)

### 9.1 System Context
*This module runs as a background thread within the Python Backend. It provides the "Source of Truth" by verifying predictions against official results (Equibase/GBGB) and calculating the "Favorite to Place" profitability in real-time.*

### 9.2 Database Schema (SQLite)

```pseudocode
TABLE audit_log:
  race_id: TEXT PRIMARY KEY (e.g., "GP-20251213-05")
  track_code: TEXT
  race_number: INT
  predicted_horse: TEXT
  timestamp: DATETIME
  status: TEXT (Default: 'PENDING') // Options: 'PENDING', 'CASHED', 'BURNED'
  official_payout: REAL (Default: 0.00)
  net_profit: REAL (Default: 0.00)
```

### 9.3 Auditor Engine Logic (`auditor.py`)

```pseudocode
CLASS AuditorEngine:
  INIT(db_connection):
    self.db <- db_connection
    self.http_client <- httpx.AsyncClient()
    self.TOTE_UNIT <- 2.00

  // --- Phase 1: The Snapshot ---
  // Called by OddsEngine when a race qualifies as a bet
  ASYNC FUNCTION snapshot_qualifier(race, predicted_horse):
    race_id <- generate_id(race.venue, race.date, race.number)

    TRY:
      SQL_INSERT into audit_log (
        race_id, track_code, race_number, predicted_horse, timestamp, status
      ) VALUES (
        race_id, race.venue_code, race.number, predicted_horse, NOW(), 'PENDING'
      )
      LOG "Snapshot saved for verification: " + race_id
    CATCH IntegrityError:
      LOG_WARN "Race already tracked: " + race_id

  // --- Phase 2: The Fetcher (Background Loop) ---
  // Runs continuously to check results for the last hour
  ASYNC FUNCTION run_audit_loop():
    WHILE True:
      // 1. Find pending races from the last 60 minutes
      cutoff_time <- NOW() - MINUTES(60)
      pending_races <- SQL_SELECT * FROM audit_log
                       WHERE status = 'PENDING' AND timestamp > cutoff_time

      IF pending_races is EMPTY:
        SLEEP 120 seconds
        CONTINUE

      // 2. Fetch Official Results (Batch by Track to be polite)
      FOR race IN pending_races:
        official_result <- AWAIT self._fetch_official_result(race.track_code, race.race_number)

        IF official_result is NOT NULL:
          self._determine_verdict(race, official_result)

      SLEEP 120 seconds

  // --- Phase 3: The Verdict & Economics ---
  FUNCTION _determine_verdict(prediction, official_result):
    did_place <- FALSE
    payout <- 0.00

    // Check if our horse is in the official "Place" payouts
    // (Note: "Place" in US racing covers 1st and 2nd)
    FOR finisher IN official_result.finishers:
      IF finisher.name == prediction.predicted_horse AND finisher.place_payout > 0:
        did_place <- TRUE
        payout <- finisher.place_payout

    // Calculate Net Profit based on $2.00 Unit
    IF did_place:
      new_status <- 'CASHED'
      net_profit <- payout - self.TOTE_UNIT
      LOG_SUCCESS `💰 CASHED: ${prediction.race_id} | Profit: $${net_profit}`
    ELSE:
      new_status <- 'BURNED'
      net_profit <- -self.TOTE_UNIT // Lost the $2.00 stake
      LOG_FAIL `🔥 BURNED: ${prediction.race_id} | Loss: -$2.00`

    // Update the Source of Truth
    SQL_UPDATE audit_log
    SET status = new_status, official_payout = payout, net_profit = net_profit
    WHERE race_id = prediction.race_id

  // --- Helper: Scraper Logic ---
  ASYNC FUNCTION _fetch_official_result(track_code, race_number):
    // Logic to scrape Equibase Summary Results
    html <- AWAIT self.http_client.GET("https://www.equibase.com/static/chart/summary/index.html")
    parsed_data <- parse_html_table(html)

    // Return structured object if result is posted, else NULL
    RETURN find_race_in_summary(parsed_data, track_code, race_number)

  // --- Phase 4: Dashboard Metrics ---
  FUNCTION get_rolling_metrics():
    // Returns stats for the UI "Last Hour" overlay
    cutoff <- NOW() - MINUTES(60)

    stats <- SQL_QUERY """
      SELECT
        COUNT(*) as total,
        SUM(CASE WHEN status = 'CASHED' THEN 1 ELSE 0 END) as wins,
        SUM(net_profit) as profit
      FROM audit_log
      WHERE timestamp > cutoff AND status != 'PENDING'
    """

    strike_rate <- (stats.wins / stats.total) * 100
    RETURN {
      "strike_rate": strike_rate,
      "net_profit": stats.profit,
      "volume": stats.total
    }
```