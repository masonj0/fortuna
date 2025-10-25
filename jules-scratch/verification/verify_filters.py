from playwright.sync_api import sync_playwright

def run(playwright):
    browser = playwright.chromium.launch()
    page = browser.new_page()
    page.goto("http://localhost:3000")

    # Click the "Show" button to expand the filters
    page.get_by_role("button", name="Show").click()

    # Change the "Max Field Size" slider
    page.get_by_label("Max Field Size").fill("15")

    page.screenshot(path="jules-scratch/verification/verification.png")
    browser.close()

with sync_playwright() as playwright:
    run(playwright)
