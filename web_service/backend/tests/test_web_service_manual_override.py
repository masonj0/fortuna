# python_service/tests/test_manual_override.py
import pytest

from manual_override_manager import ManualOverrideManager


@pytest.fixture
def manager():
    # The manager is now in-memory and doesn't need a path
    return ManualOverrideManager()


def test_register_and_retrieve(manager):
    adapter = "TestAdapter"
    url = "https://example.com/blocked"

    request_id = manager.register_failure(
        adapter_name=adapter,
        url=url,
    )

    pending = manager.get_pending_requests()
    assert len(pending) == 1
    assert pending[0].request_id == request_id
    assert pending[0].adapter_name == adapter
    assert pending[0].url == url


def test_submit_manual_data(manager):
    adapter = "TestAdapter"
    url = "https://example.com/blocked"
    content = "<html>Manual content</html>"
    content_type = "text/html"

    request_id = manager.register_failure(
        adapter_name=adapter,
        url=url,
    )

    success = manager.submit_manual_data(
        request_id=request_id,
        raw_content=content,
        content_type=content_type,
    )

    assert success

    # Verify that the data can be retrieved correctly
    retrieved_data = manager.get_manual_data(adapter_name=adapter, url=url)
    assert retrieved_data is not None
    retrieved_content, retrieved_type = retrieved_data
    assert retrieved_content == content
    assert retrieved_type == content_type

    # Verify that data is consumed after retrieval
    assert manager.get_manual_data(adapter_name=adapter, url=url) is None
