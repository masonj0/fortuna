import httpx
from selectolax.parser import HTMLParser
import json

async def check_atr_greyhound_race():
    # Use one from the JSON-LD we saw
    url = "https://greyhounds.attheraces.com/racecard/GB/doncaster/28-January-2026/1433"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    async with httpx.AsyncClient(follow_redirects=True, headers=headers) as client:
        try:
            resp = await client.get(url, timeout=20)
            print(f"Status: {resp.status_code}")
            if resp.status_code == 200:
                with open("scripts/atr_greyhound_race.html", "w") as f:
                    f.write(resp.text)
                print("Saved race to scripts/atr_greyhound_race.html")

                parser = HTMLParser(resp.text)
                # Look for data
                # SPAs usually have a global variable or a script tag with JSON
                for script in parser.css("script"):
                    if "window.__INITIAL_STATE__" in script.text():
                        print("Found window.__INITIAL_STATE__")
                        # Extract JSON
                        # ...
                    if "application/ld+json" in script.attributes.get("type", ""):
                        print("Found JSON-LD in race page")
                        try:
                            data = json.loads(script.text())
                            # Check if it has runners
                            if isinstance(data, dict) and "@graph" in data:
                                for item in data["@graph"]:
                                    if item.get("@type") == "SportsEvent":
                                         print(f"Race: {item.get('name')}")
                        except:
                            pass
            else:
                print(f"Failed to fetch race: {resp.status_code}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(check_atr_greyhound_race())
