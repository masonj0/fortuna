# 🐴 Fortuna Faucet - Racing Analysis Engine

Welcome to Fortuna Faucet! This guide will help you get the application running.

## Getting Started (for Users)

If you have downloaded this project as a ZIP file, you can get started right away.

1.  **Run the Application:** Double-click the `fortuna_app.py` file.
2.  **One-Click Setup:** A setup window will appear to automatically install all required dependencies. Click **'Start Installation'** and wait for the process to complete.
3.  **Launch:** Once finished, click **'Launch'** to start the main application dashboard.

That's it! The application is now ready to use.

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
