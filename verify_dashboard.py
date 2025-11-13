
from playwright.sync_api import sync_playwright

def verify_dashboard(page):
    """
    Navigates to the dashboard and takes a screenshot.
    """
    page.goto("http://localhost:3000")
    page.wait_for_selector("text=Fortuna Faucet")
    page.screenshot(path="verification.png")

if __name__ == "__main__":
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            verify_dashboard(page)
        finally:
            browser.close()
