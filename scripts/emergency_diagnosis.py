#!/usr/bin/env python3
"""
EMERGENCY DIAGNOSIS - Test which adapters actually work.
Run this FIRST to see what's really happening.
"""

import asyncio
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Type

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configuration
TIMEOUT_SECONDS = 60
PAUSE_BETWEEN_TESTS = 2


async def test_adapter(adapter_class: Type, adapter_name: str) -> dict[str, Any]:
    """Test a single adapter to see if it actually returns data."""
    print(f"\n{'='*60}")
    print(f"Testing: {adapter_name}")
    print('='*60)

    adapter = None

    try:
        adapter = adapter_class()

        # Test with today's date
        today = datetime.now().strftime('%Y-%m-%d')
        print(f"📅 Fetching races for {today}...")

        # Add timeout protection
        # Most adapters have get_races, but some might have fetch_races in the prompt's pseudocode
        # Looking at at_the_races_adapter.py, it uses get_races (from BaseAdapterV3)
        method_to_call = getattr(adapter, 'get_races', None) or getattr(adapter, 'fetch_races', None)

        if not method_to_call:
            print(f"❌ ERROR: Adapter {adapter_name} has no get_races or fetch_races method")
            return {
                'adapter': adapter_name,
                'status': 'ERROR',
                'error': 'No fetch method found'
            }

        races = await asyncio.wait_for(
            method_to_call(today),
            timeout=TIMEOUT_SECONDS
        )

        if races:
            print(f"✅ SUCCESS: {len(races)} races found!")

            # Show first 3 races
            print("\n📋 Sample races:")
            for i, race in enumerate(races[:3], 1):
                # Race objects might be dicts or models
                if isinstance(race, dict):
                    venue = race.get('venue', 'Unknown')
                    time = race.get('time', 'Unknown')
                    race_type = race.get('type', 'Unknown')
                else:
                    venue = getattr(race, 'venue', 'Unknown')
                    time = getattr(race, 'start_time', 'Unknown')
                    race_type = getattr(race, 'source', 'Unknown')
                print(f"  {i}. {venue} @ {time} ({race_type})")

            # Check SmartFetcher health if available
            if hasattr(adapter, 'smart_fetcher') and adapter.smart_fetcher:
                try:
                    health = adapter.smart_fetcher.get_health_report()
                    best_engine = health.get('best_engine', 'unknown')
                    print(f"\n🔧 Engine used: {best_engine}")
                except Exception:
                    pass

            return {
                'adapter': adapter_name,
                'status': 'SUCCESS',
                'race_count': len(races),
                'sample': str(races[:3])
            }
        else:
            print("⚠️  No races returned (empty list)")
            return {
                'adapter': adapter_name,
                'status': 'NO_DATA',
                'race_count': 0,
                'sample': []
            }

    except asyncio.TimeoutError:
        print(f"⏰ TIMEOUT: Adapter took longer than {TIMEOUT_SECONDS}s")
        return {
            'adapter': adapter_name,
            'status': 'TIMEOUT',
            'error': f'Exceeded {TIMEOUT_SECONDS}s timeout'
        }

    except Exception as e:
        print(f"❌ ERROR: {type(e).__name__}: {str(e)}")

        import traceback
        print("\n🔍 Full traceback:")
        traceback.print_exc()

        return {
            'adapter': adapter_name,
            'status': 'ERROR',
            'error': f"{type(e).__name__}: {str(e)}"
        }

    finally:
        if adapter:
            # Close SmartFetcher if present
            if hasattr(adapter, 'smart_fetcher') and adapter.smart_fetcher:
                try:
                    await adapter.smart_fetcher.close()
                except Exception:
                    pass
            # Close session if present
            if hasattr(adapter, 'session') and adapter.session:
                try:
                    await adapter.session.close()
                except Exception:
                    pass


async def main() -> int:
    print("\n" + "="*60)
    print("🚨 EMERGENCY ADAPTER DIAGNOSIS")
    print("="*60)
    print("\nTesting which adapters actually return race data...")
    print(f"⏱️  Timeout per adapter: {TIMEOUT_SECONDS}s")

    # Import adapters
    adapters_to_test = []

    try:
        from python_service.adapters.at_the_races_adapter import AtTheRacesAdapter
        adapters_to_test.append((AtTheRacesAdapter, "At The Races"))
    except ImportError as e:
        print(f"⚠️  Cannot import AtTheRacesAdapter: {e}")

    try:
        from python_service.adapters.sporting_life_adapter import SportingLifeAdapter
        adapters_to_test.append((SportingLifeAdapter, "Sporting Life"))
    except ImportError as e:
        print(f"⚠️  Cannot import SportingLifeAdapter: {e}")

    try:
        from python_service.adapters.racingpost_adapter import RacingPostAdapter
        adapters_to_test.append((RacingPostAdapter, "Racing Post"))
    except ImportError as e:
        print(f"⚠️  Cannot import RacingPostAdapter: {e}")

    if not adapters_to_test:
        print("\n❌ FATAL: Could not import ANY adapters!")
        print("\nMake sure you're running from the project root:")
        return 1

    # Run tests
    results = []
    for adapter_class, adapter_name in adapters_to_test:
        result = await test_adapter(adapter_class, adapter_name)
        results.append(result)
        await asyncio.sleep(PAUSE_BETWEEN_TESTS)

    # Categorize results
    successful = [r for r in results if r['status'] == 'SUCCESS']
    no_data = [r for r in results if r['status'] == 'NO_DATA']
    timeouts = [r for r in results if r['status'] == 'TIMEOUT']
    errored = [r for r in results if r['status'] == 'ERROR']

    # Print Summary
    print("\n" + "="*60)
    print("📊 DIAGNOSIS SUMMARY")
    print("="*60)

    print(f"\n✅ Working: {len(successful)}")
    for r in successful:
        print(f"   • {r['adapter']}: {r['race_count']} races")

    print(f"\n⚠️  No Data: {len(no_data)}")
    for r in no_data:
        print(f"   • {r['adapter']}: Runs but returns empty")

    print(f"\n⏰ Timeouts: {len(timeouts)}")
    for r in timeouts:
        print(f"   • {r['adapter']}: {r.get('error', 'Timed out')}")

    print(f"\n❌ Errors: {len(errored)}")
    for r in errored:
        error = r.get('error', 'Unknown')[:50]
        print(f"   • {r['adapter']}: {error}")

    # Save results
    import json
    output_file = Path('adapter_diagnosis.json')
    with open(output_file, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'timeout_seconds': TIMEOUT_SECONDS,
            'results': results,
            'summary': {
                'successful': len(successful),
                'no_data': len(no_data),
                'timeouts': len(timeouts),
                'errored': len(errored)
            }
        }, f, indent=2, default=str)

    print(f"\n💾 Results saved to: {output_file.absolute()}")

    return 0 if successful else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
