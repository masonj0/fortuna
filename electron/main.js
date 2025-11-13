// electron/main.js - CORRECTED VERSION
const { app, BrowserWindow, Tray, Menu, nativeImage, ipcMain } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const SecureSettingsManager = require('./secure-settings-manager');

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
    let backendCommand;
    let backendArgs = [];
    let backendCwd = process.cwd();

    if (isDev) {
      console.log('[DEV MODE] Configuring backend to run from Python venv...');
      backendCommand = path.join(__dirname, '..', '.venv', 'Scripts', 'python.exe');
      backendArgs = ['-m', 'uvicorn', 'api:app', '--host', '127.0.0.1', '--port', '8000'];
      backendCwd = path.join(__dirname, '..', 'python_service');

      if (!fs.existsSync(backendCommand)) {
        const errorMsg = `FATAL: Python executable for dev not found at ${backendCommand}. Run setup first.`;
        this.backendState = 'error';
        this.backendLogs.push(errorMsg);
        this.sendBackendStatusUpdate();
        return;
      }
    } else {
      console.log('[PROD MODE] Configuring backend to run from packaged executable...');
      backendCommand = path.join(process.resourcesPath, 'fortuna-backend.exe');
      if (!fs.existsSync(backendCommand)) {
        const errorMsg = `FATAL: Backend executable missing at ${backendCommand}`;
        console.error(errorMsg);
        this.backendState = 'error';
        this.backendLogs.push(errorMsg);
        this.sendBackendStatusUpdate();
        const { dialog } = require('electron');
        dialog.showErrorBox(
          'Backend Missing',
          'The backend service is missing. Please reinstall Fortuna Faucet.'
        );
        return;
      }
    }

    console.log(`Spawning backend: ${backendCommand} ${backendArgs.join(' ')}`);
    this.backendProcess = spawn(backendCommand, backendArgs, {
      cwd: backendCwd,
      env: { ...process.env, HOST: '127.0.0.1', PORT: '8000' },
      stdio: ['ignore', 'pipe', 'pipe']
    });

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

    const indexPath = path.join(app.getAppPath(), 'web-ui-build', 'out', 'index.html');
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

    const frontendUrl = this.getFrontendPath();
    this.mainWindow.loadURL(frontendUrl);

    if (!app.isPackaged) {
      this.mainWindow.webContents.openDevTools();
    }

    this.mainWindow.on('close', (event) => {
      if (!app.isQuitting) {
        event.preventDefault();
        this.mainWindow.hide();
      }
    });
  }

  createSystemTray() {
    // ... (rest of the file is unchanged)
  }

  initialize() {
    this.createMainWindow();
    this.createSystemTray();
    this.startBackend();

    ipcMain.on('restart-backend', () => this.startBackend());
    ipcMain.handle('get-backend-status', async () => ({
      state: this.backendState,
      logs: this.backendLogs.slice(-20)
    }));

    ipcMain.handle('get-api-key', async () => {
      return SecureSettingsManager.getApiKey();
    });

    ipcMain.handle('generate-api-key', async () => {
      const crypto = require('node:crypto');
      const newKey = crypto.randomBytes(16).toString('hex');
      SecureSettingsManager.saveApiKey(newKey);
      return newKey;
    });

    ipcMain.handle('save-api-key', async (event, apiKey) => {
      return SecureSettingsManager.saveApiKey(apiKey);
    });

    ipcMain.handle('save-betfair-credentials', async (event, credentials) => {
      return SecureSettingsManager.saveBetfairCredentials(credentials);
    });
  }

  cleanup() {
    if (this.backendProcess && !this.backendProcess.killed) {
      this.backendProcess.kill();
    }
  }
}

let fortunaApp;

app.whenReady().then(() => {
  fortunaApp = new FortunaDesktopApp();
  fortunaApp.initialize();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    // Do nothing, keep app running in tray
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    fortunaApp.createMainWindow();
  } else {
    fortunaApp.mainWindow.show();
  }
});

app.on('before-quit', () => {
  app.isQuitting = true;
  if (fortunaApp) {
    fortunaApp.cleanup();
  }
});
