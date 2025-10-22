// electron/main.js
const { app, BrowserWindow, Tray, Menu, nativeImage, dialog } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

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
      show: false
    });

    this.mainWindow.on('close', (event) => {
      if (!app.isQuitting) {
        event.preventDefault();
        this.mainWindow.hide();
      }
    });

    const isDev = process.env.NODE_ENV === 'development';
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
    const isDev = process.env.NODE_ENV === 'development';

    let pythonPath;
    let serviceCwd;

    if (isDev) {
        // In development, use the project's virtual environment
        pythonPath = path.join(process.cwd(), '.venv', 'Scripts', 'python.exe');
        serviceCwd = path.join(process.cwd(), 'python_service');
    } else {
        // In production, use the embedded Python in the installed app resources
        pythonPath = path.join(process.resourcesPath, 'python', 'python.exe');
        serviceCwd = path.join(process.resourcesPath, 'app', 'python_service');
    }

    // Verify the executable path exists before attempting to spawn
    if (!fs.existsSync(pythonPath)) {
        throw new Error(`Python executable not found at: ${pythonPath}`);
    }

    this.backendProcess = spawn(pythonPath,
        ['-m', 'uvicorn', 'api:app', '--host', '127.0.0.1', '--port', '8000'],
        {
            cwd: serviceCwd,
            stdio: 'pipe' // Use 'pipe' to capture output
        }
    );

    return new Promise((resolve, reject) => {
        const timeout = setTimeout(() => {
            this.backendProcess.kill();
            reject(new Error('Backend startup timed out after 15 seconds.'));
        }, 15000);

        this.backendProcess.stdout.on('data', (data) => {
            const output = data.toString();
            console.log(`[Backend STDOUT]: ${output}`);
            if (output.includes('Uvicorn running')) {
                console.log('Backend started successfully.');
                clearTimeout(timeout);
                resolve();
            }
        });

        this.backendProcess.stderr.on('data', (data) => {
            const errorOutput = data.toString();
            console.error(`[Backend STDERR]: ${errorOutput}`);
            // Reject on first error to fail fast
            clearTimeout(timeout);
            reject(new Error(`Backend failed to start: ${errorOutput}`));
        });

        this.backendProcess.on('close', (code) => {
            if (code !== 0) {
                console.error(`Backend process exited with code ${code}`);
                clearTimeout(timeout);
                reject(new Error(`Backend process exited with code ${code}`));
            }
        });

        this.backendProcess.on('error', (err) => {
            console.error('Failed to start backend process:', err);
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
      const errorMessage = `Failed to initialize Fortuna Faucet: ${err.message}\n\nPlease check the logs for more details.`;
      dialog.showErrorBox('Fatal Initialization Error', errorMessage);
      console.error(errorMessage, err);
      app.quit();
    }
  }

  cleanup() {
    console.log('Cleaning up backend process...');
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
  // Prevent app from quitting when all windows are closed.
  // The app will continue to run in the system tray.
  event.preventDefault();
});

app.on('before-quit', () => {
  if (fortunaApp) {
    fortunaApp.cleanup();
  }
});
