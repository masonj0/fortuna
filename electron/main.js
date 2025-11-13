// electron/main.js - AUTHORITATIVE VERSION FROM ARCHIVE
const { app, BrowserWindow, Tray, Menu, nativeImage, ipcMain, dialog } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const sudo = require('sudo-prompt');
const SecureSettingsManager = require('./secure-settings-manager');
const { isServiceRunning, installService, startService } = require('./install-validator');

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
      try {
        const isRunning = await isServiceRunning(SERVICE_NAME);
        if (isRunning) {
          console.log(`[OK] Service '${SERVICE_NAME}' is already running.`);
          return;
        }

        console.log(`Service '${SERVICE_NAME}' is not running. Attempting to install and start.`);
        const backendExePath = path.join(process.resourcesPath, 'fortuna-backend.exe');

        // This is the point of failure. We must use sudo-prompt here.
        const installCommand = `\\\"${backendExePath}\\\" service install --name \\\"${SERVICE_NAME}\\\" --display-name \\\"${SERVICE_DISPLAY_NAME}\\\" --description \\\"${SERVICE_DESCRIPTION}\\\"`;
        const startCommand = `\\\"${backendExePath}\\\" service start --name \\\"${SERVICE_NAME}\\\"`;

        const options = { name: 'Fortuna Faucet' };

        sudo.exec(installCommand, options, (error, stdout, stderr) => {
          if (error) {
            dialog.showErrorBox('Service Installation Failed', `Could not install backend service: ${error.message}`);
            return;
          }
          console.log('Service installed successfully. Now starting...');
          sudo.exec(startCommand, options, (startError, startStdout, startStderr) => {
            if (startError) {
              dialog.showErrorBox('Service Start Failed', `Could not start backend service: ${startError.message}`);
              return;
            }
            console.log('Service started successfully.');
          });
        });

      } catch (err) {
        dialog.showErrorBox('Backend Service Error', `An error occurred while managing the backend service: ${err.message}`);
      }
    } else {
      console.log('[DEV MODE] Skipping service installation. The backend should be run manually.');
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
