import asyncio
from python_service.core.smart_fetcher import SmartFetcher, FetchStrategy, BrowserEngine, StealthMode

async def check_twinspires():
    strategy = FetchStrategy(
        primary_engine=BrowserEngine.HTTPX, # Start with HTTPX for quick check
        enable_js=False,
        timeout=20
    )
    fetcher = SmartFetcher(strategy=strategy)

    urls = [
        "https://www.twinspires.com/bet/todays-races/time",
        "https://www.twinspires.com/bet/todays-races/thoroughbred",
        "https://www.twinspires.com/bet/todays-races/harness",
        "https://www.twinspires.com/bet/todays-races/greyhound"
    ]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    }

    for url in urls:
        print(f"Checking {url}...")
        try:
            resp = await fetcher.fetch(url, headers=headers)
            print(f"  Status: {resp.status}")
            print(f"  Size: {len(resp.text)} chars")
            # Save a snippet
            with open(f"scripts/ts_{url.split('/')[-1]}.html", "w") as f:
                f.write(resp.text)
        except Exception as e:
            print(f"  Error: {e}")

    await fetcher.close()

if __name__ == "__main__":
    asyncio.run(check_twinspires())
