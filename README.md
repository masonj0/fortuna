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

*   **Backend (`python_service/`):** An asynchronous FastAPI application.
*   **Frontend (`web_platform/frontend/`):** A Next.js and TypeScript dashboard.
*   **Unified Launcher (`fortuna_app.py`):** The primary entry point for local development, managing all services and providing real-time health monitoring.

### Manual Development Setup

1.  **Prerequisites:** Python 3.11+, Node.js (LTS), Git.
2.  **Clone:** `git clone https://github.com/masonj0/fortuna.git`
3.  **Backend:** Create a venv (`python -m venv .venv`) and `pip install -r requirements.txt`.
4.  **Frontend:** `cd web_platform/frontend` and run `npm install`.

### Creating a Release Build (MSI Installer)

The project uses the WiX Toolset to create a distributable MSI installer.

*   **Configuration:** All WiX source files are in the `wix/` directory.
*   **Build Script:** The build process is managed by `scripts/build_msi.ps1`.
*   **CI/CD:** The build is automated via GitHub Actions, defined in `.github/workflows/build_msi.yml`. To create a release build locally, ensure the WiX Toolset is installed and run the PowerShell script.
