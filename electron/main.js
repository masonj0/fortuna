// electron/main.js
const { app, BrowserWindow, ipcMain, Menu } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');
const isDev = process.env.NODE_ENV === 'development';

let mainWindow = null;
let backendProcess = null;

/**
 * Get the correct path for the backend executable.
 * In production with extraResources, backend.exe is in the app root directory.
 */
function getBackendExePath() {
  if (isDev) {
    // Development: backend in electron/resources/fortuna-backend.exe
    return path.join(__dirname, 'resources', 'fortuna-backend.exe');
  } else {
    // Production: extraResources places backend.exe in app root
    // app.getAppPath() = /Program Files/Fortuna Faucet/resources/app.asar.unpacked
    // Go up two levels to: /Program Files/Fortuna Faucet/fortuna-backend.exe
    const asarUnpackedPath = app.getAppPath();
    const appRoot = path.join(asarUnpackedPath, '..', '..');
    return path.join(appRoot, 'fortuna-backend.exe');
  }
}

/**
 * Get the frontend path for both development and production.
 */
function getFrontendPath() {
  if (isDev) {
    return path.join(__dirname, 'web-ui-build', 'out');
  } else {
    return path.join(app.getAppPath(), 'web-ui-build', 'out');
  }
}

/**
 * Start the Python backend process.
 */
function startBackend() {
  return new Promise((resolve, reject) => {
    const backendExePath = getBackendExePath();

    console.log('[MAIN] Starting backend...');
    console.log('[MAIN] Backend executable path:', backendExePath);
    console.log('[MAIN] App path:', app.getAppPath());

    // Verify backend executable exists
    if (!fs.existsSync(backendExePath)) {
      console.error('[MAIN] ERROR: Backend executable not found!');
      console.error('[MAIN] Expected at:', backendExePath);

      // Debug: list app structure
      const appRoot = path.dirname(app.getAppPath());
      console.error('[MAIN] App root directory:', appRoot);
      console.error('[MAIN] Contents of app root:');
      try {
        const files = fs.readdirSync(appRoot);
        files.forEach(f => {
          const fullPath = path.join(appRoot, f);
          const isDir = fs.statSync(fullPath).isDirectory();
          console.error('[MAIN]   -', isDir ? `[DIR] ${f}` : f);
        });
      } catch (err) {
        console.error('[MAIN]   Error reading directory:', err.message);
      }

      reject(new Error(`Backend executable not found at ${backendExePath}`));
      return;
    }

    console.log('[MAIN] Backend executable found, spawning process...');

    // Spawn backend process
    backendProcess = spawn(backendExePath, [], {
      stdio: ['ignore', 'pipe', 'pipe'],
      detached: false,
      shell: false
    });

    backendProcess.stdout.on('data', (data) => {
      console.log('[BACKEND STDOUT]:', data.toString().trim());
    });

    backendProcess.stderr.on('data', (data) => {
      console.error('[BACKEND STDERR]:', data.toString().trim());
    });

    backendProcess.on('error', (err) => {
      console.error('[MAIN] Backend process spawn error:', err);
      reject(err);
    });

    backendProcess.on('exit', (code, signal) => {
      console.log('[MAIN] Backend process exited with code:', code, 'signal:', signal);
    });

    // Wait for backend to start listening
    setTimeout(() => {
      console.log('[MAIN] Backend startup completed');
      resolve();
    }, 5000);
  });
}

/**
 * Create the application window and load the frontend.
 */
function createWindow() {
  const frontendPath = getFrontendPath();
  const indexPath = path.join(frontendPath, 'index.html');

  console.log('[MAIN] Creating window...');
  console.log('[MAIN] Frontend path:', frontendPath);
  console.log('[MAIN] Index path:', indexPath);

  // Verify frontend files exist
  if (!fs.existsSync(indexPath)) {
    console.error('[MAIN] ERROR: Frontend index.html not found!');
    console.error('[MAIN] Expected at:', indexPath);

    if (fs.existsSync(frontendPath)) {
      console.error('[MAIN] Contents of frontend directory:');
      try {
        const files = fs.readdirSync(frontendPath);
        files.forEach(f => console.error('[MAIN]   -', f));
      } catch (err) {
        console.error('[MAIN]   Error reading directory:', err.message);
      }
    } else {
      console.error('[MAIN] Frontend directory does not exist!');
    }
  }

  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      enableRemoteModule: false,
      preload: path.join(__dirname, 'preload.js'),
      sandbox: true
    },
    icon: path.join(__dirname, 'assets', 'icon.ico')
  });

  // Load frontend
  if (isDev) {
    console.log('[MAIN] Development mode: loading from localhost:3000');
    mainWindow.loadURL('http://localhost:3000');
    mainWindow.webDevTools.openDevTools();
  } else {
    console.log('[MAIN] Production mode: loading from file:', indexPath);
    mainWindow.loadFile(indexPath).catch(err => {
      console.error('[MAIN] Error loading index.html:', err);
    });
  }

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  console.log('[MAIN] Window created');
}

/**
 * App event: ready
 */
app.on('ready', async () => {
  console.log('[MAIN] App ready event');
  console.log('[MAIN] App version:', app.getVersion());
  console.log('[MAIN] Node version:', process.version);
  console.log('[MAIN] Electron version:', process.versions.electron);
  console.log('[MAIN] App path:', app.getAppPath());
  console.log('[MAIN] User data path:', app.getPath('userData'));

  try {
    console.log('[MAIN] ========== STARTING BACKEND ==========');
    await startBackend();
    console.log('[MAIN] ========== BACKEND STARTED ==========');

    console.log('[MAIN] ========== CREATING WINDOW ==========');
    createWindow();
    console.log('[MAIN] ========== WINDOW CREATED ==========');
  } catch (err) {
    console.error('[MAIN] FATAL ERROR during startup:', err);

    const { dialog } = require('electron');
    dialog.showErrorBox(
      'Fortuna Faucet Startup Error',
      `Failed to start application:\n\n${err.message}\n\nPlease check the application logs for more details.\n\nLogs location: ${app.getPath('userData')}`
    );

    app.quit();
  }
});

/**
 * App event: window-all-closed
 */
app.on('window-all-closed', () => {
  console.log('[MAIN] All windows closed');
  if (process.platform !== 'darwin') {
    if (backendProcess) {
      console.log('[MAIN] Terminating backend process');
      backendProcess.kill();
    }
    app.quit();
  }
});

/**
 * App event: activate (macOS)
 */
app.on('activate', () => {
  console.log('[MAIN] Activate event');
  if (mainWindow === null) {
    createWindow();
  }
});

/**
 * App event: before-quit
 */
app.on('before-quit', () => {
  console.log('[MAIN] Before quit event');
  if (backendProcess) {
    console.log('[MAIN] Killing backend process');
    try {
      backendProcess.kill();
    } catch (err) {
      console.error('[MAIN] Error killing backend:', err);
    }
  }
});

/**
 * Handle uncaught exceptions
 */
process.on('uncaughtException', (err) => {
  console.error('[MAIN] Uncaught exception:', err);
});

console.log('[MAIN] ========== ELECTRON MAIN PROCESS LOADED ==========');
