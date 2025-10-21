# python_service/updater.py
import httpx
import semver
import os
import sys
from pathlib import Path

# --- Constants ---
GITHUB_REPO_OWNER = "masonj0"
GITHUB_REPO_NAME = "fortuna"
API_URL = f"https://api.github.com/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}/releases/latest"

def get_current_version():
    """Reads the current version from VERSION.txt."""
    try:
        # Correctly locate VERSION.txt relative to the project root
        base_path = Path(__file__).resolve().parent.parent
        version_file = base_path / "VERSION.txt"
        return version_file.read_text().strip()
    except FileNotFoundError:
        return "0.0.0" # Default version if file is missing

async def check_for_updates():
    """
    Checks for a new release on GitHub and returns info if an update is available.
    """
    current_version_str = get_current_version()
    try:
        current_version = semver.VersionInfo.parse(current_version_str)
    except ValueError:
        return {"status": "error", "message": "Invalid local version format."}

    headers = {"Accept": "application/vnd.github.v3+json"}
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(API_URL, headers=headers)
            response.raise_for_status()
            latest_release = response.json()
        except httpx.HTTPStatusError as e:
            return {"status": "error", "message": f"GitHub API error: {e.response.status_code}"}
        except Exception as e:
            return {"status": "error", "message": f"Failed to connect to GitHub: {e}"}

    latest_version_str = latest_release.get("tag_name", "0.0.0").lstrip('v')
    try:
        latest_version = semver.VersionInfo.parse(latest_version_str)
    except ValueError:
        return {"status": "error", "message": "Invalid remote version format."}

    if latest_version > current_version:
        msi_asset = next((asset for asset in latest_release.get("assets", []) if asset["name"].endswith(".msi")), None)
        if msi_asset:
            return {
                "status": "update_available",
                "current_version": str(current_version),
                "latest_version": str(latest_version),
                "download_url": msi_asset["browser_download_url"],
                "release_notes": latest_release.get("body", "No release notes available.")
            }
        else:
            return {"status": "no_msi_asset", "message": "New version found, but no MSI installer is attached."}
    else:
        return {"status": "up_to_date", "current_version": str(current_version)}

def download_and_install_update(url: str):
    """
    (Placeholder) This function will download the MSI from the URL
    and execute it. This requires careful implementation to handle permissions
    and execution correctly.
    """
    # 1. Download the file to a temporary directory
    # 2. Verify file integrity (e.g., checksum if available)
    # 3. Run the MSI installer (e.g., using os.startfile or subprocess)
    # 4. Handle post-install cleanup.
    pass

if __name__ == '__main__':
    import asyncio
    async def main():
        update_info = await check_for_updates()
        print(update_info)
    asyncio.run(main())
