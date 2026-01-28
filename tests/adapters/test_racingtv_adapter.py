# tests/adapters/test_racingtv_adapter.py
import pytest

from python_service.adapters import RacingTVAdapter


@pytest.mark.asyncio
async def test_racingtv_adapter_is_stub():
    """
    Tests that the RacingTVAdapter is a non-functional stub that returns no data.
    """
    # ARRANGE
    adapter = RacingTVAdapter()

    # ACT
    races = await adapter.get_races("2025-10-27")

    # ASSERT
    assert races == []
