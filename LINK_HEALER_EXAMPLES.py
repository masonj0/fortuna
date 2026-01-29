#!/usr/bin/env python3
"""
Link Healer Usage Examples

This file demonstrates how to integrate Link Healer into various parts
of the Fortuna Faucet architecture.
"""

import asyncio
import json
from datetime import datetime
from python_service.utilities.link_healer import heal_url, get_healing_report, LinkHealer


# --- Example 1: Integrating into a Base Adapter ---

class MockBaseAdapter:
    """Mock base adapter to show integration pattern."""

    async def make_request(self, url):
        print(f"Requesting: {url}")
        # Simulate a 404 for a specific bad URL
        if "broken-link" in url:
            return type('obj', (object,), {'status_code': 404})
        return type('obj', (object,), {'status_code': 200, 'text': 'Success'})

    async def get_race_data(self, url, venue=None, date=None):
        """Fetch race data with automatic 404 healing."""
        response = await self.make_request(url)

        if response.status_code == 404:
            print(f"⚠️ 404 detected for {url}. Attempting healing...")

            # Provide context to help the healer
            context = {
                "venue": venue,
                "date": date or datetime.now(),
                "adapter_name": self.__class__.__name__
            }

            # Try to heal the URL
            healed_url = await heal_url(self.__class__.__name__, url, context)

            if healed_url:
                print(f"✅ Successfully healed! Retrying with: {healed_url}")
                response = await self.make_request(healed_url)
            else:
                print(f"❌ Healing failed for {url}")

        return response


# --- Example 2: Bulk Healing in an Engine ---

async def engine_example():
    """Example of how an OddsEngine might use Link Healer."""
    urls_to_fetch = [
        ("EquibaseAdapter", "https://equibase.com/broken-link/2025-01-29"),
        ("BrisnetAdapter", "https://brisnet.com/races/today/bad-venue"),
    ]

    for adapter_name, url in urls_to_fetch:
        print(f"\n--- Processing {adapter_name} ---")
        context = {"venue": "Aqueduct", "date": datetime.now()}

        # In a real engine, this would be part of the request loop
        healed = await heal_url(adapter_name, url, context)

        if healed:
            print(f"Engine recovered URL: {healed}")
        else:
            print(f"Engine could not recover URL.")


# --- Example 3: Standalone Usage with Context Manager ---

async def standalone_example():
    """Using LinkHealer as an async context manager for clean session management."""
    broken_url = "https://www.racingpost.com/racing/cards/broken"

    async with LinkHealer(adapter_name="RacingPostAdapter") as healer:
        healed_url = await healer.heal_url(broken_url, {"venue": "Ascot"})
        if healed_url:
            print(f"Healed: {healed_url}")

        # Get report for just this healer instance
        print(json.dumps(healer.get_healing_report(), indent=2))


# --- Main Execution for Demonstration ---

async def main():
    try:
        print("=== Link Healer Examples ===\n")

        # 1. Adapter integration demo
        adapter = MockBaseAdapter()
        await adapter.get_race_data("https://equibase.com/broken-link/2025-01-29", venue="GP")

        # 2. Engine demo
        await engine_example()

        # 3. Final global report
        print("\n=== Final Global Healing Report ===")
        print(json.dumps(get_healing_report(), indent=2))
    finally:
        # Clean up global pool
        from python_service.utilities.link_healer import _pool
        await _pool.close()


if __name__ == "__main__":
    asyncio.run(main())
