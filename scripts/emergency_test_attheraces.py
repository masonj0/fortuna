# scripts/emergency_test_attheraces.py
"""Test if AtTheRaces adapter actually works."""
import asyncio
import os
import sys
from datetime import datetime

# Add root to sys.path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from python_service.adapters.at_the_races_adapter import AtTheRacesAdapter

async def main():
    adapter = AtTheRacesAdapter()

    try:
        print("🔍 Testing AtTheRaces adapter...")

        # Try to fetch races for today
        # today = datetime.now().strftime('%Y-%m-%d')
        # Use a hardcoded date that likely has data if today is empty, or just use today
        today = "2026-01-28"
        print(f"📅 Fetching for date: {today}")
        races = await adapter.get_races(today)

        print(f"\n✅ SUCCESS: Found {len(races)} races!")

        if races:
            print("\nFirst 3 races:")
            for race in races[:3]:
                # Adjusting based on expected Race model attributes
                venue = getattr(race, 'venue', 'N/A')
                start_time = getattr(race, 'start_time', 'N/A')
                source = getattr(race, 'source', 'N/A')
                print(f"  - {venue} at {start_time} (Source: {source})")

        # Save debug output
        if hasattr(adapter, 'smart_fetcher'):
            health = adapter.smart_fetcher.get_health_report()
            print(f"\n🔧 Engine used: {health.get('best_engine')}")

        return len(races) > 0

    except Exception as e:
        print(f"❌ FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        if hasattr(adapter, 'smart_fetcher'):
            await adapter.smart_fetcher.close()

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
