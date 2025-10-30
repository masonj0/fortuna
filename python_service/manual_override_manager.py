# File: python_service/manual_override_manager.py (NEW FILE)

from pydantic import BaseModel


class ManualOverrideSubmissionModel(BaseModel):
    request_id: str
    source_name: str


class ManualOverrideManager:
    """Placeholder for unimplemented Manual Override Management."""

    def get_override(self, source_name: str) -> None:
        return None

    def get_pending_requests(self) -> list:
        return []

    def submit_manual_data(self, request_id, raw_content, content_type) -> bool:
        return False

    def skip_request(self, request_id) -> bool:
        return True

    def clear_old_requests(self, max_age_hours: int = 24) -> None:
        pass
