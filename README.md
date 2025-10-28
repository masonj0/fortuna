# 🐴 Fortuna Faucet - Developer's Guide

This guide provides technical instructions for developers contributing to the Fortuna Faucet project. For end-user installation, please see `README_WINDOWS.md`.

## Core Architecture

The project has a distinct architecture for production and development environments. Understanding this separation is key to effective development.

*   **Production Architecture (MSI Installer):**
    *   **Standalone Backend:** The Python backend is compiled into a single, self-contained executable (`fortuna-api.exe`) using **PyInstaller**. This bundles the Python interpreter and all dependencies, requiring no Python installation on the user's machine.
    *   **Static Frontend:** The Next.js frontend is exported as a set of static HTML, CSS, and JavaScript assets.
    *   **Electron Wrapper:** The Electron app acts as a lightweight shell, launching the backend executable as a background process and loading the static frontend directly from the filesystem.

*   **Development Architecture:**
    *   **Backend (`python_service/`):** An asynchronous FastAPI application run from a local Python virtual environment.
    *   **Frontend (`web_platform/frontend/`):** A standard Next.js development server that enables hot-reloading for rapid UI development.

## Development Environment

### 1. Prerequisites

*   Python 3.12+
*   Node.js (LTS)
*   Git

### 2. Initial One-Time Setup

For your first time setting up the project, run the main setup script. This will create the Python virtual environment and install all necessary dependencies for both the backend and frontend.

```bash
git clone https://github.com/masonj0/fortuna.git
cd fortuna
run_dev_environment.bat
```

### 3. Daily Execution

Once the initial setup is complete, use the `fortuna-quick-start.ps1` script for your daily development workflow. This powerful script handles all pre-flight checks and launches both servers concurrently.

```powershell
# From a PowerShell terminal in the project root
.\\scripts\\fortuna-quick-start.ps1
```

*   **Options:** The script includes parameters for skipping dependency checks (`-SkipChecks`) and running only the backend (`-NoFrontend`) for maximum flexibility.

---

## Key Scripts & Tooling

*   **`run_dev_environment.bat`**: The master script for the **initial one-time setup** of the development environment.
*   **`scripts/fortuna-quick-start.ps1`**: The recommended script for **daily execution**, providing robust process management for both backend and frontend servers.
*   **`scripts/build_msi.ps1`**: The local build orchestrator. This script runs the entire production build pipeline: it compiles the backend with PyInstaller, builds the static frontend, and packages everything into an MSI installer using the WiX Toolset.
*   **`ARCHIVE_PROJECT.py`**: The "True Scribe." This script programmatically scans the repository and generates the `FORTUNA_ALL_PART*.JSON` archive files, which are the authoritative source for project-wide code reviews.
*   **`.github/workflows/build-msi.yml`**: The CI/CD pipeline definition for GitHub Actions, which automates the creation of the release MSI installer.
