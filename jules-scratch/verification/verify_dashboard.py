from playwright.sync_api import sync_playwright, expect
import time

def run(playwright):
    browser = playwright.chromium.launch()
    page = browser.new_page()

    # Give the dev servers time to start up
    time.sleep(15)

    page.goto("http://localhost:3000")

    # Expect the connection status to eventually turn green
    expect(page.locator('text=Connected to Fortuna Engine')).to_be_visible(timeout=15000)

    # Take a screenshot showing the green status indicator
    page.screenshot(path="jules-scratch/verification/verification.png")

    browser.close()

with sync_playwright() as playwright:
    run(playwright)
