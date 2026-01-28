import httpx
from selectolax.parser import HTMLParser

async def test_tf_race():
    url = "https://www.timeform.com/horse-racing/racecards/dundalk/2026-01-28/1432/207/1/view-restaurant-at-dundalk-stadium-maiden"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    async with httpx.AsyncClient(follow_redirects=True, headers=headers) as client:
        try:
            resp = await client.get(url, timeout=20)
            print(f"Status: {resp.status_code}")
            if resp.status_code == 200:
                with open("scripts/tf_race.html", "w") as f:
                    f.write(resp.text)
                print("Saved race to scripts/tf_race.html")
            else:
                print(f"Failed to fetch race: {resp.status_code}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_tf_race())
