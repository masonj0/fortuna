# tests/test_manual_override.py
import pytest
from fastapi.testclient import TestClient

from python_service.api import app
from python_service.api import get_settings
from python_service.manual_override_manager import ManualOverrideManager
from tests.conftest import get_test_settings

# Override settings for tests
app.dependency_overrides[get_settings] = get_test_settings
_settings = get_test_settings()
API_KEY = getattr(_settings, "API_KEY", "test-override-key-123")


@pytest.fixture
def manager() -> ManualOverrideManager:
    """Provides a clean ManualOverrideManager instance for each test."""
    return ManualOverrideManager()


def test_register_failure(manager: ManualOverrideManager):
    adapter_name = "TestAdapter"
    url = "http://test.com/races"
    request_id = manager.register_failure(adapter_name, url)
    assert request_id is not None
    pending = manager.get_pending_requests()
    assert len(pending) == 1
    assert pending[0].request_id == request_id
    assert pending[0].adapter_name == adapter_name
    assert pending[0].url == url


def test_submit_manual_data(manager: ManualOverrideManager):
    request_id = manager.register_failure("TestAdapter", "http://test.com/races")
    success = manager.submit_manual_data(request_id, "<html></html>", "html")
    assert success
    assert len(manager.get_pending_requests()) == 0
    data = manager.get_manual_data("TestAdapter", "http://test.com/races")
    assert data is not None
    assert data[0] == "<html></html>"
    assert data[1] == "html"


def test_skip_request(manager: ManualOverrideManager):
    request_id = manager.register_failure("TestAdapter", "http://test.com/races")
    success = manager.skip_request(request_id)
    assert success
    assert len(manager.get_pending_requests()) == 0
    data = manager.get_manual_data("TestAdapter", "http://test.com/races")
    assert data is None


@pytest.mark.asyncio
async def test_get_pending_overrides_endpoint(client):
    # ARRANGE
    # Access the manager *after* the TestClient has run the lifespan startup
    manager = client.app.state.manual_override_manager
    manager.clear_old_requests(max_age_hours=-1)  # Ensure a clean state by clearing all
    manager.register_failure("EndpointAdapter", "http://endpoint.com/data")

    # ACT
    response = await client.get("/api/manual-overrides/pending", headers={"X-API-Key": API_KEY})
    assert response.status_code == 200
    data = response.json()
    assert "pending_requests" in data
    assert len(data["pending_requests"]) > 0
    assert data["pending_requests"][0]["adapter_name"] == "EndpointAdapter"


@pytest.mark.asyncio
async def test_submit_manual_data_endpoint(client):
    # ARRANGE
    manager = client.app.state.manual_override_manager
    manager.clear_old_requests(max_age_hours=-1)
    request_id = manager.register_failure("SubmitAdapter", "http://submit.com/data")
    submission = {
        "request_id": request_id,
        "content": "<h1>Hello</h1>",
        "content_type": "html",
    }
    response = await client.post(
        "/api/manual-overrides/submit",
        json=submission,
        headers={"X-API-Key": API_KEY},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    data = manager.get_manual_data("SubmitAdapter", "http://submit.com/data")
    assert data is not None
    assert data[0] == "<h1>Hello</h1>"


@pytest.mark.asyncio
async def test_skip_manual_override_endpoint(client):
    # ARRANGE
    manager = client.app.state.manual_override_manager
    manager.clear_old_requests(max_age_hours=-1)
    request_id = manager.register_failure("SkipAdapter", "http://skip.com/data")
    response = await client.post(f"/api/manual-overrides/skip/{request_id}", headers={"X-API-Key": API_KEY})
    assert response.status_code == 200
    assert response.json()["status"] == "success"
    # Verify the request is no longer pending
    pending = manager.get_pending_requests()
    assert not any(p.request_id == request_id for p in pending)
