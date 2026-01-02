@echo off
REM This script provides a user-friendly, double-clickable way to start the
REM development environment by running the fortuna-quick-start.ps1 script.
REM It bypasses the system's PowerShell execution policy for this script only.

echo Starting Fortuna Faucet Development Environment...
echo This will open two new terminal windows for the backend and frontend.

powershell.exe -ExecutionPolicy Bypass -File "%~dp0scripts\fortuna-quick-start.ps1"

echo.
echo Script execution finished. The development servers are running in new windows.
pause
