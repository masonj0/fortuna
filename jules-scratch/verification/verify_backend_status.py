from playwright.sync_api import sync_playwright, expect
import time

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()

    # Mock the Electron API
    page.add_init_script("""
        window.electronAPI = {
            getApiKey: () => Promise.resolve('test-api-key'),
            getBackendStatus: () => Promise.resolve({ state: 'stopped', logs: [] }),
            onBackendStatusUpdate: (callback) => {
                // Do nothing
                return () => {}; // Return an unsubscribe function
            },
            restartBackend: () => {
                // Simulate a restart
                window.electronAPI.getBackendStatus = () => Promise.resolve({ state: 'running', logs: [] });
            }
        };
    """)

    page.goto("http://localhost:3000")

    # Check that the "Stopped" state is shown
    expect(page.locator('[data-testid="status-indicator"]')).to_have_text("Stopped")
    expect(page.get_by_text("Backend Service Stopped")).to_be_visible()

    # Click the "Start Backend Service" button
    page.get_by_text("Start Backend Service").click()

    # Check that the status indicator eventually shows "Live"
    expect(page.locator('[data-testid="status-indicator"]')).to_have_text("Live", timeout=5000)

    page.screenshot(path="jules-scratch/verification/backend-status.png")
    browser.close()

with sync_playwright() as playwright:
    run(playwright)
