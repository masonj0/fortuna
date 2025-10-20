# 🐴 Fortuna Faucet - Racing Analysis Engine (Developer Guide)

This document serves as the central guide for developers contributing to the Fortuna Faucet project. For user-facing installation instructions, see `README_WINDOWS.md`.

## Core Architecture

- **Backend (`python_service/`):** An asynchronous FastAPI application.
- **Frontend (`web_platform/frontend/`):** A Next.js and TypeScript dashboard.
- **Unified Launcher (`launcher_gui.py`):** The primary entry point for local development, managing all services and providing real-time health monitoring.

## Local Development Setup

1.  **Prerequisites:** Python 3.11+, Node.js (LTS), Git.
2.  **Clone:** `git clone https://github.com/masonj0/fortuna.git`
3.  **Backend:** Create a venv and `pip install -r requirements.txt`.
4.  **Frontend:** `cd web_platform/frontend` and run `npm install`.

### Running for Development

The entire system can be run for local development using the central GUI launcher. With your Python virtual environment activated, run:

```bash
python launcher_gui.py
```

## Creating a Release Build (MSI Installer)

The project has a professional, automated build pipeline for creating a distributable MSI installer using the WiX Toolset.

- **Configuration:** All WiX source files are located in the `wix/` directory.
- **Build Orchestration:** The entire build process is managed by the PowerShell script located at `scripts/build_msi.ps1`.

To create a release build locally, ensure the WiX Toolset v4 is installed and run the orchestrator:

```powershell
# Navigate to the project root
./scripts/build_msi.ps1
```

The final `.msi` package will be generated in the `dist/` directory.

### Automated CI/CD

This build process is fully automated via GitHub Actions, as defined in `.github/workflows/build_msi.yml`. Every push to `main` or `develop` will automatically build, test, and archive the MSI installer as a workflow artifact.