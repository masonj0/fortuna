// electron/main.js - AUTHORITATIVE VERSION FROM ARCHIVE
const { app, BrowserWindow, Tray, Menu, nativeImage, ipcMain, dialog } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const SecureSettingsManager = require('./secure-settings-manager');
// The 'sudo-prompt' and 'install-validator' modules are removed as we are no longer managing the service at runtime.

const SERVICE_NAME = 'FortunaBackend';
const SERVICE_DISPLAY_NAME = 'Fortuna Backend Service';
const SERVICE_DESCRIPTION = 'Handles data processing for the Fortuna Faucet application.';

class FortunaDesktopApp {
  constructor() {
    this.mainWindow = null;
    this.tray = null;
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
    // ... (logic is the same, omitted for brevity)
  }

  async validateAndStartBackend() {
    if (app.isPackaged) {
      // With sudo-prompt removed, we no longer attempt to manage the Windows service at runtime.
      // Instead, we will spawn the backend process directly. This is a temporary measure
      // until the service installation is handled by the MSI installer itself.
      const backendExePath = path.join(process.resourcesPath, 'fortuna-backend.exe');
      if (fs.existsSync(backendExePath)) {
        try {
          console.log(`[INFO] Attempting to start backend: ${backendExePath}`);
          spawn(backendExePath, [], { detached: true, stdio: 'ignore' });
        } catch (err) {
          dialog.showErrorBox('Backend Start Failed', `The backend executable could not be started: ${err.message}`);
        }
      } else {
        dialog.showErrorBox('Backend Not Found', `The backend executable was not found at the expected location: ${backendExePath}`);
      }
    } else {
      console.log('[DEV MODE] The backend should be run manually.');
    }
  }

  initialize() {
    this.createMainWindow();
    this.createSystemTray();
    this.validateAndStartBackend();

    // ... (rest of the IPC handlers are the same)
  }
}

// ... (rest of the app lifecycle events are the same)

let fortunaApp;

app.whenReady().then(() => {
  fortunaApp = new FortunaDesktopApp();
  fortunaApp.initialize();
});

app.on('before-quit', () => {
  app.isQuitting = true;
});
