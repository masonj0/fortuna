# jules-scratch/verification/verify_launch.py
from playwright.sync_api import sync_playwright, expect

def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()

    page.goto("http://localhost:3002")

    # Wait for the dashboard to be visible
    dashboard_title = page.get_by_text("Fortuna Faucet")
    expect(dashboard_title).to_be_visible()

    page.screenshot(path="jules-scratch/verification/launch.png")
    browser.close()

with sync_playwright() as playwright:
    run(playwright)
