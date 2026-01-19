# Fortuna Faucet - Race Reporting System

This subsystem allows you to generate automated race reports using GitHub Actions, without needing to maintain a permanent server.

## 🚀 Quick Start (5 Minutes)

1.  **File Setup**: Ensure `.github/workflows/generate-race-report.yml` and `scripts/test_api_query.py` are in your repository.
2.  **Add Secret**: Go to **Settings -> Secrets and variables -> Actions** and add `API_KEY`.
3.  **Run**: Go to the **Actions** tab, select **Fortuna - Instant Filtered Race Report**, and click **Run workflow**.

## 🔄 Workflow Lifecycle

1.  **Setup**: Installs Python 3.10 and dependencies.
2.  **Backend Launch**: Spins up the FastAPI backend on `localhost:8000`.
3.  **Health Check**: Polls until the backend is ready.
4.  **Query**: Fetches qualified races from `/api/races/qualified/trifecta`.
5.  **Generate**: Creates a polished HTML report (`race-report.html`).
6.  **Cleanup**: Uploads artifacts and shuts down the backend.

## 📥 Downloading Reports

1.  Go to the **Actions** tab in GitHub.
2.  Click on a completed run.
3.  Scroll down to **Artifacts**.
4.  Download `fortuna-race-report-[RUN_NUMBER]`.
5.  Extract the zip file to view the HTML report.

## 🧪 Local Testing

You can verify the logic locally before pushing to GitHub:

```bash
# Terminal 1: Start Backend
python -m uvicorn web_service.backend.main:app --port 8000

# Terminal 2: Run Query Script
python scripts/test_api_query.py
```
