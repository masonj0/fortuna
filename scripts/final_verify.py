import asyncio
from datetime import datetime
from python_service.adapters import (
    AtTheRacesAdapter,
    AtTheRacesGreyhoundAdapter,
    SportingLifeAdapter,
    RacingPostAdapter,
    TimeformAdapter
)

async def verify_all():
    date = "2026-01-28"
    adapters = [
        AtTheRacesAdapter(),
        AtTheRacesGreyhoundAdapter(),
        SportingLifeAdapter(),
        RacingPostAdapter(),
        TimeformAdapter()
    ]

    for adapter in adapters:
        print(f"--- Testing {adapter.source_name} ---")
        try:
            # We'll just test index fetching and parsing logic if possible
            # To avoid full run during verification (might be slow/blocked)
            # but since I already have some local files, I'll use those for some
            pass
        except Exception as e:
            print(f"Error testing {adapter.source_name}: {e}")
        finally:
            await adapter.close()

if __name__ == "__main__":
    # Actually, I'll just re-run the previous specific verification scripts
    # to ensure they still work after all changes.
    pass
