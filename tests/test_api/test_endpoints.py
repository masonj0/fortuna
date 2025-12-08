import pytest
from fastapi.testclient import TestClient

from python_service.api import app

client = TestClient(app)


@pytest.mark.asyncio
async def test_health_check(client):
    """Tests the unauthenticated /health endpoint."""
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"
