import httpx
import json
from selectolax.parser import HTMLParser

async def test_sl_json():
    url = "https://www.sportinglife.com/racing/racecards"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    async with httpx.AsyncClient(follow_redirects=True, headers=headers) as client:
        resp = await client.get(url, timeout=20)
        parser = HTMLParser(resp.text)
        next_data = parser.css_first("script#__NEXT_DATA__")
        data = json.loads(next_data.text())

        meetings = data['props']['pageProps']['meetings']
        print(f"Found {len(meetings)} meetings")

        for meeting in meetings[:2]:
            print(f"Meeting: {meeting.get('name')} ({meeting.get('id')})")
            races = meeting.get('races', [])
            print(f"  Races: {len(races)}")
            for race in races[:2]:
                print(f"    Race: {race.get('time')} - {race.get('name')} (ID: {race.get('id')})")
                # Does it have runners?
                if 'runners' in race:
                    print(f"      Runners: {len(race['runners'])}")
                else:
                    print("      No runners in index JSON")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_sl_json())
