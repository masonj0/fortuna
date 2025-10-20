# tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from python_service.api import app
import httpx
from unittest.mock import Mock
import os

@pytest.fixture(scope="module")
def client():
    """A TestClient instance for testing the FastAPI app."""
    with TestClient(app) as c:
        yield c

@pytest.fixture
def mock_httpx_client():
    """Mocks the httpx.AsyncClient for testing adapters."""
    return Mock(spec=httpx.AsyncClient)

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """
    Creates a dummy .env file in the project root for the test suite and
    ensures it's loaded.
    """
    env_content = 'API_KEY="test_api_key"'
    env_path = ".env"
    with open(env_path, "w") as f:
        f.write(env_content)

    # Force reload of settings to pick up the new .env file
    from python_service.config import get_settings
    get_settings.cache_clear()

    yield

    os.remove(env_path)
    get_settings.cache_clear()
