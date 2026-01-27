
import asyncio
from scrapling import Fetcher, StealthyFetcher
try:
    from scrapling.fetchers import AsyncStealthySession
except ImportError:
    AsyncStealthySession = None

async def test_scrapling():
    print("--- Testing StealthyFetcher (Sync) ---")
    sf = StealthyFetcher()
    try:
        # Check if it raises sync error inside event loop
        resp = sf.fetch("https://httpbin.org/get")
        print(f"StealthyFetcher.fetch status: {resp.status}")
    except Exception as e:
        print(f"StealthyFetcher.fetch error: {e}")

    if AsyncStealthySession:
        print("\n--- Testing AsyncStealthySession ---")
        session = AsyncStealthySession(headless=True)
        await session.start()
        try:
            resp = await session.fetch("https://httpbin.org/get")
            print(f"AsyncStealthySession.fetch status: {resp.status}")
        except Exception as e:
            print(f"AsyncStealthySession.fetch error: {e}")
        finally:
            await session.close()

    print("\n--- Testing Fetcher (Sync) ---")
    f = Fetcher()
    try:
        resp = f.get("https://httpbin.org/get")
        print(f"Fetcher.get status: {resp.status}")
    except Exception as e:
        print(f"Fetcher.get error: {e}")

if __name__ == "__main__":
    asyncio.run(test_scrapling())
