
import asyncio
from python_service.adapters.at_the_races_adapter import AtTheRacesAdapter

async def test_atr():
    adapter = AtTheRacesAdapter()
    print(f"Testing {adapter.source_name}...")

    # Test regex
    url1 = "/racecard/GP/Attheraces-Sky-Sports-Racing-Hd-Virgin-535/2026-01-27/1520/1"
    url2 = "/racecard/Vaal/27-January-2026/1010"

    num1 = adapter._extract_race_number(url1)
    num2 = adapter._extract_race_number(url2)

    print(f"URL 1: {url1} -> Race {num1}")
    print(f"URL 2: {url2} -> Race {num2}")

    # Test fetch (this might fail if network is down or blocked)
    try:
        # data = await adapter._fetch_data("2026-01-27")
        # print(f"Fetch success: {len(data.get('pages', [])) if data else 0} pages")
        pass
    except Exception as e:
        print(f"Fetch failed: {e}")
    finally:
        await adapter.close()

if __name__ == "__main__":
    asyncio.run(test_atr())
