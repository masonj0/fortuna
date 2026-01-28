import asyncio
import os
from datetime import datetime
from python_service.adapters.at_the_races_greyhound_adapter import AtTheRacesGreyhoundAdapter

async def test_atr_greyhound():
    adapter = AtTheRacesGreyhoundAdapter()

    # Test index parsing from local file
    index_path = "scripts/atr_greyhounds_index.html"
    if os.path.exists(index_path):
        from selectolax.parser import HTMLParser
        with open(index_path, "r") as f:
            html = f.read()
        parser = HTMLParser(html)
        links = adapter._extract_links_from_json_ld(parser)
        print(f"Found {len(links)} links in index")
    else:
        print(f"File {index_path} not found")

    # Test single race parsing from local file
    race_path = "scripts/atr_greyhound_race.html"
    if os.path.exists(race_path):
        with open(race_path, "r") as f:
            race_html = f.read()

        race_date = datetime(2026, 1, 28).date()
        race = adapter._parse_single_race(race_html, "/racecard/GB/doncaster/28-January-2026/1433", race_date)

        if race:
            print(f"Parsed Race: {race.venue} at {race.start_time}")
            print(f"Runners: {len(race.runners)}")
            for runner in race.runners:
                print(f"  - Trap {runner.number}: {runner.name} (Odds: {runner.odds})")
        else:
            print("Failed to parse race")
    else:
        print(f"File {race_path} not found")

if __name__ == "__main__":
    asyncio.run(test_atr_greyhound())
