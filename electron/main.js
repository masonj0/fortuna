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
    if (this.isBackendStarting) {
      console.log('Backend start already in progress. Ignoring request.');
      return;
    }

    this.isBackendStarting = true;
    this.backendState = 'starting';
    this.backendLogs = ['Attempting to start backend...'];
    this.sendBackendStatusUpdate();

    const port = process.env.FORTUNA_PORT || 8000;

    try {
      const isPortInUse = await this.checkPortInUse(port);
      if (isPortInUse) {
        console.log(`Port ${port} is already in use. Assuming backend is running.`);
        this.backendState = 'running';
        this.backendLogs.push(`Port ${port} is already in use. Assuming backend is running.`);
        this.isBackendStarting = false;
        this.sendBackendStatusUpdate();
        return; // The most important change: we just stop here.
      }
    } catch (error) {
        const errorMsg = `Error checking port ${port}: ${error.message}`;
        console.error(errorMsg);
        this.backendState = 'error';
        this.backendLogs.push(errorMsg);
        this.isBackendStarting = false;
        this.sendBackendStatusUpdate();
        dialog.showErrorBox('Network Error', `Could not check port ${port}. Please check your network configuration.`);
        return;
    }

    if (this.backendProcess && !this.backendProcess.killed) {
      console.log('An old backend process was found. Terminating it before starting a new one.');
      this.backendProcess.kill();
    }

    const isDev = !app.isPackaged;
    let backendCommand;
    const backendArgs = [];
    let backendCwd = process.cwd();

    if (isDev) {
      // This logic remains the same for development
      console.log('[DEV MODE] Configuring backend to run from Python venv...');
      backendCommand = path.join(__dirname, '..', '.venv', 'Scripts', 'python.exe');
      backendArgs.push('-m', 'uvicorn', 'api:app', '--host', '127.0.0.1', '--port', port);
      backendCwd = path.join(__dirname, '..', 'python_service');
    } else {
      console.log('[PROD MODE] Configuring backend to run from packaged executable...');
      backendCommand = path.join(process.resourcesPath, 'python-service-bin', 'fortuna-backend.exe');
    }

    if (!fs.existsSync(backendCommand)) {
      const errorMsg = `FATAL: Backend executable not found at ${backendCommand}`;
      console.error(errorMsg);
      this.backendState = 'error';
      this.backendLogs.push(errorMsg);
      this.isBackendStarting = false;
      this.sendBackendStatusUpdate();
      dialog.showErrorBox('Backend Missing', 'The backend service executable is missing. Please try reinstalling Fortuna Faucet.');
      return;
    }

    console.log(`Spawning backend: ${backendCommand} ${backendArgs.join(' ')}`);
    this.backendProcess = spawn(backendCommand, backendArgs, {
      cwd: backendCwd,
      env: { ...process.env, FORTUNA_PORT: port.toString() },
      stdio: ['ignore', 'pipe', 'pipe'],
    });

    this.backendProcess.stdout.on('data', (data) => {
      const output = data.toString().trim();
      console.log(`[Backend] ${output}`);
      this.backendLogs.push(output);
      if (this.backendState !== 'running' && output.includes('Application startup complete')) {
        console.log('✅ Backend is ready!');
        this.backendState = 'running';
        this.isBackendStarting = false;
      }
      this.sendBackendStatusUpdate();
    });

 this.backendProcess.stderr.on('data', (data) => {
 const errorOutput = data.toString().trim();
 console.error(`[Backend ERROR] ${errorOutput}`);
 this.backendLogs.push(`ERROR: ${errorOutput}`);
 this.backendState = 'error';
 this.isBackendStarting = false;
 this.sendBackendStatusUpdate();
 });

 this.backendProcess.on('error', (err) => {
 const errorMsg = `FATAL: Failed to start backend process: ${err.message}`;
 console.error(errorMsg);
 this.backendLogs.push(errorMsg);
 this.backendState = 'error';
 this.isBackendStarting = false;
 this.sendBackendStatusUpdate();
 });

 this.backendProcess.on('exit', (code) => {
 if (code !== 0 && this.backendState !== 'stopped') {
 const errorMsg = `Backend process exited unexpectedly with code ${code}`;
 console.error(errorMsg);
 this.backendLogs.push(errorMsg);
 this.backendState = 'error';
 this.isBackendStarting = false;
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
