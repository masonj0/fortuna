// electron/main.js
const { app, BrowserWindow, Tray, Menu, nativeImage, dialog, ipcMain } = require('electron');
const { spawn, execFile } = require('child_process');
const path = require('path');
const fs = require('fs');

/**
 * A centralized function to show a critical error message to the user
 * and then safely quit the application.
 * @param {string} title - The title for the error dialog.
 * @param {string} message - The main content of the error message.
 */
function showCriticalError(title, message) {
  console.error(`[CRITICAL ERROR] ${title}: ${message}`);
  dialog.showErrorBox(title, message);
  app.quit();
}

class FortunaDesktopApp {
  constructor() {
    this.mainWindow = null;
    this.tray = null;
    this.backendProcess = null;

    if (!app.requestSingleInstanceLock()) {
      app.quit();
    } else {
      app.on('second-instance', () => {
        if (this.mainWindow) {
          if (this.mainWindow.isMinimized()) this.mainWindow.restore();
          this.mainWindow.focus();
        }
      });
    }
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
      backgroundColor: '#1a1a2e',
      show: false // Window is created hidden and shown only when ready
    });

    this.mainWindow.on('close', (event) => {
      if (!app.isQuitting) {
        event.preventDefault();
        this.mainWindow.hide();
      }
    });

    if (!app.isPackaged) {
      this.mainWindow.loadURL('http://localhost:3000');
    } else {
      this.mainWindow.loadFile(path.join(__dirname, '..', 'web-ui-build', 'out', 'index.html'));
    }
  }

  createSystemTray() {
    const iconPath = path.join(__dirname, 'assets', 'tray-icon.png');
    const icon = nativeImage.createFromPath(iconPath);
    this.tray = new Tray(icon.resize({ width: 16, height: 16 }));

    const contextMenu = Menu.buildFromTemplate([
      { label: 'Show Dashboard', click: () => this.showWindow() },
      { type: 'separator' },
      { label: 'Quit Fortuna Faucet', click: () => this.quitApp() }
    ]);

    this.tray.setToolTip('Fortuna Faucet - Monitoring Races');
    this.tray.setContextMenu(contextMenu);
    this.tray.on('double-click', () => this.showWindow());
  }

  showWindow() {
    if (this.mainWindow) {
      this.mainWindow.show();
      this.mainWindow.focus();
    }
  }

  quitApp() {
    app.isQuitting = true;
    app.quit();
  }

  startBackend() {
    return new Promise((resolve, reject) => {
      const platform = process.platform;
      const backendExe = platform === 'win32' ? 'fortuna-backend.exe' : 'fortuna-backend';
      let executablePath;

      if (!app.isPackaged) {
        // DEVELOPMENT: Run via Python script runner
        executablePath = path.join(process.cwd(), '..', '.venv', 'Scripts', 'python.exe');
        const scriptPath = path.join(process.cwd(), '..', 'run_backend.py');
        this.backendProcess = spawn(executablePath, [scriptPath], { cwd: path.join(process.cwd(), '..') });
      } else {
        // PRODUCTION: Run the packaged executable
        // path.join(__dirname) points to the root of app.asar
        // The executable is unpacked into a sibling directory 'app.asar.unpacked'
        executablePath = path.join(path.dirname(app.getAppPath()), 'app.asar.unpacked', 'resources', backendExe);

        console.log(`[Backend Starter] Attempting to launch production backend at: ${executablePath}`);

        if (!fs.existsSync(executablePath)) {
          return reject(new Error(`Backend executable not found. The application is corrupted or installed incorrectly. Expected at: ${executablePath}`));
        }

        this.backendProcess = spawn(executablePath, [], {
          // CRITICAL: Set CWD to the executable's directory to find bundled resources
          cwd: path.dirname(executablePath)
        });
      }

      let stdoutBuffer = '';
      let startupResolved = false;

      // Safety timeout for backend startup
      const startupTimeout = setTimeout(() => {
        if (!startupResolved) {
          startupResolved = true;
          reject(new Error(`Backend process failed to start within 30 seconds. Timeout exceeded. \n---LOGS---\n${stdoutBuffer}`));
        }
      }, 30000);

      this.backendProcess.stdout.on('data', (data) => {
        const logMsg = data.toString();
        stdoutBuffer += logMsg;
        console.log(`[Backend] ${logMsg.trim()}`);
        // Look for the Uvicorn startup message as the success signal
        if (!startupResolved && logMsg.includes('Uvicorn running on')) {
          startupResolved = true;
          clearTimeout(startupTimeout);
          console.log('[Backend Starter] Backend startup signal detected.');
          resolve();
        }
      });

      this.backendProcess.stderr.on('data', (data) => {
        console.error(`[Backend STDERR] ${data.toString().trim()}`);
      });

      this.backendProcess.on('error', (err) => {
        if (!startupResolved) {
          startupResolved = true;
          clearTimeout(startupTimeout);
          reject(new Error(`Failed to spawn backend process. Error: ${err.message}`));
        }
      });

      this.backendProcess.on('close', (code) => {
        console.log(`[Backend] Process exited with code ${code}`);
        if (!startupResolved) {
          startupResolved = true;
          clearTimeout(startupTimeout);
          reject(new Error(`Backend process exited prematurely with code ${code} before sending startup signal. \n---LOGS---\n${stdoutBuffer}`));
        }
      });
    });
  }

  async initialize() {
    this.createSystemTray();

    // The UI now waits for the backend to start.
    try {
      console.log('Attempting to start backend...');
      await this.startBackend();
      console.log('Backend started successfully. Creating main window...');

      this.createMainWindow();
      this.mainWindow.once('ready-to-show', () => {
        this.mainWindow.show();
      });

    } catch (error) {
      showCriticalError(
        'Application Startup Failed',
        `The backend service could not be started, so the application cannot run.\n\nDetails: ${error.message}`
      );
    }
  }

  cleanup() {
    console.log('Cleaning up backend process...');
    if (this.backendProcess) {
      // Use 'taskkill' on Windows for a more forceful termination
      if (process.platform === "win32") {
        spawn("taskkill", ["/pid", this.backendProcess.pid, '/f', '/t']);
      } else {
        this.backendProcess.kill();
      }
    }
  }
}

let fortunaApp;

app.whenReady().then(() => {
  ipcMain.handle('get-api-key', () => {
    // This is a placeholder for future secure key handling
    return process.env.API_KEY || null;
  });

  fortunaApp = new FortunaDesktopApp();
  fortunaApp.initialize();
});

app.on('window-all-closed', (event) => {
  event.preventDefault(); // Keep the app running in the tray
});

app.on('before-quit', () => {
  if (fortunaApp) {
    fortunaApp.cleanup();
  }
});
