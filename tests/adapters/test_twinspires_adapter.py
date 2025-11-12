# tests/adapters/test_twinspires_adapter.py
import pytest
from python_service.adapters.twinspires_adapter import TwinSpiresAdapter
from python_service.models import Race

# A mock settings object to satisfy the adapter's config dependency
class MockSettings:
    pass

@pytest.fixture
def adapter():
    return TwinSpiresAdapter(config=MockSettings())

@pytest.mark.asyncio
async def test_get_races_from_fixture(adapter):
    """
    Test that the adapter can correctly parse a local HTML fixture.
    This test validates the end-to-end parsing logic, including runner data,
    using the offline implementation.
    """
    # Call the method under test, which is now wired to read from the fixture
    races = await adapter._get_races_async(date="2025-11-12")

    # Assertions
    assert isinstance(races, list)
    assert len(races) == 1

    # Check the race for correct parsing
    race = races[0]
    assert race.venue == "Churchill Downs"
    assert race.race_number == 5

    # Check that runners were parsed correctly
    assert len(race.runners) == 4

    # Verify a specific runner's details
    runner_1 = next((r for r in race.runners if r.number == 1), None)
    assert runner_1 is not None
    assert runner_1.name == "Braveheart"
    assert not runner_1.scratched
    assert runner_1.odds["TwinSpires"].win == 3.5

    # Verify a scratched runner
    runner_3 = next((r for r in race.runners if r.number == 3), None)
    assert runner_3 is not None
    assert runner_3.name == "Steady Eddy"
    assert runner_3.scratched
    assert not runner_3.odds
