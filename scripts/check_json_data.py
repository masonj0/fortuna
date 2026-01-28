import httpx
import json
from selectolax.parser import HTMLParser

async def test_site(name, url):
    print(f"--- Testing {name} ---")
    async with httpx.AsyncClient(follow_redirects=True, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }) as client:
        try:
            resp = await client.get(url, timeout=20)
            print(f"Status: {resp.status_code}")
            parser = HTMLParser(resp.text)

            # Check for __NEXT_DATA__
            next_data = parser.css_first("script#__NEXT_DATA__")
            if next_data:
                print("Found __NEXT_DATA__!")
                try:
                    data = json.loads(next_data.text())
                    # Print keys of the data
                    print(f"Keys: {list(data.keys())}")
                    if 'props' in data:
                        print(f"Props keys: {list(data['props'].keys())}")
                        if 'pageProps' in data['props']:
                            print(f"pageProps keys: {list(data['props']['pageProps'].keys())}")
                except Exception as e:
                    print(f"Error parsing JSON: {e}")
            else:
                print("__NEXT_DATA__ not found.")

            # Check for Racing Post specific data
            # Racing Post often uses a similar pattern or window.INITIAL_STATE
            for script in parser.css("script"):
                if "window.INITIAL_STATE" in script.text():
                    print("Found window.INITIAL_STATE in Racing Post!")
                    break

        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    import asyncio
    async def main():
        await test_site("Sporting Life", "https://www.sportinglife.com/racing/racecards")
        await test_site("Racing Post", "https://www.racingpost.com/racecards")
    asyncio.run(main())
