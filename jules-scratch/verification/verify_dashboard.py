
import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        await page.goto("http://localhost:3000")

        # Wait for a key element to be visible to ensure the page has loaded
        await page.wait_for_selector("h2:has-text('Adapter Status')")

        await page.screenshot(path="jules-scratch/verification/verification.png")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
