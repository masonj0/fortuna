# jules-scratch/verification/verify_error_handling.py
from playwright.sync_api import expect
from playwright.sync_api import sync_playwright


def run(playwright):
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()

    # Mock the API call to return an error
    page.route(
        "**/api/races/qualified/trifecta?**",
        lambda route: route.fulfill(
            status=500,
            json={
                "error": {
                    "message": "A data source is currently unavailable.",
                    "suggestion": "This is usually temporary. Please try again in a few minutes.",
                    "details": "AdapterHttpError: HTTP Error 503 for https://example.com",
                }
            },
        ),
    )

    page.goto("http://localhost:3000")

    # Wait for the status indicator to show "Offline"
    offline_indicator = page.get_by_text("Offline")
    expect(offline_indicator).to_be_visible()

    # Now that we know the app is in an error state, check for the detailed message
    error_message = page.get_by_text("A data source is currently unavailable.")
    expect(error_message).to_be_visible()

    page.screenshot(path="jules-scratch/verification/error_handling.png")
    browser.close()


with sync_playwright() as playwright:
    run(playwright)
