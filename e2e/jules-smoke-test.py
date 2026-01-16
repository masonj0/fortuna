import asyncio
from playwright.async_api import async_playwright, expect

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        try:
            await page.goto("http://127.0.0.1:8000")
            await expect(page.get_by_test_id("main-heading")).to_be_visible()
            await page.screenshot(path="playwright-screenshot.png")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
