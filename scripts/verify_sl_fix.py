import asyncio
import os
import json
from datetime import datetime
from python_service.adapters.sporting_life_adapter import SportingLifeAdapter

async def test_sl():
    adapter = SportingLifeAdapter()

    # Test single race parsing from local file
    race_path = "scripts/sl_race.json"
    if os.path.exists(race_path):
        with open(race_path, "r") as f:
            data = json.load(f)

        dummy_html = f'<html><body><script id="__NEXT_DATA__" type="application/json">{json.dumps(data)}</script></body></html>'

        raw_data = {"pages": [dummy_html], "date": "2026-01-28"}
        races = adapter._parse_races(raw_data)

        if races:
            race = races[0]
            print(f"Parsed Race: {race.venue} at {race.start_time} (R{race.race_number})")
            print(f"Runners: {len(race.runners)}")
            for runner in race.runners[:3]:
                print(f"  - {runner.number}: {runner.name} (Odds: {runner.odds})")
        else:
            print("Failed to parse race")
    else:
        print(f"File {race_path} not found")

if __name__ == "__main__":
    asyncio.run(test_sl())
