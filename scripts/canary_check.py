#!/usr/bin/env python3
# scripts/canary_check.py
"""
Lightweight canary check for upstream data sources.
Runs more frequently to detect issues early.
"""

import asyncio
import json
import sys
import os
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict

# Ensure imports work
sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass
class CanaryResult:
    """Result of a single canary check."""
    source: str
    success: bool
    latency_ms: float
    race_count: int
    error: Optional[str] = None
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.utcnow().isoformat()


class SimpleCanaryChecker:
    """
    Simple canary checker that tests each data source.
    """

    def __init__(self):
        self.results: List[CanaryResult] = []

    async def check_twinspires(self) -> CanaryResult:
        """Check TwinSpires availability."""
        start = time.perf_counter()

        try:
            from python_service.adapters.twinspires_adapter import TwinSpiresAdapter

            async with TwinSpiresAdapter() as adapter:
                today = datetime.utcnow().strftime("%Y-%m-%d")
                races = await asyncio.wait_for(
                    adapter.get_races(today),
                    timeout=60
                )

                latency = (time.perf_counter() - start) * 1000
                race_count = len(races) if races else 0

                return CanaryResult(
                    source="TwinSpires",
                    success=True,
                    latency_ms=latency,
                    race_count=race_count,
                )

        except asyncio.TimeoutError:
            return CanaryResult(
                source="TwinSpires",
                success=False,
                latency_ms=(time.perf_counter() - start) * 1000,
                race_count=0,
                error="Timeout after 60s"
            )
        except Exception as e:
            return CanaryResult(
                source="TwinSpires",
                success=False,
                latency_ms=(time.perf_counter() - start) * 1000,
                race_count=0,
                error=str(e)
            )

    async def check_httpbin(self) -> CanaryResult:
        """Basic connectivity check via httpbin."""
        start = time.perf_counter()

        try:
            from scrapling.fetchers import StealthyFetcher

            fetcher = StealthyFetcher(headless=True)
            response = await asyncio.wait_for(
                asyncio.to_thread(fetcher.fetch, 'https://httpbin.org/status/200'),
                timeout=30
            )

            latency = (time.perf_counter() - start) * 1000

            return CanaryResult(
                source="httpbin",
                success=response.status == 200,
                latency_ms=latency,
                race_count=0,
                error=None if response.status == 200 else f"Status: {response.status}"
            )

        except Exception as e:
            return CanaryResult(
                source="httpbin",
                success=False,
                latency_ms=(time.perf_counter() - start) * 1000,
                race_count=0,
                error=str(e)
            )

    async def run_all_checks(self) -> Dict[str, Any]:
        """Run all canary checks."""
        print("=" * 60)
        print("CANARY HEALTH CHECK")
        print(f"Time: {datetime.utcnow().isoformat()}")
        print("=" * 60)

        # Run checks
        checks = [
            ("httpbin", self.check_httpbin),
            ("twinspires", self.check_twinspires),
        ]

        for name, check_func in checks:
            print(f"\n→ Checking {name}...")
            try:
                result = await check_func()
                self.results.append(result)

                if result.success:
                    print(f"  ✅ {name}: OK ({result.latency_ms:.0f}ms, {result.race_count} races)")
                else:
                    print(f"  ❌ {name}: FAILED - {result.error}")
            except Exception as e:
                print(f"  ❌ {name}: Exception - {e}")
                self.results.append(CanaryResult(
                    source=name,
                    success=False,
                    latency_ms=0,
                    race_count=0,
                    error=str(e)
                ))

        # Calculate summary
        total = len(self.results)
        passed = sum(1 for r in self.results if r.success)
        success_rate = passed / total if total > 0 else 0

        # Determine status
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
            "results": [asdict(r) for r in self.results]
        }

        print("\n" + "=" * 60)
        print("SUMMARY")
        print("=" * 60)
        print(f"Status: {status.upper()}")
        print(f"Success Rate: {success_rate:.0%}")
        print(f"Passed: {passed}/{total}")

        return summary


async def main():
    """Run canary checks."""
    checker = SimpleCanaryChecker()

    try:
        summary = await checker.run_all_checks()

        # Save results
        with open("canary_result.json", "w") as f:
            json.dump(summary, f, indent=2)

        print(f"\nResults saved to canary_result.json")

        # Exit code based on status
        if summary["status"] == "unhealthy":
            return 1
        return 0

    except Exception as e:
        print(f"\n❌ Canary check failed: {e}")

        # Save error result
        error_result = {
            "status": "error",
            "success_rate": "0%",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }
        with open("canary_result.json", "w") as f:
            json.dump(error_result, f, indent=2)

        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
