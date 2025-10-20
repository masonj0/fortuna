// electron/main.js
const { app, BrowserWindow, Tray, Menu, nativeImage, dialog } = require('electron');
const { spawn, exec } = require('child_process');
const path = require('path');
const fs = require('fs');

// --- Python Backend Manager ---
class PythonManager {
    constructor() {
        this.venvPath = path.join(app.getPath('userData'), 'backend_env');
        this.pythonPath = path.join(this.venvPath, 'Scripts', 'python.exe');
        this.backendProcess = null;
    }

    async setupEnvironment() {
        return new Promise((resolve, reject) => {
            if (fs.existsSync(this.pythonPath)) {
                console.log('Python environment already exists.');
                return resolve();
            }

            console.log('Creating Python virtual environment...');
            exec(`python -m venv "${this.venvPath}"`, (error, stdout, stderr) => {
                if (error) {
                    console.error(`Failed to create venv: ${stderr}`);
                    dialog.showErrorBox('Fatal Error', 'Failed to create the Python virtual environment. Please ensure Python 3.9+ is installed and in your PATH.');
                    return reject(error);
                }
                console.log('Virtual environment created. Installing backend...');
                this.installBackend().then(resolve).catch(reject);
            });
        });
    }

    async installBackend() {
        return new Promise((resolve, reject) => {
            const pipPath = path.join(this.venvPath, 'Scripts', 'pip.exe');
            const wheelPath = path.resolve(__dirname, '..', 'dist', 'fortuna_engine-1.0.0-py3-none-any.whl'); // Assuming a wheel is built
            const reqsPath = path.resolve(__dirname, '..', 'requirements.txt');

            exec(`"${pipPath}" install -r "${reqsPath}"`, (error, stdout, stderr) => {
                if (error) {
                    console.error(`Failed to install dependencies: ${stderr}`);
                    dialog.showErrorBox('Backend Error', 'Failed to install Python dependencies.');
                    return reject(error);
                }
                console.log('Backend installed successfully.');
                resolve();
            });
        });
    }

    start() {
        console.log(`Spawning backend from: ${this.pythonPath}`);
        this.backendProcess = spawn(this.pythonPath, ['-m', 'python_service.run_api'], {
            cwd: path.resolve(__dirname, '..')
        });

        this.backendProcess.stdout.on('data', (data) => console.log(`Backend: ${data}`));
        this.backendProcess.stderr.on('data', (data) => console.error(`Backend ERR: ${data}`));
    }

    stop() {
        if (this.backendProcess) {
            this.backendProcess.kill();
        }
    }
}


// --- Main Application Class ---
class FortunaDesktopApp {
  constructor() {
    this.mainWindow = null;
    this.tray = null;
    this.pythonManager = new PythonManager();

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

  async initialize() {
    try {
        await this.pythonManager.setupEnvironment();
        this.pythonManager.start();
        this.createMainWindow();
        this.createSystemTray();
    } catch(err) {
        console.error("Initialization failed:", err);
        app.quit();
    }
  }

  cleanup() {
    console.log('Cleaning up processes...');
    this.pythonManager.stop();
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
