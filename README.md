# 🐴 Fortuna Faucet - Racing Analysis Engine

Welcome to Fortuna Faucet! This guide provides instructions for both end-users and developers.

## Getting Started: The Official Installation

The easiest way to get started is with our official MSI installer, which handles all setup and configuration automatically.

1.  **Download the Installer:**
    *   Go to the [latest release page](https://github.com/masonj0/fortuna/releases/latest) on GitHub.
    *   Download the `Fortuna-Faucet-Setup-vX.X.X.msi` file.

2.  **Run the Installer:**
    *   Double-click the downloaded `.msi` file.
    *   Follow the on-screen instructions in the setup wizard.

Once installed, a "Fortuna Faucet" folder will be created in your Start Menu. The application's backend will run automatically as a background service, and you can access the dashboard via the Start Menu shortcut.

---

## For Developers

This section contains instructions for developers who wish to contribute to the project or manage the environment manually.

### Core Architecture

The project has a distinct architecture for production and development environments.

*   **Production Architecture (in the MSI):**
    *   **Standalone Backend:** The Python backend is compiled into a single, self-contained executable (`fortuna-api`) using **PyInstaller**. This bundles the Python interpreter and all dependencies, requiring no Python installation on the user's machine.
    *   **Static Frontend:** The Next.js frontend is exported as a set of static HTML, CSS, and JavaScript assets. These are served directly from the filesystem by the Electron application.
    *   **Electron Wrapper:** The Electron app acts as a shell, launching the backend executable as a background process and loading the static frontend.

*   **Development Architecture:**
    *   **Backend (`python_service/`):** An asynchronous FastAPI application run from a local Python virtual environment.
    *   **Frontend (`web_platform/frontend/`):** A standard Next.js development server that enables hot-reloading for rapid UI development.
    *   **Unified Launcher (`run_dev_environment.bat`):** The primary entry point for local development, managing both backend and frontend services.

### Manual Development Setup

1.  **Prerequisites:** Python 3.11+, Node.js (LTS), Git.
2.  **Clone:** `git clone https://github.com/masonj0/fortuna.git`
3.  **Run the Setup Script:** For a one-time setup of both the Python virtual environment and Node.js dependencies, simply run the `run_dev_environment.bat` script.

### Creating a Release Build (MSI Installer)

The project uses the WiX Toolset to create a professional, distributable MSI installer based on the production architecture.

*   **Build Orchestrator:** The entire build process is automated and managed by the `scripts/build_msi.ps1` PowerShell script.
*   **Key Build Steps:**
    1.  The script first compiles the entire Python backend into a standalone executable using **PyInstaller**.
    2.  Next, it builds the Next.js frontend into a static export.
    3.  Finally, it uses the **WiX Toolset** (`heat.exe`, `candle.exe`, `light.exe`) to harvest these pre-built artifacts and package them into a clean, reliable MSI installer.
*   **CI/CD:** The build is fully automated via GitHub Actions, as defined in `.github/workflows/build_msi.yml`. To create a release build locally, ensure the WiX Toolset is installed and run the `scripts/build_msi.ps1` script from a PowerShell terminal.
