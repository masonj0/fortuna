import httpx
import json
from selectolax.parser import HTMLParser

async def test_site(name, url):
    print(f"--- Testing {name} ---")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
    }
    async with httpx.AsyncClient(follow_redirects=True, headers=headers) as client:
        try:
            resp = await client.get(url, timeout=20)
            print(f"Status: {resp.status_code}")
            if resp.status_code == 200:
                 with open(f"scripts/{name.lower().replace(' ', '_')}.html", "w") as f:
                     f.write(resp.text)
                 print(f"Saved to scripts/{name.lower().replace(' ', '_')}.html")
            else:
                print(f"Response text start: {resp.text[:500]}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    import asyncio
    async def main():
        await test_site("Racing Post", "https://www.racingpost.com/racecards")
    asyncio.run(main())
