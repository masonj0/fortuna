import asyncio
import os
from datetime import datetime
from selectolax.parser import HTMLParser
from python_service.adapters.at_the_races_adapter import AtTheRacesAdapter

async def test_atr_parsing():
    adapter = AtTheRacesAdapter()

    # Test index parsing
    index_path = "debug-snapshots/attheraces/20260128_101537_709387_atr_index_2026-01-28.html"
    with open(index_path, "r") as f:
        index_html = f.read()

    parser = HTMLParser(index_html)
    links = adapter._find_links_with_fallback(parser)
    print(f"Found {len(links)} links in index")

    # Filter links like in the adapter
    import re
    filtered_links = {
        link for link in links
        if re.search(r'/\d{4}$', link) or re.search(r'/\d{1,2}$', link)
    }
    print(f"Filtered to {len(filtered_links)} race links")

    # Test single race parsing
    race_path = "scripts/atr_dundalk.html"
    if os.path.exists(race_path):
        with open(race_path, "r") as f:
            race_html = f.read()

        race_date = datetime(2026, 1, 28).date()
        race = adapter._parse_single_race(race_html, "/racecard/Dundalk/28-January-2026/1432", race_date)

        if race:
            print(f"Parsed Race: {race.venue} at {race.start_time}")
            print(f"Runners: {len(race.runners)}")
            for runner in race.runners[:3]:
                print(f"  - {runner.number}: {runner.name} (Odds: {runner.odds})")
        else:
            print("Failed to parse race")
    else:
        print(f"File {race_path} not found")

if __name__ == "__main__":
    asyncio.run(test_atr_parsing())
