#!/usr/bin/env python3
"""
Test which racing sites are accessible with simple HTTPX (no browser needed).
These are your "quick win" sites that might work right now.

Features:
- Parallel testing for speed
- Configurable concurrency
- Comprehensive bot detection
- Organized output files
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import httpx
from selectolax.parser import HTMLParser


# ============================================================================
# CONFIGURATION
# ============================================================================

TIMEOUT_SECONDS = 30
MAX_CONCURRENT = 3  # Don't hammer all sites at once
OUTPUT_DIR = Path("httpx_test_output")

# Standard browser headers
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate, br',
    'DNT': '1',
    'Connection': 'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Cache-Control': 'max-age=0'
}

# Sites to test
SITES_TO_TEST: list[dict[str, Any]] = [
    {
        "name": "At The Races",
        "url": "https://www.attheraces.com/racecards",
        "check": lambda html: "racecard" in html.lower() or "race card" in html.lower(),
        "notes": "Usually works without JavaScript"
    },
    {
        "name": "Racing TV",
        "url": "https://www.racingtv.com/racecards",
        "check": lambda html: "racecard" in html.lower() or "fixture" in html.lower(),
        "notes": "Simple HTML site"
    },
    {
        "name": "Horse Racing Nation",
        "url": "https://www.horseracingnation.com/race_cards",
        "check": lambda html: "race" in html.lower() and ("card" in html.lower() or "entries" in html.lower()),
        "notes": "US site, might work"
    },
    {
        "name": "Equibase",
        "url": "https://www.equibase.com/premium/todaysRacingLanding.cfm",
        "check": lambda html: "entries" in html.lower() or "racing" in html.lower(),
        "notes": "Official US racing data"
    },
    {
        "name": "Racing Post",
        "url": "https://www.racingpost.com/racecards",
        "check": lambda html: "racecard" in html.lower(),
        "notes": "Will likely be blocked, but worth checking"
    },
    {
        "name": "Sporting Life",
        "url": "https://www.sportinglife.com/racing/racecards",
        "check": lambda html: "racecard" in html.lower(),
        "notes": "Will likely be blocked, but worth checking"
    },
    {
        "name": "Timeform",
        "url": "https://www.timeform.com/horse-racing/racecards",
        "check": lambda html: "racecard" in html.lower() or "race card" in html.lower(),
        "notes": "Premium data source"
    },
    {
        "name": "Sky Sports Racing",
        "url": "https://www.skysports.com/racing/racecards",
        "check": lambda html: "race" in html.lower(),
        "notes": "May have good coverage"
    },
]


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def detect_blocking(html: str) -> list[str]:
    """Detect common bot protection systems."""
    blocking_signs = {
        'cloudflare': 'cloudflare' in html.lower() and 'checking your browser' in html.lower(),
        'cloudflare_challenge': 'cf-browser-verification' in html or '_cf_chl' in html,
        'cloudflare_turnstile': 'turnstile' in html.lower() and 'cloudflare' in html.lower(),
        'perimeter_x': '_px' in html or 'perimeterx' in html.lower(),
        'datadome': 'datadome' in html.lower(),
        'akamai': 'akamai' in html.lower() and 'bot' in html.lower(),
        'imperva': 'imperva' in html.lower() or 'incapsula' in html.lower(),
        'captcha': 'captcha' in html.lower() or 'recaptcha' in html.lower(),
        'hcaptcha': 'hcaptcha' in html.lower(),
        'access_denied': 'access denied' in html.lower(),
        'forbidden': '>forbidden<' in html.lower(),
        'rate_limit': 'rate limit' in html.lower() or 'too many requests' in html.lower(),
        'bot_detected': 'bot detected' in html.lower() or 'automated' in html.lower(),
        'blocked': 'you have been blocked' in html.lower(),
    }
    return [name for name, detected in blocking_signs.items() if detected]


def sanitize_filename(name: str) -> str:
    """Create safe filename from site name."""
    return "".join(c if c.isalnum() or c in '-_' else '_' for c in name).lower()


def save_html(html: str, prefix: str, site_name: str) -> Path:
    """Save HTML to output directory."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    filename = OUTPUT_DIR / f"{prefix}_{sanitize_filename(site_name)}.html"
    filename.write_text(html, encoding='utf-8')
    return filename


def get_text_content(html: str) -> tuple[int, str | None]:
    """Parse HTML and return text length and preview."""
    try:
        tree = HTMLParser(html)
        body_text = tree.body.text() if tree.body else ""
        # Clean up whitespace
        body_text = ' '.join(body_text.split())
        preview = body_text[:200] + "..." if len(body_text) > 200 else body_text
        return len(body_text), preview
    except Exception:
        return 0, None


# ============================================================================
# CORE TEST FUNCTION
# ============================================================================

async def test_site(
    client: httpx.AsyncClient,
    site: dict[str, Any],
    semaphore: asyncio.Semaphore,
    index: int,
    total: int
) -> dict[str, Any]:
    """Test if a site is accessible with basic HTTPX."""

    async with semaphore:  # Limit concurrent requests
        site_name = site['name']
        print(f"\n[{index}/{total}] 🔍 Testing: {site_name}")
        print(f"    📍 {site['url']}")

        result = {
            'name': site_name,
            'url': site['url'],
            'notes': site['notes'],
            'accessible': False,
            'status_code': None,
            'has_content': False,
            'blocked': False,
            'blocked_by': [],
            'error': None,
            'size_bytes': 0,
            'text_length': 0,
            'response_time_ms': None,
            'saved_file': None
        }

        start_time = datetime.now()

        try:
            response = await client.get(site['url'], headers=HEADERS)

            elapsed = (datetime.now() - start_time).total_seconds() * 1000
            result['response_time_ms'] = round(elapsed)
            result['status_code'] = response.status_code
            result['size_bytes'] = len(response.content)

            if response.status_code == 200:
                html = response.text
                blocked_by = detect_blocking(html)

                if blocked_by:
                    result['blocked'] = True
                    result['blocked_by'] = blocked_by
                    print(f"    ❌ BLOCKED by: {', '.join(blocked_by)}")

                    filepath = save_html(html, "blocked", site_name)
                    result['saved_file'] = str(filepath)

                else:
                    # Check if we got actual content
                    check_func: Callable[[str], bool] = site['check']
                    text_length, preview = get_text_content(html)
                    result['text_length'] = text_length

                    if check_func(html):
                        result['accessible'] = True
                        result['has_content'] = True

                        status = "✅ SUCCESS"
                        if text_length < 500:
                            status += " (sparse content)"

                        print(f"    {status} - {result['size_bytes']:,}B, {text_length:,} chars, {result['response_time_ms']}ms")

                        filepath = save_html(html, "working", site_name)
                        result['saved_file'] = str(filepath)

                    else:
                        print(f"    ⚠️  Content check failed - {result['size_bytes']:,}B")
                        filepath = save_html(html, "no_content", site_name)
                        result['saved_file'] = str(filepath)

            elif response.status_code == 403:
                result['blocked'] = True
                result['blocked_by'] = ['http_403']
                print(f"    ❌ HTTP 403 Forbidden")

            elif response.status_code == 429:
                result['blocked'] = True
                result['blocked_by'] = ['rate_limit']
                print(f"    ❌ HTTP 429 Rate Limited")

            elif response.status_code == 503:
                result['blocked'] = True
                result['blocked_by'] = ['http_503']
                print(f"    ❌ HTTP 503 (likely Cloudflare)")

            else:
                print(f"    ❌ HTTP {response.status_code}")

        except httpx.TimeoutException:
            result['error'] = "Timeout"
            print(f"    ❌ TIMEOUT ({TIMEOUT_SECONDS}s)")

        except httpx.ConnectError as e:
            result['error'] = f"Connection failed: {str(e)[:50]}"
            print(f"    ❌ CONNECTION ERROR")

        except Exception as e:
            result['error'] = f"{type(e).__name__}: {str(e)[:50]}"
            print(f"    ❌ ERROR: {type(e).__name__}")

        return result


async def test_all_sites_parallel(sites: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Test all sites in parallel with controlled concurrency."""

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    async with httpx.AsyncClient(
        timeout=TIMEOUT_SECONDS,
        follow_redirects=True,
        http2=True,  # Enable HTTP/2 for better performance
        limits=httpx.Limits(
            max_keepalive_connections=MAX_CONCURRENT,
            max_connections=MAX_CONCURRENT * 2
        )
    ) as client:

        tasks = [
            test_site(client, site, semaphore, i + 1, len(sites))
            for i, site in enumerate(sites)
        ]

        # Run all tests concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle any unexpected exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append({
                    'name': sites[i]['name'],
                    'url': sites[i]['url'],
                    'accessible': False,
                    'error': f"Unexpected: {type(result).__name__}: {str(result)[:50]}",
                    'blocked': False
                })
            else:
                processed_results.append(result)

        return processed_results


# ============================================================================
# REPORTING FUNCTIONS
# ============================================================================

def categorize_results(results: list[dict[str, Any]]) -> dict[str, list[dict]]:
    """Categorize results by status."""
    return {
        'working': [r for r in results if r.get('accessible')],
        'blocked': [r for r in results if r.get('blocked')],
        'errored': [r for r in results if r.get('error') and not r.get('blocked')],
        'no_content': [
            r for r in results
            if not r.get('accessible') and not r.get('blocked') and not r.get('error')
        ]
    }


def print_summary(categories: dict[str, list[dict]]) -> None:
    """Print categorized results summary."""

    working = categories['working']
    blocked = categories['blocked']
    errored = categories['errored']
    no_content = categories['no_content']

    print(f"\n{'─'*60}")
    print(f"✅ WORKING ({len(working)})")
    print('─'*60)
    if working:
        for r in working:
            time_ms = r.get('response_time_ms', '?')
            print(f"   ✅ {r['name']}")
            print(f"      └─ {r['size_bytes']:,}B in {time_ms}ms (HTTPX works!)")
    else:
        print("   None 😞")

    print(f"\n{'─'*60}")
    print(f"❌ BLOCKED ({len(blocked)})")
    print('─'*60)
    if blocked:
        for r in blocked:
            blockers = ', '.join(r.get('blocked_by', ['unknown']))
            print(f"   ❌ {r['name']}")
            print(f"      └─ Blocked by: {blockers}")
    else:
        print("   None (great!)")

    print(f"\n{'─'*60}")
    print(f"⚠️  NO CONTENT ({len(no_content)})")
    print('─'*60)
    if no_content:
        for r in no_content:
            print(f"   ⚠️  {r['name']}")
            print(f"      └─ Check: {r.get('saved_file', 'N/A')}")
    else:
        print("   None")

    print(f"\n{'─'*60}")
    print(f"💥 ERRORS ({len(errored)})")
    print('─'*60)
    if errored:
        for r in errored:
            print(f"   💥 {r['name']}")
            print(f"      └─ {r.get('error', 'Unknown error')}")
    else:
        print("   None")


def print_recommendations(categories: dict[str, list[dict]]) -> None:
    """Print actionable recommendations."""

    working = categories['working']
    blocked = categories['blocked']

    print("\n" + "="*60)
    print("🎯 RECOMMENDATIONS")
    print("="*60)

    if working:
        print(f"\n✅ QUICK WINS: {len(working)} site(s) work with HTTPX!")
        print("\n   These can run in GitHub Actions without browser:")

        for r in working:
            adapter_name = r['name'].replace(' ', '').replace('-', '') + 'Adapter'
            print(f"\n   📦 {adapter_name}:")
            print(f"      URL: {r['url']}")
            print(f"      Strategy: primary_engine=BrowserEngine.HTTPX")

        print("\n   📋 Next steps:")
        print("      1. Create/update adapters for these sites")
        print("      2. Use FetchStrategy(primary_engine=BrowserEngine.HTTPX)")
        print("      3. Disable browser-only adapters in CI")
        print("      4. Deploy to GitHub Actions immediately!")

    if blocked:
        print(f"\n⚠️  NEEDS BROWSER: {len(blocked)} site(s) are blocking")
        print("\n   These require Camoufox or similar:")

        for r in blocked:
            print(f"   • {r['name']}: {', '.join(r.get('blocked_by', []))}")

        print("\n   Options:")
        print("      1. Use Camoufox with StealthMode.CAMOUFLAGE")
        print("      2. Use residential proxy service")
        print("      3. Try paid API (e.g., Racing API, TheOddsAPI)")
        print("      4. Run browser-based scraping locally only")

    if not working:
        print("\n🚨 CRITICAL: No sites accessible via HTTPX!")
        print("\n   Possible causes:")
        print("      1. All sites use bot protection")
        print("      2. Your IP may be flagged")
        print("      3. Network/proxy issues")
        print("\n   Try:")
        print("      1. Run from different network")
        print("      2. Use VPN or proxy")
        print("      3. Check saved HTML files for clues")


def print_performance_stats(results: list[dict[str, Any]], elapsed: float) -> None:
    """Print performance statistics."""

    successful = [r for r in results if r.get('response_time_ms')]

    print("\n" + "="*60)
    print("⚡ PERFORMANCE STATS")
    print("="*60)

    print(f"\n   Total time: {elapsed:.1f}s for {len(results)} sites")
    print(f"   Parallel speedup: ~{len(results) * TIMEOUT_SECONDS / max(elapsed, 1):.1f}x")

    if successful:
        times = [r['response_time_ms'] for r in successful]
        avg_time = sum(times) / len(times)
        print(f"\n   Response times:")
        print(f"      Fastest: {min(times)}ms")
        print(f"      Slowest: {max(times)}ms")
        print(f"      Average: {avg_time:.0f}ms")


# ============================================================================
# MAIN
# ============================================================================

async def main() -> int:
    print("\n" + "="*60)
    print("🚨 HTTPX SITE ACCESSIBILITY TEST (PARALLEL)")
    print("="*60)
    print(f"\n📊 Testing {len(SITES_TO_TEST)} sites with {MAX_CONCURRENT} concurrent connections")
    print(f"⏱️  Timeout: {TIMEOUT_SECONDS}s per site")
    print(f"📁 Output: {OUTPUT_DIR.absolute()}")
    print("\n" + "="*60)

    # Run parallel tests
    start_time = datetime.now()
    results = await test_all_sites_parallel(SITES_TO_TEST)
    elapsed = (datetime.now() - start_time).total_seconds()

    # Categorize and report
    categories = categorize_results(results)

    print("\n" + "="*60)
    print("📊 TEST RESULTS SUMMARY")
    print("="*60)

    print_summary(categories)
    print_performance_stats(results, elapsed)
    print_recommendations(categories)

    # Save results
    OUTPUT_DIR.mkdir(exist_ok=True)
    output_file = OUTPUT_DIR / 'httpx_test_results.json'

    # Remove lambda functions from results (not JSON serializable)
    clean_results = []
    for r in results:
        clean = {k: v for k, v in r.items() if not callable(v)}
        clean_results.append(clean)

    with open(output_file, 'w') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'config': {
                'timeout_seconds': TIMEOUT_SECONDS,
                'max_concurrent': MAX_CONCURRENT,
                'sites_tested': len(SITES_TO_TEST)
            },
            'elapsed_seconds': round(elapsed, 2),
            'results': clean_results,
            'summary': {
                'working': len(categories['working']),
                'blocked': len(categories['blocked']),
                'errored': len(categories['errored']),
                'no_content': len(categories['no_content'])
            }
        }, f, indent=2)

    print(f"\n💾 Results: {output_file}")
    print(f"💾 HTML files: {OUTPUT_DIR}/*.html")

    # Return status
    if categories['working']:
        print("\n" + "="*60)
        print("✅ SUCCESS - You have working sites!")
        print("="*60)
        return 0
    else:
        print("\n" + "="*60)
        print("❌ No HTTPX-accessible sites found")
        print("="*60)
        return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
