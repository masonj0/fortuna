# web_service/backend/adapter_manager.py
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Protocol

class AdapterHealth(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILING = "failing"
    DISABLED = "disabled"

@dataclass
class AdapterStatus:
    name: str
    health: AdapterHealth
    success_rate_24h: float
    last_success: datetime | None
    consecutive_failures: int
    avg_response_time_ms: float
    last_error: str | None

    def should_use(self) -> bool:
        """Determine if adapter should be tried."""
        if self.health == AdapterHealth.DISABLED:
            return False
        if self.consecutive_failures > 5:
            return False
        if self.success_rate_24h < 0.2:  # Less than 20% success
            return False
        return True

    def get_priority(self) -> int:
        """Get adapter priority (lower = better)."""
        if self.health == AdapterHealth.HEALTHY:
            return 1
        if self.health == AdapterHealth.DEGRADED:
            return 2
        return 3

class AdapterHealthMonitor:
    """Tracks adapter health and makes routing decisions."""

    def __init__(self):
        self.statuses: dict[str, AdapterStatus] = {}
        self.health_check_interval = timedelta(minutes=5)

    async def update_adapter_status(self, adapter_name: str, success: bool,
                                   latency_ms: float, error: str | None = None):
        """Update adapter status after each attempt."""
        status = self.statuses.get(adapter_name)
        if not status:
            status = AdapterStatus(
                name=adapter_name,
                health=AdapterHealth.HEALTHY,
                success_rate_24h=1.0,
                last_success=None,
                consecutive_failures=0,
                avg_response_time_ms=0,
                last_error=None
            )
            self.statuses[adapter_name] = status

        if success:
            status.consecutive_failures = 0
            status.last_success = datetime.utcnow()
            status.last_error = None
        else:
            status.consecutive_failures += 1
            status.last_error = error

        # Update health based on consecutive failures
        if status.consecutive_failures >= 5:
            status.health = AdapterHealth.FAILING
        elif status.consecutive_failures >= 2:
            status.health = AdapterHealth.DEGRADED
        elif status.consecutive_failures == 0:
            status.health = AdapterHealth.HEALTHY

    def get_ordered_adapters(self, adapter_list: list[str]) -> list[str]:
        """Return adapters ordered by health/priority."""
        return sorted(
            [a for a in adapter_list if self.statuses.get(a, None) and
             self.statuses[a].should_use()],
            key=lambda a: self.statuses[a].get_priority()
        )
