// electron/install-dependencies.js
const { execSync } = require('child_process');
const path = require('path');
const fs = require('fs');

const ROOT_DIR = path.resolve(__dirname, '..');
const PYTHON_SERVICE_DIR = path.join(ROOT_DIR, 'python_service');
const FRONTEND_DIR = path.join(ROOT_DIR, 'web_platform', 'frontend');

function log(message) {
    const timestamp = new Date().toISOString();
    const logMsg = `[${timestamp}] ${message}`;
    console.log(logMsg);

    // IMPORTANT: Also write to a file for debugging
    try {
        const logFile = path.join(process.env.TEMP || '/tmp', 'fortuna-install.log');
        fs.appendFileSync(logFile, logMsg + '\n');
    } catch (e) {
        console.error('Could not write to log file:', e.message);
    }
}

function runCommand(command, cwd) {
    log(`Executing: ${command}`);
    log(`Working directory: ${cwd}`);

    try {
        const result = execSync(command, {
            cwd,
            stdio: ['pipe', 'pipe', 'pipe'],
            encoding: 'utf-8',
            maxBuffer: 10 * 1024 * 1024
        });
        log(`SUCCESS: ${command}`);
        log(`Output: ${result.substring(0, 500)}`); // Log first 500 chars
        return true;
    } catch (error) {
        log(`ERROR: ${command} failed with code ${error.status}`);
        log(`Error output: ${error.stderr || error.message}`);
        return false;
    }
}

try {
    log('--- Starting Fortuna Faucet Installation ---');

    // Verify critical directories exist
    if (!fs.existsSync(PYTHON_SERVICE_DIR)) {
        throw new Error(`Python service directory not found: ${PYTHON_SERVICE_DIR}`);
    }
    if (!fs.existsSync(FRONTEND_DIR)) {
        throw new Error(`Frontend directory not found: ${FRONTEND_DIR}`);
    }

    // Step 1: Python dependencies
    log('Step 1: Installing Python dependencies...');
    const venvPython = path.join(ROOT_DIR, '.venv', 'Scripts', 'python.exe');

    if (fs.existsSync(venvPython)) {
        const cmd = `"${venvPython}" -m pip install -r requirements.txt`;
        const success = runCommand(cmd, PYTHON_SERVICE_DIR);
        if (!success) {
            log('WARNING: Python dependencies installation failed, but continuing...');
        }
    } else {
        log(`WARNING: Python not found at ${venvPython}`);
    }

    // Step 2: Frontend dependencies
    log('Step 2: Installing Frontend dependencies...');
    if (fs.existsSync(path.join(FRONTEND_DIR, 'package.json'))) {
        const success = runCommand('npm install', FRONTEND_DIR);
        if (!success) {
            log('WARNING: npm install failed, but continuing...');
        }
    } else {
        log(`WARNING: package.json not found in ${FRONTEND_DIR}`);
    }

    log('--- Installation Complete ---');
    process.exit(0);
} catch (error) {
    log(`FATAL ERROR: ${error.message}`);
    log(`Stack: ${error.stack}`);
    // Always exit with code 0 to prevent MSI rollback, as requested by the user.
    // The error is logged to fortuna-install.log for debugging.
    process.exit(0);
}
