#!/usr/bin/env python3
# scripts/verify_browsers.py
"""
Verify browser installations are working correctly.
"""

import asyncio
import sys
import os
import json
from datetime import datetime

# Results storage
results = {
    "timestamp": datetime.utcnow().isoformat(),
    "display": os.environ.get("DISPLAY", "not set"),
    "tests": {}
}


async def test_stealthy_session():
    """Test Scrapling's StealthySession (Camoufox)."""
    print("\n" + "=" * 60)
    print("TEST: StealthySession (Camoufox)")
    print("=" * 60)

    try:
        from scrapling.fetchers import StealthyFetcher

        fetcher = StealthyFetcher(
            headless=True,
            block_images=True,
        )

        print("→ Fetching test page...")
        response = await asyncio.wait_for(
            asyncio.to_thread(fetcher.fetch, 'https://httpbin.org/headers'),
            timeout=30
        )

        print(f"✓ Status: {response.status}")
        print(f"✓ Content length: {len(response.text)} chars")

        if response.status == 200 and len(response.text) > 100:
            print("✅ StealthySession PASSED")
            return True, "OK"
        else:
            return False, f"Unexpected response: status={response.status}"

    except ImportError as e:
        print(f"⚠️ Import error: {e}")
        return False, f"Import error: {e}"
    except asyncio.TimeoutError:
        print("⚠️ Timeout")
        return False, "Timeout after 30s"
    except Exception as e:
        print(f"❌ Error: {e}")
        return False, str(e)


async def test_playwright_session():
    """Test Scrapling's PlaywrightFetcher."""
    print("\n" + "=" * 60)
    print("TEST: PlaywrightFetcher (Chromium)")
    print("=" * 60)

    try:
        from scrapling.fetchers import PlayWrightFetcher

        fetcher = PlayWrightFetcher(
            headless=True,
            browser_type='chromium',
        )

        print("→ Fetching test page...")
        response = await asyncio.wait_for(
            asyncio.to_thread(fetcher.fetch, 'https://httpbin.org/get'),
            timeout=30
        )

        print(f"✓ Status: {response.status}")
        print(f"✓ Content length: {len(response.text)} chars")

        if response.status == 200:
            print("✅ PlaywrightFetcher PASSED")
            return True, "OK"
        else:
            return False, f"Status: {response.status}"

    except ImportError as e:
        print(f"⚠️ Import error: {e}")
        return False, f"Import error: {e}"
    except asyncio.TimeoutError:
        print("⚠️ Timeout")
        return False, "Timeout after 30s"
    except Exception as e:
        print(f"❌ Error: {e}")
        return False, str(e)


async def test_async_stealthy():
    """Test async StealthySession."""
    print("\n" + "=" * 60)
    print("TEST: AsyncStealthySession")
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
        else:
            return False, f"Status: {response.status}"

    except ImportError as e:
        print(f"⚠️ Import error: {e}")
        return False, f"Import error: {e}"
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

    # Check scrapling version
    try:
        import scrapling
        print(f"Scrapling: {scrapling.__version__}")
    except:
        print("Scrapling: not installed")
        sys.exit(1)

    # Run tests
    tests = [
        ("async_stealthy", test_async_stealthy),
        ("playwright", test_playwright_session),
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            success, message = await test_func()
            results["tests"][name] = {"passed": success, "message": message}
            if success:
                passed += 1
            else:
                failed += 1
        except Exception as e:
            results["tests"][name] = {"passed": False, "message": str(e)}
            failed += 1

    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")

    for name, result in results["tests"].items():
        status = "✅" if result["passed"] else "❌"
        print(f"  {status} {name}: {result['message']}")

    # Save results
    with open("browser_verification.json", "w") as f:
        json.dump(results, f, indent=2)

    # Exit code
    if passed > 0:
        print("\n✅ At least one browser backend is working")
        return 0
    else:
        print("\n❌ No browser backends available!")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
