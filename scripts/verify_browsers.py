#!/usr/bin/env python3
"""
Enhanced Browser Verification Script (Scrapling 0.3.x compatible)
Tests all available browser engines and provides actionable recommendations
"""

import asyncio
import sys
import os
import json
from datetime import datetime
from pathlib import Path
import traceback
import shutil

# Results structure
results = {
    "timestamp": datetime.utcnow().isoformat(),
    "environment": {
        "display": os.environ.get("DISPLAY", "not set"),
        "python_version": sys.version.split()[0],
        "ci": os.environ.get("CI", "false"),
        "headless": os.environ.get("SCRAPLING_HEADLESS", "true"),
        "xvfb_running": False,
    },
    "tests": {},
    "recommendations": [],
    "summary": {
        "total_tests": 0,
        "passed": 0,
        "failed": 0,
        "operational_engines": []
    }
}

def check_display():
    """Check if display server is available"""
    display = os.environ.get("DISPLAY")
    if not display:
        return False, "DISPLAY not set"

    # Try to connect to display
    try:
        import subprocess
        # Check if xdpyinfo exists
        if not shutil.which("xdpyinfo"):
            return False, "xdpyinfo not found"

        result = subprocess.run(
            ['xdpyinfo', '-display', display],
            capture_output=True,
            timeout=5
        )
        if result.returncode == 0:
            results["environment"]["xvfb_running"] = True
            return True, f"Display {display} accessible"
        return False, f"Display {display} not accessible"
    except Exception as e:
        return False, f"Could not check display: {e}"

async def test_httpx_fallback():
    """Test basic HTTPX fetcher (lightweight fallback)"""
    print("\n" + "=" * 60)
    print("TEST 1/4: HTTPX Fallback (Lightweight)")
    print("=" * 60)

    test_name = "httpx_fallback"
    results["tests"][test_name] = {
        "started": datetime.utcnow().isoformat(),
        "passed": False,
        "duration_ms": 0,
        "details": {}
    }

    start = datetime.now()

    try:
        from scrapling import Fetcher
        print("✓ Scrapling imported")

        print("→ Initializing HTTPX fetcher...")
        # Use httpx backend explicitly for stability
        fetcher = Fetcher()
        try:
            fetcher.configure(backend='httpx')
        except:
            pass
        print("✓ Fetcher initialized")

        print("→ Testing basic fetch...")
        # In scrapling 0.3.x, use .get()
        response = fetcher.get('https://httpbin.org/get')

        duration_ms = (datetime.now() - start).total_seconds() * 1000

        print(f"✓ Status: {response.status}")
        print(f"✓ Content length: {len(response.text)} chars")
        print(f"✓ Duration: {duration_ms:.0f}ms")

        # Verify response content
        if response.status == 200 and len(response.text) > 100:
            print("✅ HTTPX PASSED")
            results["tests"][test_name].update({
                "passed": True,
                "message": "Basic HTTP fetch working",
                "duration_ms": duration_ms,
                "details": {
                    "status": response.status,
                    "content_length": len(response.text)
                }
            })
            return True, "Basic HTTP fetch working"

        return False, f"Unexpected response: {response.status}"

    except Exception as e:
        print(f"❌ Error: {str(e)}")
        results["tests"][test_name]["message"] = str(e)
        traceback.print_exc()
        return False, str(e)
    finally:
        results["tests"][test_name]["duration_ms"] = (datetime.now() - start).total_seconds() * 1000

async def test_playwright_chromium():
    """Test Playwright Chromium (Recommended for CI)"""
    print("\n" + "=" * 60)
    print("TEST 2/4: Playwright Chromium (Recommended for CI)")
    print("=" * 60)

    test_name = "playwright_chromium"
    results["tests"][test_name] = {
        "started": datetime.utcnow().isoformat(),
        "passed": False,
        "duration_ms": 0,
        "details": {}
    }

    start = datetime.now()
    session = None
    try:
        from scrapling.fetchers import AsyncDynamicSession
        print("✓ AsyncDynamicSession imported")

        print("→ Initializing Playwright (Chromium) session...")
        session = AsyncDynamicSession(
            headless=True,
            disable_resources=True
        )
        await session.start()
        print("✓ Session started")

        print("→ Testing HTML fetch...")
        response = await session.fetch('https://httpbin.org/html')
        print(f"✓ Status: {response.status}")
        print(f"✓ Content: {len(response.text)} chars")

        duration_ms = (datetime.now() - start).total_seconds() * 1000
        print(f"✓ Total duration: {duration_ms:.0f}ms")

        print("✅ PLAYWRIGHT CHROMIUM PASSED")
        results["tests"][test_name].update({
            "passed": True,
            "message": "All Playwright tests passed",
            "duration_ms": duration_ms,
            "details": {
                "status": response.status
            }
        })
        return True, "All Playwright tests passed"

    except Exception as e:
        msg = str(e)
        print(f"❌ Error: {msg}")
        results["tests"][test_name]["message"] = msg
        return False, msg
    finally:
        if session:
            try:
                await session.close()
            except:
                pass
        results["tests"][test_name]["duration_ms"] = (datetime.now() - start).total_seconds() * 1000

async def test_playwright_firefox():
    """Test Playwright Firefox (Backup)"""
    # Not easily supported via AsyncDynamicSession which defaults to Chromium
    # We'll skip this for now or implement if needed
    print("\n" + "=" * 60)
    print("TEST 3/4: Playwright Firefox (Backup)")
    print("=" * 60)
    print("Skipping Firefox specific test as AsyncDynamicSession is Chromium optimized.")
    return True, "Skipped"

async def test_async_stealthy():
    """Test AsyncStealthySession (Camoufox - most stealthy)"""
    print("\n" + "=" * 60)
    print("TEST 4/4: AsyncStealthySession (Camoufox - Most Stealthy)")
    print("=" * 60)

    test_name = "async_stealthy"
    results["tests"][test_name] = {
        "started": datetime.utcnow().isoformat(),
        "passed": False,
        "duration_ms": 0,
        "details": {}
    }

    session = None
    start = datetime.now()

    try:
        from scrapling.fetchers import AsyncStealthySession
        print("✓ AsyncStealthySession imported")

        print("→ Initializing Camoufox session...")
        session = AsyncStealthySession(
            headless=True,
            disable_resources=True,
        )

        print("→ Starting session (may take 10-30s)...")
        await asyncio.wait_for(session.start(), timeout=45)
        print("✓ Session started")

        print("→ Testing stealth fetch...")
        response = await asyncio.wait_for(
            session.fetch('https://httpbin.org/headers'),
            timeout=30
        )

        duration_ms = (datetime.now() - start).total_seconds() * 1000

        print(f"✓ Status: {response.status}")
        print(f"✓ Content: {len(response.text)} chars")
        print(f"✓ Duration: {duration_ms:.0f}ms")

        print("✅ CAMOUFOX PASSED")
        results["tests"][test_name].update({
            "passed": True,
            "message": "Camoufox stealth working",
            "duration_ms": duration_ms,
            "details": {
                "stealth": True
            }
        })
        return True, "Camoufox stealth working"

    except Exception as e:
        msg = str(e)
        print(f"⚠️ Error: {msg}")
        results["tests"][test_name]["message"] = msg
        return False, msg
    finally:
        if session:
            try:
                await asyncio.wait_for(session.close(), timeout=10)
                print("✓ Session closed")
            except:
                pass
        results["tests"][test_name]["duration_ms"] = (datetime.now() - start).total_seconds() * 1000

def generate_recommendations():
    """Generate actionable recommendations based on test results"""
    recs = []

    test_results = results["tests"]
    passed_tests = [name for name, result in test_results.items() if result.get("passed")]

    # Critical: No browsers available
    if not passed_tests:
        recs.append({
            "level": "CRITICAL",
            "icon": "🚨",
            "message": "NO BROWSERS AVAILABLE!",
            "action": "Install Playwright browsers: playwright install chromium --with-deps"
        })
        return recs

    # Check HTTPX
    if "httpx_fallback" not in passed_tests:
        recs.append({
            "level": "WARNING",
            "icon": "⚠️",
            "message": "HTTPX fallback not working",
            "action": "Check Scrapling installation: pip install 'scrapling[all]'"
        })

    # Check Playwright Chromium (most important for CI)
    if "playwright_chromium" not in passed_tests:
        recs.append({
            "level": "CRITICAL",
            "icon": "🚨",
            "message": "Playwright Chromium not working",
            "action": "Install: playwright install chromium --with-deps"
        })
    else:
        recs.append({
            "level": "SUCCESS",
            "icon": "✅",
            "message": "Playwright Chromium working (recommended for CI)"
        })

    # Check Camoufox
    if "async_stealthy" not in passed_tests:
        recs.append({
            "level": "INFO",
            "icon": "ℹ️",
            "message": "Camoufox not available (optional)",
            "action": "For anti-bot protection, install: pip install camoufox"
        })
    else:
        recs.append({
            "level": "SUCCESS",
            "icon": "✅",
            "message": "Camoufox available (best for anti-bot sites)"
        })

    # Check display
    if not results["environment"]["xvfb_running"]:
        recs.append({
            "level": "WARNING",
            "icon": "⚠️",
            "message": "No display server detected",
            "action": "For headless browsers, start Xvfb: Xvfb :99 -screen 0 1920x1080x24 &"
        })

    return recs

async def main():
    """Run comprehensive browser verification"""
    print("=" * 60)
    print("BROWSER VERIFICATION SUITE")
    print("=" * 60)
    print(f"Timestamp: {results['timestamp']}")
    print(f"Display: {os.environ.get('DISPLAY', 'not set')}")
    print(f"Python: {sys.version.split()[0]}")
    print(f"CI Mode: {os.environ.get('CI', 'false')}")
    print(f"Headless: {os.environ.get('SCRAPLING_HEADLESS', 'true')}")

    # Check display
    display_ok, display_msg = check_display()
    print(f"Display Status: {display_msg}")

    # Check Scrapling
    try:
        import scrapling
        version = scrapling.__version__
        print(f"Scrapling: v{version}")
        results["environment"]["scrapling_version"] = version
    except Exception as e:
        print(f"❌ FATAL: Scrapling not installed: {e}")
        print("Install with: pip install 'scrapling[all]'")
        results["summary"]["fatal_error"] = "Scrapling not installed"

        # Save results
        with open("browser_verification.json", "w") as f:
            json.dump(results, f, indent=2)

        return 1

    # Run tests
    tests = [
        ("httpx_fallback", test_httpx_fallback),
        ("playwright_chromium", test_playwright_chromium),
        ("async_stealthy", test_async_stealthy),
    ]

    passed = 0
    results["summary"]["total_tests"] = len(tests)

    for name, test_func in tests:
        try:
            success, message = await test_func()
            if success:
                passed += 1
                results["summary"]["operational_engines"].append(name)
        except Exception as e:
            print(f"\n❌ Test {name} crashed: {e}")
            traceback.print_exc()

    results["summary"]["passed"] = passed
    results["summary"]["failed"] = len(tests) - passed

    # Generate recommendations
    results["recommendations"] = generate_recommendations()

    # Print Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)

    for name, result in results["tests"].items():
        status = "✅" if result.get("passed") else "❌"
        message = result.get("message", "No message")
        duration = result.get("duration_ms", 0)
        print(f"  {status} {name}: {message} ({duration:.0f}ms)")

    print(f"\n📊 Results: {passed}/{len(tests)} tests passed")

    # Print recommendations
    if results["recommendations"]:
        print("\n" + "=" * 60)
        print("RECOMMENDATIONS")
        print("=" * 60)
        for rec in results["recommendations"]:
            icon = rec.get("icon", "•")
            level = rec.get("level", "INFO")
            message = rec.get("message", "")
            action = rec.get("action", "")

            print(f"\n{icon} [{level}] {message}")
            if action:
                print(f"   → {action}")

    # Save detailed results
    output_path = Path("browser_verification.json")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n📄 Detailed results saved to: {output_path}")

    # Determine exit code
    print("\n" + "=" * 60)
    if passed == 0:
        print("❌ CRITICAL: No browsers available!")
        print("🔧 Action Required: Install browsers before running scrapers")
        return 1
    elif passed < len(tests):
        print("⚠️  Some browsers unavailable, but system operational")
        print(f"✅ Operational engines: {', '.join(results['summary']['operational_engines'])}")
        return 0
    else:
        print("✅ All browsers working perfectly!")
        return 0

if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
