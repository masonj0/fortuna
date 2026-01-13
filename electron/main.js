// electron/main.js - CORRECTED VERSION
const { app, BrowserWindow, Tray, Menu, nativeImage, ipcMain, dialog } = require('electron');
const { autoUpdater } = require('electron-updater');
const { spawn } = require('child_process');
const net = require('net');
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
 this.isBackendStarting = false;
 }

 sendBackendStatusUpdate() {
 if (this.mainWindow) {
 this.mainWindow.webContents.send('backend-status-update', {
 state: this.backendState,
 logs: this.backendLogs.slice(-20) // Send last 20 log entries
 });
 }
 }

 stopBackend() {
 if (this.backendProcess && !this.backendProcess.killed) {
 console.log('Stopping backend process...');
 this.backendProcess.kill();
 this.backendState = 'stopped';
 this.isBackendStarting = false; // Ensure lock is released on stop
 this.backendLogs.push('Backend process stopped by user.');
 this.sendBackendStatusUpdate();
 }
 }

  checkPortInUse(port) {
    return new Promise((resolve, reject) => {
      const server = net.createServer();
      server.once('error', (err) => {
        if (err.code === 'EADDRINUSE') {
          resolve(true); // Port is in use
        } else {
          reject(err);
        }
      });
      server.once('listening', () => {
        server.close(() => {
          resolve(false); // Port is free
        });
      });
      server.listen(port, '127.0.0.1');
    });
  }

  async waitForBackend(maxRetries = 30) {
    const port = process.env.FORTUNA_PORT || 8000;
    const url = `http://127.0.0.1:${port}/health`;

    console.log(`[Backend Check] Starting health check at: ${url}`);

    for (let i = 0; i < maxRetries; i++) {
      try {
        const response = await fetch(url, { timeout: 3000 });
        console.log(`[Backend Check] Attempt ${i}: Status ${response.status}`);

        if (response.ok) {
          console.log('✅ Backend is healthy and responding');
          return true;
        }
      } catch (e) {
        console.log(`[Backend Check] Attempt ${i} failed: ${e.message}`);

        // Check if process is still alive
        if (this.backendProcess && !this.backendProcess.killed) {
          console.log(`[Backend Check] Process still running (PID: ${this.backendProcess.pid})`);
        } else {
          console.error(`[Backend Check] ⚠️  Backend process is DEAD!`);
          console.error(`[Backend Check] Last logs:`, this.backendLogs.slice(-5));
          throw new Error(`Backend process died. Last logs:\\n${this.backendLogs.slice(-5).join('\\n')}`);
        }

        await new Promise(r => setTimeout(r, 1000));
      }
    }

    throw new Error(`Backend failed to respond at ${url} after 30 seconds`);
  }

  async startBackend() {
    const isDev = !app.isPackaged;
    let backendCommand;
    let backendCwd;

    if (isDev) {
      console.log('[DEV MODE] Configuring backend...');
      backendCommand = path.join(__dirname, '..', '.venv', 'Scripts', 'python.exe');
      backendCwd = path.join(__dirname, '..', 'web_service', 'backend');
    } else {
      const backendFolder = path.join(process.resourcesPath, 'fortuna-webservice');
      backendCommand = path.join(backendFolder, 'fortuna-webservice.exe');
      backendCwd = backendFolder;

      console.log(`[Backend] Looking for executable at: ${backendCommand}`);
      console.log(`[Backend] Directory exists: ${fs.existsSync(backendFolder)}`);
      console.log(`[Backend] Executable exists: ${fs.existsSync(backendCommand)}`);
    }

    if (!fs.existsSync(backendCommand)) {
      const errorMsg = `Backend executable not found at: ${backendCommand}`;
      console.error(`[Backend] ${errorMsg}`);
      this.backendLogs.push(`ERROR: ${errorMsg}`);
      this.backendState = 'error';
      dialog.showErrorBox(
        'Backend Launch Failed',
        `Could not find backend executable.\\n\\nExpected location:\\n${backendCommand}`
      );
      return;
    }

    console.log(`[Backend] Executable found, attempting to spawn...`);

    this.backendProcess = spawn(backendCommand, [], {
      cwd: backendCwd,
      windowsHide: true,
      env: {
        ...process.env,
        FORTUNA_MODE: 'electron',
        PYTHONPATH: backendCwd
      }
    });

    this.backendState = 'starting';
    this.isBackendStarting = true;

    this.backendProcess.stdout.on('data', (data) => {
      const output = data.toString().trim();
      console.log(`[Backend STDOUT] ${output}`);
      this.backendLogs.push(output);

      // Detect successful startup from log messages
      if (output.includes('Application startup complete') || output.includes('Uvicorn running')) {
        if (this.backendState !== 'running') {
          console.log('✅ Backend reported successful startup');
          this.backendState = 'running';
          this.isBackendStarting = false;
        }
      }

      this.sendBackendStatusUpdate();
    });

    this.backendProcess.stderr.on('data', (data) => {
      const errorOutput = data.toString().trim();
      console.error(`[Backend STDERR] ${errorOutput}`);
      this.backendLogs.push(`ERROR: ${errorOutput}`);

      if (this.backendState === 'starting') {
        this.backendState = 'error';
        this.isBackendStarting = false;
      }

      this.sendBackendStatusUpdate();
    });

    this.backendProcess.on('error', (err) => {
      const errorMsg = `Failed to spawn backend process: ${err.message}`;
      console.error(`[Backend] ${errorMsg}`);
      this.backendLogs.push(`ERROR: ${errorMsg}`);
      this.backendState = 'error';
      this.isBackendStarting = false;
      this.sendBackendStatusUpdate();
    });

    this.backendProcess.on('exit', (code) => {
      if (code !== 0 && this.backendState !== 'stopped') {
        console.error(`[CRITICAL] Backend process exited with code: ${code}`);
        console.error(`[CRITICAL] Last 10 logs:`, this.backendLogs.slice(-10));

        // Save logs for debugging
        const logFile = path.join(require('os').homedir(), '.fortuna', 'backend_crash.log');
        fs.mkdirSync(path.dirname(logFile), { recursive: true });
        fs.writeFileSync(logFile, this.backendLogs.join('\\n'));
        console.error(`[CRITICAL] Full logs saved to: ${logFile}`);

        this.backendState = 'error';
        this.isBackendStarting = false;
        this.sendBackendStatusUpdate();
      }
    });
  }

  getFrontendPath() {
    // UNIFIED: Always serve from the backend
    const port = process.env.FORTUNA_PORT || 8000;
    return `http://127.0.0.1:${port}/`;
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
    console.log('[Electron] Initializing Fortuna application...');

    this.createMainWindow();
    this.createSystemTray();
    this.startBackend();

    // Wait for backend to be ready, then load the unified frontend
    this.waitForBackend()
      .then(() => {
        console.log('[Electron] Backend is ready, loading frontend...');
        const frontendUrl = this.getFrontendPath();
        console.log(`[Electron] Loading frontend from: ${frontendUrl}`);
        this.mainWindow.loadURL(frontendUrl);
      })
      .catch((err) => {
        console.error('[Electron] Backend startup failed:', err);
        dialog.showErrorBox(
          'Backend Error',
          'Failed to start backend service:\\n\\n' + err.message
        );
      });

    // Check for updates
    autoUpdater.checkForUpdatesAndNotify();

    autoUpdater.on('update-downloaded', (info) => {
      const dialogOpts = {
        type: 'info',
        buttons: ['Restart', 'Later'],
        title: 'Application Update',
        message: process.platform === 'win32' ? info.releaseName : info.releaseName,
        detail: 'A new version has been downloaded. Restart the application to apply the updates.'
      };

      dialog.showMessageBox(dialogOpts).then((returnValue) => {
        if (returnValue.response === 0) autoUpdater.quitAndInstall();
      });
    });

    ipcMain.on('restart-backend', () => this.startBackend());
    ipcMain.on('stop-backend', () => this.stopBackend());
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

    ipcMain.handle('get-api-port', () => {
      return process.env.FORTUNA_PORT || 8000;
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
  // Harden the session for security
  const { session } = require('electron');
  const ses = session.defaultSession;

  // 1. Content-Security-Policy
  ses.webRequest.onHeadersReceived((details, callback) => {
    callback({
      responseHeaders: {
        ...details.responseHeaders,
        'Content-Security-Policy': [
          "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self' data:; connect-src 'self' http://127.0.0.1:*"
        ]
      }
    });
  });

  // 2. Permission Request Handler
  ses.setPermissionRequestHandler((webContents, permission, callback) => {
    const allowedPermissions = ['clipboard-read', 'clipboard-sanitized-write'];
    if (allowedPermissions.includes(permission)) {
      callback(true); // Grant allowed permissions
    } else {
      console.warn(`[SECURITY] Denied permission request for: ${permission}`);
      callback(false); // Deny all others by default
    }
  });

  // 3. Certificate Pinning (TODO)
  // Certificate pinning would be implemented here. It is commented out
  // because it requires a known certificate hash and would break local dev.
  // ses.setCertificateVerifyProc((request, callback) => {
  //   const { hostname, certificate, verificationResult } = request;
  //   if (hostname === 'api.fortuna.faucet') {
  //     // TODO: Replace with actual certificate fingerprint
  //     const expectedFingerprint = '...';
  //     if (certificate.fingerprint === expectedFingerprint) {
  //       callback(0); // 0 means success
  //     } else {
  //       callback(-2); // -2 means failure
  //     }
  //   } else {
  //     callback(0); // Allow other domains
  //   }
  // });

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
