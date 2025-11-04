// electron/main.js - CORRECTED VERSION
const { app, BrowserWindow, Tray, Menu, nativeImage, ipcMain } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

class FortunaDesktopApp {
  constructor() {
    this.backendProcess = null;
    this.mainWindow = null;
    this.tray = null;
    this.backendState = 'stopped'; // "stopped", "starting", "running", "error"
    this.backendLogs = [];
  }

  sendBackendStatusUpdate() {
    if (this.mainWindow) {
      this.mainWindow.webContents.send('backend-status-update', {
        state: this.backendState,
        logs: this.backendLogs.slice(-20) // Send last 20 log entries
      });
    }
  }

  startBackend() {
    this.backendState = 'starting';
    this.backendLogs = ['Attempting to start backend process...'];
    this.sendBackendStatusUpdate();

    if (this.backendProcess && !this.backendProcess.killed) {
      console.log('Backend process already running. Killing old process.');
      this.backendProcess.kill();
    }

    const isDev = !app.isPackaged;

    if (isDev) {
      // Development: use Python venv
      console.log('[DEV MODE] Starting backend from Python venv...');
      const pythonPath = path.join(__dirname, '..', '.venv', 'Scripts', 'python.exe');

      if (!fs.existsSync(pythonPath)) {
        const errorMsg = 'FATAL: Python executable not found. Run setup first.';
        console.error(errorMsg, { path: pythonPath });
        this.backendState = 'error';
        this.backendLogs.push(errorMsg);
        this.sendBackendStatusUpdate();
        return;
      }

      this.backendProcess = spawn(pythonPath, ['-m', 'uvicorn', 'api:app', '--host', '127.0.0.1', '--port', '8000'], {
        cwd: path.join(__dirname, '..', 'python_service'),
        env: process.env
      });
    } else {
      // Production: use PyInstaller exe
      console.log('[PROD MODE] Starting backend from packaged executable...');
      const exePath = path.join(process.resourcesPath, 'fortuna-backend.exe');

      if (!fs.existsSync(exePath)) {
        const errorMsg = 'FATAL: Backend executable missing from installation.';
        console.error(errorMsg, { path: exePath });
        this.backendState = 'error';
        this.backendLogs.push(errorMsg, `Expected at: ${exePath}`);
        this.sendBackendStatusUpdate();
        return;
      }

      console.log('Launching backend from:', exePath);
      this.backendProcess = spawn(exePath, [], {
        env: { ...process.env, HOST: '127.0.0.1', PORT: '8000' }
      });
    }

    // Common event handlers for the backend process
    this.backendProcess.stdout.on('data', (data) => {
      const output = data.toString().trim();
      console.log(`[Backend] ${output}`);
      this.backendLogs.push(output);

      if (this.backendState !== 'running' && (output.includes('Uvicorn running') || output.includes('Application startup complete'))) {
        console.log('✅ Backend is ready!');
        this.backendState = 'running';
      }
      this.sendBackendStatusUpdate();
    });

    this.backendProcess.stderr.on('data', (data) => {
      const errorOutput = data.toString().trim();
      console.error(`[Backend ERROR] ${errorOutput}`);
      this.backendLogs.push(`ERROR: ${errorOutput}`);
      this.backendState = 'error';
      this.sendBackendStatusUpdate();
    });

    this.backendProcess.on('error', (err) => {
      const errorMsg = `FATAL: Failed to start backend process: ${err.message}`;
      console.error(errorMsg);
      this.backendLogs.push(errorMsg);
      this.backendState = 'error';
      this.sendBackendStatusUpdate();
    });

    this.backendProcess.on('exit', (code) => {
      // Only flag as an error if it wasn't a clean shutdown or a planned restart
      if (code !== 0 && this.backendState !== 'stopped') {
        const errorMsg = `Backend process exited unexpectedly with code ${code}`;
        console.error(errorMsg);
        this.backendLogs.push(errorMsg);
        this.backendState = 'error';
        this.sendBackendStatusUpdate();
      }
    });
  }

  getFrontendPath() {
    const isDev = !app.isPackaged;

    if (isDev) {
      return 'http://localhost:3000';
    }

    // FIXED: In production, the frontend files are in app/web-ui-build/out/
    // When packaged in app.asar, use app.getAppPath() to get the asar location
    // The files are included via the files array in package.json
    const indexPath = path.join(app.getAppPath(), 'web-ui-build', 'out', 'index.html');

    console.log('DEBUG [Frontend Path Resolution]:');
    console.log('  app.isPackaged:', app.isPackaged);
    console.log('  app.getAppPath():', app.getAppPath());
    console.log('  Resolved path:', indexPath);
    console.log('  File exists:', fs.existsSync(indexPath));

    // If not found, list what's actually there for debugging
    if (!fs.existsSync(indexPath)) {
      const appPath = app.getAppPath();
      try {
        console.error('Contents of app directory:');
        const listDir = (dir, depth = 0) => {
          if (depth > 3) return; // Limit recursion
          try {
            const files = fs.readdirSync(dir);
            files.forEach(file => {
              const fullPath = path.join(dir, file);
              const indent = '  '.repeat(depth);
              if (fs.statSync(fullPath).isDirectory()) {
                console.error(`${indent}📁 ${file}/`);
                listDir(fullPath, depth + 1);
              } else {
                console.error(`${indent}📄 ${file}`);
              }
            });
          } catch (err) {
            console.error(`Error listing ${dir}:`, err.message);
          }
        };
        listDir(appPath);
      } catch (err) {
        console.error('Could not list app directory:', err);
      }
    }

    return `file://${indexPath}`;
  }

  createMainWindow() {
    this.mainWindow = new BrowserWindow({
      width: 1600,
      height: 1000,
      title: 'Fortuna Faucet - Racing Analysis',
      icon: path.join(__dirname, 'assets', 'icon.ico'),
      webPreferences: {
        nodeIntegration: false,
        contextIsolation: true,
        preload: path.join(__dirname, 'preload.js')
      },
      autoHideMenuBar: true,
      backgroundColor: '#1a1a2e'
    });

    const isDev = !app.isPackaged;

    if (isDev) {
      // Development: load from Next.js dev server
      console.log('[DEV MODE] Loading frontend from http://localhost:3000');
      this.mainWindow.loadURL('http://localhost:3000');

      // Open DevTools in development
      this.mainWindow.webContents.openDevTools();
    } else {
      // Production: load from bundled static files
      const frontendUrl = this.getFrontendPath();

      if (!frontendUrl.startsWith('http') && !fs.existsSync(frontendUrl.replace('file://', ''))) {
        console.error('FATAL: Frontend index.html not found!');

        // Show error dialog to user
        const { dialog } = require('electron');
        dialog.showErrorBox(
          'Installation Error',
          'The application frontend is missing. Please reinstall Fortuna Faucet.'
        );
        app.quit();
        return;
      }

      console.log('[PROD MODE] Loading frontend from:', frontendUrl);
      this.mainWindow.loadURL(frontendUrl);
    }

    // Handle window close - keep running in tray
    this.mainWindow.on('close', (event) => {
      if (!app.isQuitting) {
        event.preventDefault();
        this.mainWindow.hide();
      }
    });
  }

  createSystemTray() {
    const iconPath = path.join(__dirname, 'assets', 'tray-icon.png');

    // Create tray icon (with fallback if missing)
    let icon;
    if (fs.existsSync(iconPath)) {
      icon = nativeImage.createFromPath(iconPath).resize({ width: 16, height: 16 });
    } else {
      console.warn('Tray icon not found, using default');
      icon = nativeImage.createEmpty();
    }

    this.tray = new Tray(icon);

    const contextMenu = Menu.buildFromTemplate([
      {
        label: 'Open Dashboard',
        click: () => {
          this.mainWindow.show();
          this.mainWindow.focus();
        }
      },
      { type: 'separator' },
      {
        label: 'Backend Status',
        enabled: false
      },
      {
        label: this.backendProcess && !this.backendProcess.killed ? '✅ Running' : '❌ Stopped',
        enabled: false
      },
      { type: 'separator' },
      {
        label: 'Exit',
        click: () => {
          app.isQuitting = true;
          app.quit();
        }
      }
    ]);

    this.tray.setToolTip('Fortuna Faucet - Racing Analysis');
    this.tray.setContextMenu(contextMenu);

    // Double-click tray icon to show window
    this.tray.on('double-click', () => {
      this.mainWindow.show();
      this.mainWindow.focus();
    });
  }

  initialize() {
    console.log('=== Fortuna Faucet Initializing ===');

    // Create the window immediately
    this.createMainWindow();
    this.createSystemTray();

    // Start the backend in parallel
    this.startBackend();

    // Set up IPC listener for restart command
    ipcMain.on('restart-backend', (event) => {
      console.log('Received restart-backend command from frontend.');
      this.backendLogs.push('Restart command received. Attempting to restart backend...');
      this.startBackend(); // This will kill the old process and start a new one
    });

    // Add a handler for the frontend to request the current status on load
    ipcMain.handle('get-backend-status', async (event) => {
      console.log('Received get-backend-status request from frontend.');
      return {
        state: this.backendState,
        logs: this.backendLogs.slice(-20)
      };
    });

    console.log('✅ Fortuna Faucet UI initialized. Backend starting in background...');
  }

  cleanup() {
    console.log('Cleaning up processes...');

    if (this.backendProcess && !this.backendProcess.killed) {
      console.log('Stopping backend process...');
      this.backendProcess.kill();
    }
  }
}

let fortunaApp;

app.whenReady().then(() => {
  fortunaApp = new FortunaDesktopApp();
  fortunaApp.initialize();
});

// macOS: re-create window when dock icon is clicked
app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    fortunaApp.createMainWindow();
  } else {
    fortunaApp.mainWindow.show();
  }
});

// Don't quit on window close (run in tray)
app.on('window-all-closed', () => {
  // On Windows/Linux, keep running in system tray
  // On macOS, it's common to quit when all windows are closed
  if (process.platform === 'darwin') {
    app.quit();
  }
});

// Clean up on quit
app.on('before-quit', () => {
  if (fortunaApp) {
    fortunaApp.cleanup();
  }
});
