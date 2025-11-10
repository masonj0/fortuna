# 🐎 Fortuna Faucet - User Guide

**Version:** 2.0
**Last Updated:** November 10, 2025

Thank you for choosing Fortuna Faucet, your personal racing analysis platform. This guide will help you get the application installed and running on your Windows PC.

## System Requirements

- **Operating System:** Windows 10 (64-bit) or Windows 11
- **Disk Space:** Approximately 300 MB for installation
- **Internet Connection:** Required for fetching live race data

No external software (like Python or Node.js) is required. All necessary components are bundled within the installer.

## Installation

Installing Fortuna Faucet is a simple, one-click process thanks to the MSI installer.

1.  **Download the Installer:**
    *   Go to the [**Latest Release Page**](https://github.com/masonj0/fortuna/releases/latest) on GitHub.
    *   Under the "Assets" section, download the file named `fortuna-installer-windows.msi`.

2.  **Run the Installer:**
    *   Locate the downloaded `.msi` file in your Downloads folder.
    *   Double-click the file to launch the installation wizard.
    *   You may see a Windows Defender SmartScreen prompt. Click "More info" and then "Run anyway".
    *   Follow the on-screen instructions. You can choose the installation directory or use the default `C:\Program Files\Fortuna Faucet\`.

3.  **Launch the Application:**
    *   Once the installation is complete, a shortcut for "Fortuna Faucet" will be created on your Desktop and in your Start Menu.
    *   Double-click the shortcut to launch the application.

The application will start, and the backend service will initialize in the background. Within a few moments, the dashboard should indicate an "Online" status and begin populating with race data.

## First-Time Configuration

On the first run, you may need to configure API keys for certain data sources (like Betfair) for the application to function fully. These settings can be accessed within the application's configuration panel.

## Troubleshooting

#### Application Shows "Error" or "Offline" Status

This can happen if the backend service fails to start correctly.

*   **Restart the Application:** The simplest solution is often to close and reopen the application.
*   **Check for Conflicting Processes:** Ensure no other applications are using the required network port (typically `8000`).
*   **Check Logs:** The application logs can provide more detail. These are typically located in `%APPDATA%\Fortuna Faucet\logs\`.

#### "Windows protected your PC" Message During Installation

This is expected behavior for new, unsigned applications.

*   Click the "**More info**" link.
*   Click the "**Run anyway**" button that appears.

## Uninstalling

To uninstall Fortuna Faucet:

1.  Open the **Windows Start Menu**.
2.  Go to **Settings > Apps > Apps & features**.
3.  Find "Fortuna Faucet" in the list.
4.  Click it and select **Uninstall**.
5.  Follow the prompts to remove the application.
