from fastapi.testclient import TestClient
from python_service.api import app

client = TestClient(app)

def test_health_check():
    """Tests the unauthenticated /health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
