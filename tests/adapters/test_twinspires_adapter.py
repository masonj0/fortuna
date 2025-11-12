# tests/adapters/test_twinspires_adapter.py
import pytest
import respx
import httpx
from httpx import Response
from python_service.adapters.twinspires_adapter import TwinSpiresAdapter
from python_service.models import Race

# A mock settings object to satisfy the adapter's config dependency
class MockSettings:
    pass

@pytest.fixture
def adapter():
    return TwinSpiresAdapter(config=MockSettings())

@pytest.mark.asyncio
@respx.mock
async def test_get_races_with_mock_data(adapter):
    """
    Test that the adapter can correctly parse a mock API response.
    This test uses a mocked API response to avoid live calls and ensure reproducibility.
    """
    mock_track_data = [
        {"trackId":"cp1","trackName":"Central Park","raceType":"Greyhound"},
        {"trackId":"fl","trackName":"Finger Lakes","raceType":"Thoroughbred"},
        {"trackId":"mr","trackName":"Monticello Raceway","raceType":"Harness"},
    ]

    mock_race_card_data = [
        {"raceNumber": 1, "postTime": "2025-11-12T10:36:17-04:00", "distance": "303 Y"},
        {"raceNumber": 2, "postTime": "2025-11-12T10:54:15-04:00", "distance": "537 Y"},
    ]

    # Mock the initial 'todays-tracks' call
    respx.get(adapter.base_url + "/adw/todays-tracks?affid=0").mock(
        return_value=Response(200, json=mock_track_data)
    )

    # Mock the race card calls for each track
    for track in mock_track_data:
        track_id = track.get("trackId")
        race_type = track.get("raceType")
        respx.get(f"{adapter.base_url}/adw/todays-tracks/{track_id}/{race_type}/races?affid=0").mock(
            return_value=Response(200, json=mock_race_card_data)
        )

    # The adapter needs a real http_client to work with the mock
    async with httpx.AsyncClient() as client:
        adapter.http_client = client
        # Call the method under test
        races = await adapter._get_races_async(date="2025-11-12")

    # Assertions
    assert isinstance(races, list)
    assert len(races) == 6 # 3 tracks * 2 races each

    # Check the first race for correct parsing
    first_race = races[0]
    assert first_race.venue == "Central Park"
    assert first_race.race_number == 1
    assert first_race.discipline == "Greyhound"
    assert first_race.runners == [] # Expected to be empty for now
