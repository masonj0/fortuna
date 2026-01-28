import httpx
from selectolax.parser import HTMLParser

async def check_atr_greyhounds():
    url = "https://greyhounds.attheraces.com/racecards"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    async with httpx.AsyncClient(follow_redirects=True, headers=headers) as client:
        try:
            resp = await client.get(url, timeout=20)
            print(f"Status: {resp.status_code}")
            if resp.status_code == 200:
                with open("scripts/atr_greyhounds_index.html", "w") as f:
                    f.write(resp.text)
                print("Saved index to scripts/atr_greyhounds_index.html")

                parser = HTMLParser(resp.text)
                links = [a.attributes['href'] for a in parser.css('a[href*="/racecard/"]')]
                print(f"Found {len(links)} race links")
                if links:
                    print(f"Sample link: {links[0]}")
            else:
                print(f"Failed to fetch index: {resp.status_code}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(check_atr_greyhounds())
