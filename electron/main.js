// electron/main.js
const { app, BrowserWindow, dialog } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const fs = require('fs');

class FortunaApp {
  constructor() {
    this.mainWindow = null;
    this.backendProcess = null;
    this.isDev = process.env.NODE_ENV === 'development';

    // Bind app events
    app.on('ready', this.onReady.bind(this));
    app.on('window-all-closed', this.onWindowAllClosed.bind(this));
    app.on('activate', this.onActivate.bind(this));
    app.on('before-quit', this.onBeforeQuit.bind(this));
    process.on('uncaughtException', this.onUncaughtException.bind(this));

    console.log('[MAIN] FortunaApp initialized.');
  }

  async startBackend() {
    return new Promise((resolve, reject) => {
      console.log(`[MAIN] Starting backend in ${this.isDev ? 'development' : 'production'} mode.`);

      if (this.isDev) {
        // --- DEVELOPMENT ---
        // In development, we launch the backend using the Python virtual environment.
        const pythonPath = path.join(__dirname, '..', '.venv', 'Scripts', 'python.exe');
        const servicePath = path.join(__dirname, '..', 'python_service');

        if (!fs.existsSync(pythonPath)) {
          const errMsg = `Python executable not found at: ${pythonPath}`;
          console.error(`[MAIN] FATAL: ${errMsg}`);
          return reject(new Error(errMsg));
        }

        console.log(`[MAIN] Spawning backend: ${pythonPath} -m uvicorn api:app`);
        this.backendProcess = spawn(
          pythonPath,
          ['-m', 'uvicorn', 'api:app', '--host', '127.0.0.1', '--port', '8000'],
          { cwd: servicePath }
        );

      } else {
        // --- PRODUCTION ---
        // In production, we launch the pre-packaged backend executable.
        // It's placed in the 'resources' directory by electron-builder's 'extraResources'.
        const exePath = path.join(process.resourcesPath, 'fortuna-backend.exe');

        if (!fs.existsSync(exePath)) {
          const errMsg = `Backend executable not found at: ${exePath}`;
          console.error(`[MAIN] FATAL: ${errMsg}`);
          return reject(new Error(errMsg));
        }

        console.log(`[MAIN] Spawning backend from: ${exePath}`);
        this.backendProcess = spawn(exePath, [], {
          env: {
            ...process.env,
            // Pass environment variables if the executable needs them.
            // e.g., FORTUNA_PORT: '8000'
          },
        });
      }

      // --- COMMON PROCESS HANDLING ---
      this.backendProcess.stdout.on('data', (data) => {
        const message = data.toString().trim();
        console.log(`[BACKEND] ${message}`);
        // Resolve the promise once the backend confirms it's running.
        if (message.includes('Uvicorn running on') || message.includes('Application startup complete')) {
          console.log('[MAIN] Backend startup confirmed.');
          resolve();
        }
      });

      this.backendProcess.stderr.on('data', (data) => {
        const message = data.toString().trim();
        console.error(`[BACKEND ERROR] ${message}`);
      });

      this.backendProcess.on('error', (err) => {
        console.error('[MAIN] Failed to start backend process:', err);
        reject(err);
      });

       this.backendProcess.on('exit', (code) => {
        console.error(`[MAIN] Backend process exited unexpectedly with code ${code}.`);
        // Optionally, you could reject here if it exits before resolving.
      });
    });
  }

  createMainWindow() {
    console.log('[MAIN] Creating main window.');
    this.mainWindow = new BrowserWindow({
      width: 1600,
      height: 1000,
      title: 'Fortuna Faucet',
      icon: path.join(__dirname, 'assets', 'icon.ico'),
      webPreferences: {
        nodeIntegration: false,
        contextIsolation: true,
        preload: path.join(__dirname, 'preload.js'),
        sandbox: false // Sandbox can interfere with preload scripts accessing node modules.
      }
    });

    if (this.isDev) {
      // --- DEVELOPMENT ---
      // Load from the Next.js development server.
      console.log('[MAIN] Loading URL: http://localhost:3000');
      this.mainWindow.loadURL('http://localhost:3000');
      this.mainWindow.webContents.openDevTools();

    } else {
      // --- PRODUCTION ---
      // Load the static HTML file that was packaged by electron-builder.
      const indexPath = path.join(__dirname, 'web-ui-build', 'out', 'index.html');

      if (!fs.existsSync(indexPath)) {
        const errMsg = `Frontend entry point not found at: ${indexPath}`;
        console.error(`[MAIN] FATAL: ${errMsg}`);
        dialog.showErrorBox('Fatal Error', errMsg);
        app.quit();
        return;
      }

      console.log(`[MAIN] Loading file: ${indexPath}`);
      this.mainWindow.loadFile(indexPath);
    }

    this.mainWindow.on('closed', () => {
      this.mainWindow = null;
    });
  }

  async onReady() {
    console.log('[MAIN] App is ready.');
    try {
      await this.startBackend();
      this.createMainWindow();
    } catch (error) {
      console.error('[MAIN] Startup failed:', error);
      dialog.showErrorBox('Application Startup Error', `Failed to start the backend components.\n\n${error.message}\n\nPlease check logs for more details.`);
      app.quit();
    }
  }

  onWindowAllClosed() {
    // On macOS, it's common for applications to stay active until the user quits explicitly.
    if (process.platform !== 'darwin') {
      app.quit();
    }
  }

  onActivate() {
    // On macOS, re-create the window when the dock icon is clicked and there are no other windows open.
    if (this.mainWindow === null) {
      this.createMainWindow();
    }
  }

  onBeforeQuit() {
    console.log('[MAIN] Quitting application. Terminating backend process.');
    if (this.backendProcess) {
      this.backendProcess.kill('SIGTERM'); // Send a termination signal.
      this.backendProcess = null;
    }
  }

  onUncaughtException(error) {
    console.error('[MAIN] Uncaught Exception:', error);
    // Optionally, show an error dialog to the user.
    dialog.showErrorBox('An Unexpected Error Occurred', `The application has encountered a critical error and will close.\n\n${error.message}`);
    this.onBeforeQuit(); // Ensure cleanup happens.
    app.exit(1);
  }
}

// Instantiate and start the application.
new FortunaApp();
