const fs = require('fs');
const path = require('path');
const { spawn } = require('child_process');

async function validateInstallation() {
    const resourcesPath = process.resourcesPath;
    const pythonPath = path.join(resourcesPath, 'python', 'python.exe');

    console.log('🔍 Validating installation...');

    // Check 1: Python exists
    if (!fs.existsSync(pythonPath)) {
        throw new Error(`Python not found at ${pythonPath}`);
    }
    console.log('✅ Python found');

    // Check 2: Python works
    return new Promise((resolve, reject) => {
        const proc = spawn(pythonPath, ['--version']);
        let output = '';

        proc.stdout.on('data', (data) => {
            output += data.toString();
        });

        proc.on('close', (code) => {
            if (code === 0) {
                console.log(`✅ Python works: ${output.trim()}`);
                resolve();
            } else {
                reject(new Error(`Python test failed: ${output}`));
            }
        });
    });
}

module.exports = { validateInstallation };
