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
        pythonPath = path.join(process.cwd(), '.venv', 'Scripts', 'python.exe');
        serviceCwd = path.join(process.cwd(), 'python_service');
    } else {
        pythonPath = path.join(process.resourcesPath, 'app', 'python', 'python.exe');
        serviceCwd = path.join(process.resourcesPath, 'app', 'python_service');
    }

    if (!fs.existsSync(pythonPath)) {
        throw new Error(`Python executable not found at: ${pythonPath}`);
    }

    // --- ENHANCED LOGGING ---
    const logDir = app.getPath('userData');
    const logFile = path.join(logDir, 'backend_diagnostics.log');
    // Ensure log directory exists and create a writable stream
    if (!fs.existsSync(logDir)) {
      fs.mkdirSync(logDir, { recursive: true });
    }
    const logStream = fs.createWriteStream(logFile, { flags: 'a' });
    logStream.write(`--- Log session started at ${new Date().toISOString()} ---\n`);
    logStream.write(`Python Path: ${pythonPath}\n`);
    logStream.write(`Service CWD: ${serviceCwd}\n`);

    this.backendProcess = spawn(pythonPath,
        ['-m', 'uvicorn', 'api:app', '--host', '127.0.0.1', '--port', '8000'],
        {
            cwd: serviceCwd,
            // Detach the process from the parent, and pipe output to files
            detached: true,
            stdio: ['ignore', 'pipe', 'pipe']
        }
    );

    // Redirect stdout and stderr to the log file
    this.backendProcess.stdout.pipe(logStream);
    this.backendProcess.stderr.pipe(logStream);

    return new Promise((resolve, reject) => {
        const timeout = setTimeout(() => {
            this.backendProcess.kill();
            logStream.write('--- Backend startup timed out ---\n');
            reject(new Error('Backend startup timed out after 15 seconds. Check backend_diagnostics.log for details.'));
        }, 15000);

        const onData = (data) => {
            const output = data.toString();
            if (output.includes('Uvicorn running')) {
                logStream.write('--- Backend started successfully ---\n');
                cleanupListeners();
                resolve();
            }
        };

        const onError = (data) => {
            const errorOutput = data.toString();
            logStream.write(`--- Backend failed to start: ${errorOutput} ---\n`);
            cleanupListeners();
            reject(new Error(`Backend failed to start. Check backend_diagnostics.log.`));
        };

        const cleanupListeners = () => {
            clearTimeout(timeout);
            this.backendProcess.stdout.removeListener('data', onData);
            this.backendProcess.stderr.removeListener('data', onError);
        };

        this.backendProcess.stdout.on('data', onData);
        this.backendProcess.stderr.on('data', onError);
    });
  }

  async initialize() {
    try {
      await this.startBackend();
      this.createMainWindow();
      this.createSystemTray();
    } catch(err) {
      const logPath = path.join(app.getPath('userData'), 'backend_diagnostics.log');
      const errorMessage = `Failed to initialize Fortuna Faucet: ${err.message}\n\nPlease check the log file for more details:\n${logPath}`;
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
  event.preventDefault();
});

app.on('before-quit', () => {
  if (fortunaApp) {
    fortunaApp.cleanup();
  }
});
