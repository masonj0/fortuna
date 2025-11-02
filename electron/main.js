// electron/main.js - CORRECTED VERSION
const { app, BrowserWindow, Tray, Menu, nativeImage } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

class FortunaDesktopApp {
  constructor() {
    this.backendProcess = null;
    this.mainWindow = null;
    this.tray = null;
  }

  async startBackend() {
    return new Promise((resolve, reject) => {
      const isDev = !app.isPackaged;

      if (isDev) {
        // Development: use Python venv
        console.log('[DEV MODE] Starting backend from Python venv...');
        const pythonPath = path.join(__dirname, '..', '.venv', 'Scripts', 'python.exe');
        const apiPath = path.join(__dirname, '..', 'python_service', 'api.py');

        if (!fs.existsSync(pythonPath)) {
          console.error('FATAL: Python executable not found at:', pythonPath);
          reject(new Error('Python venv not found. Run setup first.'));
          return;
        }

        this.backendProcess = spawn(pythonPath, [
          '-m', 'uvicorn',
          'api:app',
          '--host', '127.0.0.1',
          '--port', '8000'
        ], {
          cwd: path.join(__dirname, '..', 'python_service'),
          env: process.env
        });
      } else {
        // Production: use PyInstaller exe
        console.log('[PROD MODE] Starting backend from packaged executable...');
        const exePath = path.join(process.resourcesPath, 'fortuna-backend.exe');

        if (!fs.existsSync(exePath)) {
          console.error('FATAL: Backend executable not found at:', exePath);
          console.error('process.resourcesPath:', process.resourcesPath);
          console.error('Expected path:', exePath);
          reject(new Error('Backend executable missing from installation'));
          return;
        }

        console.log('Launching backend from:', exePath);
        const exeSize = fs.statSync(exePath).size / (1024 * 1024);
        console.log(`Backend executable size: ${exeSize.toFixed(2)} MB`);

        this.backendProcess = spawn(exePath, [], {
          env: {
            ...process.env,
            HOST: '127.0.0.1',
            PORT: '8000'
          }
        });
      }

      // Handle stdout
      this.backendProcess.stdout.on('data', (data) => {
        const output = data.toString();
        console.log(`[Backend] ${output}`);

        // Resolve when server is ready
        if (output.includes('Uvicorn running') ||
            output.includes('Application startup complete') ||
            output.includes('Started server process')) {
          console.log('✅ Backend is ready!');
          resolve();
        }
      });

      // Handle stderr
      this.backendProcess.stderr.on('data', (data) => {
        console.error(`[Backend ERROR] ${data}`);
      });

      // Handle process errors
      this.backendProcess.on('error', (err) => {
        console.error('Failed to start backend process:', err);
        reject(err);
      });

      // Handle unexpected exit
      this.backendProcess.on('exit', (code, signal) => {
        if (code !== 0) {
          console.error(`Backend process exited with code ${code}, signal ${signal}`);
        }
      });

      // Timeout fallback (in case startup message is missed)
      setTimeout(() => {
        if (this.backendProcess && !this.backendProcess.killed) {
          console.log('⚠️ Backend startup timeout - assuming it started successfully');
          resolve();
        }
      }, 10000); // 10 second timeout
    });
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
      const indexPath = path.join(__dirname, 'web-ui-build', 'out', 'index.html');

      if (!fs.existsSync(indexPath)) {
        console.error('FATAL: Frontend index.html not found at:', indexPath);
        console.error('__dirname:', __dirname);
        console.error('Expected path:', indexPath);

        // Show error dialog to user
        const { dialog } = require('electron');
        dialog.showErrorBox(
          'Installation Error',
          'The application frontend is missing. Please reinstall Fortuna Faucet.'
        );
        app.quit();
        return;
      }

      console.log('[PROD MODE] Loading frontend from:', indexPath);
      this.mainWindow.loadFile(indexPath);
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

  async initialize() {
    try {
      console.log('=== Fortuna Faucet Starting ===');
      console.log('Mode:', !app.isPackaged ? 'Development' : 'Production');
      console.log('Platform:', process.platform);
      console.log('Electron version:', process.versions.electron);

      console.log('\n[1/3] Starting backend...');
      await this.startBackend();

      console.log('\n[2/3] Creating main window...');
      this.createMainWindow();

      console.log('\n[3/3] Creating system tray...');
      this.createSystemTray();

      console.log('\n✅ Fortuna Faucet initialized successfully!');
    } catch (error) {
      console.error('FATAL ERROR during initialization:', error);

      const { dialog } = require('electron');
      dialog.showErrorBox(
        'Startup Error',
        `Fortuna Faucet failed to start:\n\n${error.message}\n\nPlease check the logs and try again.`
      );

      app.quit();
    }
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
