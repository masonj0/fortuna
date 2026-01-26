"""
Canary check script for early detection of upstream changes.
"""

import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from python_service.browser.canary import CanaryMonitor
from python_service.observability import configure_logging, get_logger

# Import your adapters
from web_service.backend.adapters.twinspires_adapter import TwinSpiresAdapter
# Add other adapters as needed

configure_logging(level="INFO", json_output=True)
logger = get_logger(__name__)


async def main():
    """Run canary checks."""
    logger.info("Starting canary check")

    # Initialize adapters
    adapters = [
        TwinSpiresAdapter(),
        # Add other adapters
    ]

    # Initialize canary monitor
    canary = CanaryMonitor(
        check_interval=timedelta(minutes=30),
        sample_size=2,
    )

    try:
        # Run checks
        results = await canary.run_canary_check(adapters)

        # Get health summary
        health = canary.get_health_summary()

        # Output results
        output = {
            "status": health["status"],
            "success_rate": health["success_rate"],
            "timestamp": datetime.utcnow().isoformat(),
            "results": [
                {
                    "adapter": r.adapter,
                    "track": r.track,
                    "success": r.success,
                    "race_count": r.race_count,
                    "latency_ms": r.latency_ms,
                    "error": r.error,
                }
                for r in results
            ]
        }

        # Save result
        with open("canary_result.json", "w") as f:
            json.dump(output, f, indent=2)

        logger.info(f"Canary check complete", **health)

        # Exit with appropriate code
        if health["status"] == "unhealthy":
            sys.exit(1)

    finally:
        # Cleanup adapters
        for adapter in adapters:
            if hasattr(adapter, 'cleanup'):
                await adapter.cleanup()


from datetime import timedelta

if __name__ == "__main__":
    asyncio.run(main())
