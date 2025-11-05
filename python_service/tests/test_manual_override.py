# python_service/tests/test_manual_override.py
import pytest

from python_service.manual_override_manager import ManualOverrideManager


@pytest.fixture
def manager(tmp_path):
    return ManualOverrideManager(storage_path=str(tmp_path))


def test_register_and_retrieve(manager):
    request_id = manager.register_failed_fetch(
        adapter_name="TestAdapter",
        url="https://example.com/blocked",
        date="2025-01-15",
        error=Exception("403 Forbidden"),
    )

    pending = manager.get_pending_requests()
    assert len(pending) == 1
    assert pending[0].request_id == request_id


def test_submit_manual_data(manager):
    request_id = manager.register_failed_fetch(
        adapter_name="TestAdapter",
        url="https://example.com/blocked",
        date="2025-01-15",
        error=Exception("403 Forbidden"),
    )

    success = manager.submit_manual_data(
        request_id=request_id,
        raw_content="<html>Manual content</html>",
        content_type="html",
    )

    assert success
    assert manager.get_completed_data(request_id) == "<html>Manual content</html>"
