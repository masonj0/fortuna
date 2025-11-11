const { execSync } = require('child_process');
const path = require('path');
const fs = require('fs');

// Path to the bundled Python executable (fortuna-backend.exe)
const PYTHON_EXE = path.join(process.resourcesPath, 'fortuna-backend.exe');
// Path to the Python service directory (where alembic.ini is)
const PYTHON_SERVICE_DIR = path.join(process.resourcesPath, 'python_service');

function runCommand(command, cwd) {
    console.log(`Executing: ${command} in ${cwd}`);
    try {
        const output = execSync(command, { cwd: cwd, encoding: 'utf-8' });
        console.log(output);
    } catch (error) {
        console.error(`Command failed: ${command}`);
        console.error(error.stderr || error.stdout || error.message);
        throw new Error(`Post-install setup failed: ${command}`);
    }
}

function setupDatabase() {
    console.log('--- Starting Database Setup (Alembic Migrations) ---');
    // NOTE: The bundled EXE must be able to run a command like 'alembic' or a custom script
    // that executes the migrations. Assuming the bundled EXE can run a module.
    // A more robust solution is to bundle a dedicated migration script.

    // Assuming the bundled EXE can execute a module that runs Alembic
    const migrationCommand = `${PYTHON_EXE} -m python_service.database.run_migrations`;

    // The migration script needs access to the database URL from the config.
    // This is a placeholder, as the config loading is complex in a frozen app.
    // For now, we assume the bundled EXE handles config loading.

    runCommand(migrationCommand, PYTHON_SERVICE_DIR);
    console.log('--- Database Setup Complete ---');
}

// This function is called by the Electron Builder installer hook
module.exports = async function() {
    try {
        setupDatabase();
    } catch (e) {
        console.error('FATAL: Post-install setup failed.', e);
        // In a real installer, you might log this and continue, or show a user error.
    }
};
