#!/usr/bin/env python3
"""Lightweight canary check for data sources."""

import asyncio
import json
import sys
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict
import httpx

sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass
class CanaryResult:
    source: str
    success: bool
    latency_ms: float
    message: str
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()


async def check_browser_basic() -> CanaryResult:
    """Basic browser connectivity check."""
    start = time.perf_counter()

    try:
        from scrapling.fetchers import AsyncStealthySession

        async with AsyncStealthySession(headless=True) as session:
            response = await session.fetch('https://httpbin.org/status/200')

        latency = (time.perf_counter() - start) * 1000

        return CanaryResult(
            source="httpbin",
            success=response.status == 200,
            latency_ms=latency,
            message="OK" if response.status == 200 else f"Status: {response.status}"
        )
    except Exception as e:
        return CanaryResult(
            source="httpbin",
            success=False,
            latency_ms=(time.perf_counter() - start) * 1000,
            message=str(e)
        )


async def check_twinspires() -> CanaryResult:
    """Check TwinSpires accessibility."""
    start = time.perf_counter()

    try:
        from scrapling.fetchers import AsyncStealthySession

        async with AsyncStealthySession(headless=True) as session:
            response = await session.fetch(
                'https://www.twinspires.com/bet/todays-races/time',
                timeout=30000
            )

        latency = (time.perf_counter() - start) * 1000

        # Check if we got blocked
        text = response.text.lower()
        if 'captcha' in text or 'access denied' in text:
            return CanaryResult(
                source="TwinSpires",
                success=False,
                latency_ms=latency,
                message="Blocked by anti-bot"
            )

        # Check for race content
        has_races = 'race' in text or 'track' in text

        return CanaryResult(
            source="TwinSpires",
            success=response.status == 200 and has_races,
            latency_ms=latency,
            message="OK" if has_races else f"No race content found (Status: {response.status})"
        )

    except Exception as e:
        return CanaryResult(
            source="TwinSpires",
            success=False,
            latency_ms=(time.perf_counter() - start) * 1000,
            message=str(e)
        )


async def check_http_source(name: str, url: str, expected_keywords: list[str]) -> CanaryResult:
    """Check a source via simple HTTP."""
    start = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            response = await client.get(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )

        latency = (time.perf_counter() - start) * 1000
        text = response.text.lower()

        if response.status_code != 200:
            return CanaryResult(name, False, latency, f"HTTP {response.status_code}")

        found = [kw for kw in expected_keywords if kw.lower() in text]
        success = len(found) > 0

        return CanaryResult(
            source=name,
            success=success,
            latency_ms=latency,
            message="OK" if success else f"Content check failed (Found keywords: {found})"
        )
    except Exception as e:
        return CanaryResult(name, False, (time.perf_counter() - start) * 1000, str(e))


async def main():
    print("=" * 60)
    print("CANARY HEALTH CHECK")
    print(f"Time: {datetime.utcnow().isoformat()}")
    print("=" * 60)

    results = []

    # Run checks
    print("\n→ Running Browser-based checks...")
    results.append(await check_browser_basic())
    results.append(await check_twinspires())

    print("\n→ Running HTTP-based checks...")
    http_checks = [
        ("Racing.com", "https://www.racing.com/", ["racing", "horse"]),
        ("TAB.com.au", "https://www.tab.com.au/racing", ["racing", "odds"]),
        ("Racenet", "https://www.racenet.com.au/", ["racing", "form"]),
        ("AtTheRaces", "https://www.attheraces.com/", ["racecards", "at the races"]),
        ("SportingLife", "https://www.sportinglife.com/horse-racing", ["racecards", "sporting life"])
    ]

    for name, url, kws in http_checks:
        results.append(await check_http_source(name, url, kws))

    for result in results:
        status = "✅" if result.success else "❌"
        print(f"  {status} {result.source}: {result.message} ({result.latency_ms:.0f}ms)")

    # Calculate summary
    total = len(results)
    passed = sum(1 for r in results if r.success)
    success_rate = passed / total if total > 0 else 0

    if success_rate >= 0.8:
        status = "healthy"
    elif success_rate >= 0.5:
        status = "degraded"
    else:
        status = "unhealthy"

    summary = {
        "status": status,
        "success_rate": f"{success_rate:.0%}",
        "total_checks": total,
        "passed": passed,
        "failed": total - passed,
        "timestamp": datetime.utcnow().isoformat(),
        "results": [asdict(r) for r in results]
    }

    print("\n" + "=" * 60)
    print(f"Status: {status.upper()}")
    print(f"Success Rate: {success_rate:.0%} ({passed}/{total})")
    print("=" * 60)

    with open("canary_result.json", "w") as f:
        json.dump(summary, f, indent=2)

    return 0 if status != "unhealthy" else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
