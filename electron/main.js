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

async startBackend() {
    // ... existing port checks ...

    const isDev = !app.isPackaged;
    let backendCommand;
    let backendCwd = process.cwd();

    if (isDev) {
        console.log('[DEV MODE] Configuring backend...');
        backendCommand = path.join(__dirname, '..', '.venv', 'Scripts', 'python.exe');
        backendCwd = path.join(__dirname, '..', 'python_service');
    } else {
        console.log('[PROD MODE] Resolving backend via resourcesPath...');
        // Standard location for extraResources in a production MSI
        backendCommand = path.join(process.resourcesPath, 'resources', 'fortuna-backend.exe');

        // Failsafe check for flattened directory structures
        if (!fs.existsSync(backendCommand)) {
            backendCommand = path.join(process.resourcesPath, 'fortuna-backend.exe');
        }
        backendCwd = path.dirname(backendCommand);
    }

    if (!fs.existsSync(backendCommand)) {
        dialog.showErrorBox('Backend Missing', `Executable not found at: ${backendCommand}`);
        return;
    }

    this.backendProcess = spawn(backendCommand, [], { cwd: backendCwd });
    // ... remaining stdout/stderr logic ...
}

getFrontendPath() {
    if (!app.isPackaged) return 'http://localhost:3000';

    // Ensure the path points to 'out' folder inside the app package
    const indexPath = path.join(app.getAppPath(), 'out', 'index.html');
    const { pathToFileURL } = require('url');
    return pathToFileURL(indexPath).toString();
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
  ipcMain.handle('get-api-port', () => {
    return process.env.FORTUNA_PORT || 8000;
  });
 this.createMainWindow();
 this.createSystemTray();
 this.startBackend();

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
