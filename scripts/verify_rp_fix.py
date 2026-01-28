import asyncio
import os
from datetime import datetime
from python_service.adapters.racingpost_adapter import RacingPostAdapter

async def test_rp():
    adapter = RacingPostAdapter()

    # Test single race parsing from local file
    race_path = "scripts/racing_post_race.html"
    if os.path.exists(race_path):
        with open(race_path, "r") as f:
            html = f.read()

        raw_data = {"html_contents": [html], "date": "2026-01-28"}
        races = adapter._parse_races(raw_data)

        if races:
            race = races[0]
            print(f"Parsed Race: {race.venue} at {race.start_time} (R{race.race_number})")
            print(f"Runners: {len(race.runners)}")
            for runner in race.runners[:5]:
                print(f"  - {runner.number}: {runner.name} (Odds: {runner.odds}, Scratched: {runner.scratched})")
        else:
            print("Failed to parse race")
    else:
        print(f"File {race_path} not found")

if __name__ == "__main__":
    asyncio.run(test_rp())
