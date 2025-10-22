// electron/main.js
const { app, BrowserWindow, Tray, Menu, nativeImage, dialog } = require('electron');
const { spawn, exec } = require('child_process');
const path = require('path');
const fs = require('fs');

// --- Main Application Class ---
class FortunaDesktopApp {
  constructor() {
    this.mainWindow = null;
    this.tray = null;
    this.backendProcess = null;

    const gotTheLock = app.requestSingleInstanceLock();
    if (!gotTheLock) {
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
      show: false
    });

    this.mainWindow.on('close', (event) => {
      if (!app.isQuitting) {
        event.preventDefault();
        this.mainWindow.hide();
      }
      return false;
    });

    const isDev = process.env.NODE_ENV !== 'production';
    if (isDev) {
      this.mainWindow.loadURL('http://localhost:3000');
    } else {
      this.mainWindow.loadFile(path.join(__dirname, '..', 'web_platform', 'frontend', 'out', 'index.html'));
    }

    this.mainWindow.once('ready-to-show', () => {
        this.mainWindow.show();
    });
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

  async startBackend() {
    return new Promise((resolve, reject) => {
        const isDev = process.env.NODE_ENV !== 'production';
        const rootPath = isDev ? path.join(__dirname, '..') : process.resourcesPath;
        const pythonPath = path.join(rootPath, '.venv', 'Scripts', 'python.exe');
        const apiPath = path.join(rootPath, 'python_service', 'api.py');

        // DEBUG: Verify paths exist
        if (!fs.existsSync(pythonPath)) {
            return reject(new Error(`Python not found: ${pythonPath}`));
        }
        if (!fs.existsSync(apiPath)) {
            return reject(new Error(`API module not found: ${apiPath}`));
        }

        this.backendProcess = spawn(pythonPath, ['-m', 'uvicorn', 'api:app', '--host', '127.0.0.1', '--port', '8000'], {
            cwd: path.join(rootPath, 'python_service'),
            stdio: ['ignore', 'pipe', 'pipe']  // Prevent inherit conflicts
        });

        const timeout = setTimeout(() => {
            reject(new Error('Backend startup timeout'));
        }, 15000);  // 15 second timeout

        this.backendProcess.stdout.on('data', (data) => {
            console.log(`Backend: ${data}`);
            if (data.toString().includes('Uvicorn running')) {
                clearTimeout(timeout);
                resolve();
            }
        });

        this.backendProcess.stderr.on('data', (data) => {
            console.error(`Backend error: ${data}`);
        });

        this.backendProcess.on('error', (err) => {
            clearTimeout(timeout);
            reject(err);
        });
    });
  }

  async initialize() {
    try {
        await this.startBackend();
        this.createMainWindow();
        this.createSystemTray();
    } catch(err) {
        dialog.showErrorBox('Fatal Error', `Failed to start the backend service: ${err.message}`);
        console.error("Initialization failed:", err);
        app.quit();
    }
  }

  cleanup() {
    console.log('Cleaning up processes...');
    if (this.backendProcess) {
        this.backendProcess.kill();
    }
  }
}

let fortunaApp;

app.whenReady().then(() => {
  fortunaApp = new FortunaDesktopApp();
  fortunaApp.initialize();
});

app.on('window-all-closed', (event) => {
  event.preventDefault();
});

app.on('before-quit', () => {
  if(fortunaApp) {
    fortunaApp.cleanup();
  }
});
