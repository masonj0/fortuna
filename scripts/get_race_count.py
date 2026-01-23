import json
import sys

def get_race_count():
    """
    Reads 'qualified_races.json', counts the number of races, and prints the count.
    Prints 0 if the file doesn't exist or is invalid.
    """
    try:
        with open('qualified_races.json') as f:
            data = json.load(f)
        print(len(data.get('races', [])))
    except (json.JSONDecodeError, IOError):
        print(0)

if __name__ == "__main__":
    get_race_count()
