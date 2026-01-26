#!/usr/bin/env python3
"""Verify browser installations are working correctly."""

import asyncio
import sys
import os
import json
from datetime import datetime

results = {
    "timestamp": datetime.utcnow().isoformat(),
    "display": os.environ.get("DISPLAY", "not set"),
    "python_version": sys.version.split()[0],
    "tests": {}
}


async def test_playwright_chromium():
    """Test Playwright Chromium."""
    print("\n" + "=" * 60)
    print("TEST: Playwright Chromium")
    print("=" * 60)

    try:
        from scrapling.fetchers import PlayWrightFetcher

        fetcher = PlayWrightFetcher(
            headless=True,
            browser_type='chromium',
        )

        print("→ Fetching test page...")
        response = fetcher.fetch('https://httpbin.org/get')

        print(f"✓ Status: {response.status}")
        print(f"✓ Content: {len(response.text)} chars")

        if response.status == 200:
            print("✅ Playwright Chromium PASSED")
            return True, "OK"
        return False, f"Status: {response.status}"

    except Exception as e:
        print(f"❌ Error: {e}")
        return False, str(e)


async def test_async_stealthy():
    """Test AsyncStealthySession."""
    print("\n" + "=" * 60)
    print("TEST: AsyncStealthySession (Camoufox)")
    print("=" * 60)

    session = None
    try:
        from scrapling.fetchers import AsyncStealthySession

        session = AsyncStealthySession(
            headless=True,
            block_images=True,
        )

        print("→ Starting session...")
        await session.start()
        print("✓ Session started")

        print("→ Fetching test page...")
        response = await asyncio.wait_for(
            session.fetch('https://httpbin.org/headers'),
            timeout=30
        )

        print(f"✓ Status: {response.status}")

        if response.status == 200:
            print("✅ AsyncStealthySession PASSED")
            return True, "OK"
        return False, f"Status: {response.status}"

    except ImportError as e:
        print(f"⚠️ Not available: {e}")
        return False, f"Import error: {e}"
    except asyncio.TimeoutError:
        print("⚠️ Timeout")
        return False, "Timeout"
    except Exception as e:
        print(f"❌ Error: {e}")
        return False, str(e)
    finally:
        if session:
            try:
                await session.close()
                print("✓ Session closed")
            except:
                pass


async def main():
    """Run all browser tests."""
    print("=" * 60)
    print("BROWSER VERIFICATION")
    print("=" * 60)
    print(f"Display: {os.environ.get('DISPLAY', 'not set')}")
    print(f"Python: {sys.version.split()[0]}")

    try:
        import scrapling
        print(f"Scrapling: {scrapling.__version__}")
        results["scrapling_version"] = scrapling.__version__
    except:
        print("Scrapling: not found")
        results["scrapling_version"] = "not found"

    tests = [
        ("playwright_chromium", test_playwright_chromium),
        ("async_stealthy", test_async_stealthy),
    ]

    passed = 0

    for name, test_func in tests:
        try:
            success, message = await test_func()
            results["tests"][name] = {"passed": success, "message": message}
            if success:
                passed += 1
        except Exception as e:
            results["tests"][name] = {"passed": False, "message": str(e)}

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    for name, result in results["tests"].items():
        status = "✅" if result["passed"] else "❌"
        print(f"  {status} {name}: {result['message']}")

    print(f"\nPassed: {passed}/{len(tests)}")

    # Save results
    with open("browser_verification.json", "w") as f:
        json.dump(results, f, indent=2)

    if passed > 0:
        print("\n✅ At least one browser is working")
        return 0
    else:
        print("\n❌ No browsers available!")
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
