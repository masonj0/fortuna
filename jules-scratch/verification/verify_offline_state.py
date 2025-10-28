from playwright.sync_api import sync_playwright, expect

def run_verification():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Navigate to the frontend application
        page.goto("http://localhost:3000")

        # Wait for the initial "Connecting..." state to resolve.
        connecting_status = page.get_by_text("Connecting...")
        expect(connecting_status).to_be_hidden(timeout=15000)

        # Now that the connection attempt is finished, check for the offline message.
        offline_title = page.get_by_text("Backend Service Offline")
        expect(offline_title).to_be_visible(timeout=5000)

        # Capture the final, correct state
        page.screenshot(path="jules-scratch/verification/offline-dashboard-final.png")

        browser.close()

if __name__ == "__main__":
    run_verification()
