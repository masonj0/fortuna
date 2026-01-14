import json
import os
import glob
from datetime import datetime

def get_latest_race_file(data_dir):
    """Finds the most recently modified race data file in the directory."""
    list_of_files = glob.glob(os.path.join(data_dir, '*.json'))
    if not list_of_files:
        return None
    latest_file = max(list_of_files, key=os.path.getmtime)
    return latest_file

def main():
    data_dir = os.path.join('web_service', 'backend', 'data')
    output_file = 'race-info.txt'

    if not os.path.exists(data_dir):
        with open(output_file, 'w') as f:
            f.write("Data directory not found.\n")
        return

    latest_file = get_latest_race_file(data_dir)

    if not latest_file:
        with open(output_file, 'w') as f:
            f.write("No race data files found.\n")
        return

    try:
        with open(latest_file, 'r') as f:
            race_data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        with open(output_file, 'w') as f:
            f.write(f"Error reading race data file: {e}\n")
        return

    if not race_data or not isinstance(race_data, list):
        with open(output_file, 'w') as f:
            f.write("Race data is empty or not in the expected format.\n")
        return

    # Assuming the first race in the list is the one we want.
    # A better approach might be to sort by start_time if available.
    latest_race = race_data[0]

    venue = latest_race.get('venue', 'N/A')
    race_number = latest_race.get('raceNumber', 'N/A') # Use alias
    runners = latest_race.get('runners', [])
    num_runners = len(runners)

    with open(output_file, 'w') as f:
        f.write(f"Latest Race Info:\n")
        f.write(f"  Track: {venue}\n")
        f.write(f"  Race #: {race_number}\n")
        f.write(f"  Field Size: {num_runners}\n")

if __name__ == "__main__":
    main()
