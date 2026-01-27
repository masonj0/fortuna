# scripts/verify_browsers.py
# CORRECTED VERSION - Outputs to browser_verification.json
# This version aligns with the updated CI workflow.

import asyncio
import json
import logging
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# --- Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s [%(name)s.%(funcName)s:%(lineno)d] %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

# CRITICAL: This filename must match the one expected by the GitHub workflow.
OUTPUT_FILE = Path("browser_verification.json")
EXPECTED_BROWSERS = ["chrome", "firefox"]
INSTALL_GUIDE_URL = "https://playwright.dev/docs/intro"

# --- Helper Functions ---

async def run_command(command: str) -> Tuple[bool, str, str]:
    """Executes a shell command asynchronously."""
    try:
        process = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        return process.returncode == 0, stdout.decode().strip(), stderr.decode().strip()
    except Exception as e:
        logger.error(f"Command '{command}' failed: {e}", exc_info=True)
        return False, "", str(e)

async def find_executable(name: str) -> Optional[str]:
    """Finds the full path of an executable, checking common locations."""
    path = shutil.which(name)
    if path:
        return path

    # Fallback for systems where shutil.which might be limited
    success, stdout, _ = await run_command(f"command -v {name}")
    if success and stdout:
        return stdout

    return None

async def get_browser_version(executable_path: str) -> Optional[str]:
    """Gets the version of a browser executable."""
    if not executable_path:
        return None

    name = Path(executable_path).name.lower()
    flag = "--version" # Standard for most browsers

    success, stdout, stderr = await run_command(f'"{executable_path}" {flag}')

    if success and stdout:
        # Clean up output, e.g., "Google Chrome 125.0.6422.112" -> "125.0.6422.112"
        version_part = stdout.split()[-1]
        return version_part

    logger.warning(f"Failed to get version for {name}: {stderr or 'Unknown error'}")
    return None

async def check_playwright_installation() -> Tuple[bool, Optional[str]]:
    """Checks if Playwright is installed and can be run."""
    logger.info("Verifying Playwright installation...")
    success, stdout, stderr = await run_command("npx playwright --version")
    if success:
        logger.info(f"Playwright found: {stdout}")
        return True, stdout.replace("Version ", "")

    logger.error(f"Playwright not found or failed to execute. Stderr: {stderr}")
    return False, None

async def verify_browser_installations(playwright_installed: bool) -> Dict[str, Dict]:
    """
    Checks for both system-wide and Playwright-managed browser installations.
    """
    if not playwright_installed:
        logger.warning("Playwright not found, skipping browser installation checks.")
        return {}

    logger.info("Running 'npx playwright install --with-deps' to ensure browsers are ready...")
    # This command is idempotent and ensures all dependencies are met.
    # It's a best practice for CI environments.
    success, _, stderr = await run_command("npx playwright install --with-deps")
    if not success:
        logger.error(f"Playwright browser installation failed. Stderr: {stderr}")
        # We can still proceed to check for system browsers, but this is a bad sign.
    else:
        logger.info("Playwright browsers and dependencies are up to date.")

    # Now, check what's available
    results = {}
    browser_executables = {
        "chrome": ["google-chrome-stable", "google-chrome", "chrome", "chromium"],
        "firefox": ["firefox"],
    }

    for browser, executables in browser_executables.items():
        found = False
        for exe in executables:
            path = await find_executable(exe)
            if path:
                version = await get_browser_version(path)
                results[browser] = {
                    "installed": True,
                    "version": version or "Unknown",
                    "path": path,
                }
                logger.info(f"Found {browser} at {path} (v{version or 'N/A'})")
                found = True
                break # Move to the next browser

        if not found:
            results[browser] = {
                "installed": False,
                "version": None,
                "path": None,
            }
            logger.warning(f"{browser.capitalize()} could not be found on the system path.")

    return results

def generate_summary(results: Dict) -> Tuple[bool, str]:
    """Generates a summary report and determines overall success."""
    summary_lines = ["\n--- Browser Verification Report ---"]
    all_found = True

    playwright_ok = results.get("playwright", {}).get("installed", False)
    summary_lines.append(
        f"✅ Playwright | Installed (v{results.get('playwright', {}).get('version', 'N/A')})"
        if playwright_ok else "❌ Playwright | Not Installed"
    )
    if not playwright_ok:
        all_found = False

    for browser, info in results.get("browsers", {}).items():
        if browser in EXPECTED_BROWSERS:
            if info["installed"]:
                summary_lines.append(
                    f"✅ {browser.capitalize():<10} | Found (v{info['version']}) at {info['path']}"
                )
            else:
                all_found = False
                summary_lines.append(f"❌ {browser.capitalize():<10} | Not Found")

    summary_lines.append("-" * 35)
    if all_found:
        summary_lines.append("✅ Success: All required components are installed.")
    else:
        summary_lines.append("🔥 Error: One or more required components are missing.")
        summary_lines.append(f"   Please check the logs or see install guide: {INSTALL_GUIDE_URL}")

    return all_found, "\n".join(summary_lines)

# --- Main Execution ---

async def main():
    """Main function to orchestrate the verification process."""
    logger.info("Starting browser and environment verification...")

    playwright_installed, playwright_version = await check_playwright_installation()

    browser_results = await verify_browser_installations(playwright_installed)

    final_results = {
        "playwright": {
            "installed": playwright_installed,
            "version": playwright_version,
        },
        "browsers": browser_results,
    }

    # Write structured JSON output
    try:
        OUTPUT_FILE.write_text(json.dumps(final_results, indent=4))
        logger.info(f"Successfully wrote verification results to {OUTPUT_FILE}")
    except IOError as e:
        logger.error(f"Failed to write results to {OUTPUT_FILE}: {e}")

    # Generate and print summary
    is_successful, summary = generate_summary(final_results)
    print(summary)

    # Exit with appropriate status code for CI
    sys.exit(0 if is_successful else 1)

if __name__ == "__main__":
    asyncio.run(main())
