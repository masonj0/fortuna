# python_service/manual_override_manager.py
import hashlib
from datetime import datetime
from datetime import timedelta
from typing import Dict
from typing import List
from typing import Optional
from typing import Tuple

from pydantic import BaseModel
from pydantic import Field


class ManualOverrideRequest(BaseModel):
    request_id: str
    adapter_name: str
    url: str
    timestamp: datetime = Field(default_factory=datetime.now)
    status: str = "pending"  # pending, submitted, skipped


class ManualOverrideManager:
    def __init__(self):
        self._requests: Dict[str, ManualOverrideRequest] = {}
        self._data: Dict[
            str, Tuple[str, str]
        ] = {}  # request_id -> (content, content_type)

    def _generate_id(self, adapter_name: str, url: str) -> str:
        """Generates a consistent ID for a given adapter and URL."""
        return hashlib.sha256(f"{adapter_name}:{url}".encode()).hexdigest()[:16]

    def register_failure(self, adapter_name: str, url: str) -> str:
        """
        Registers a failed fetch attempt and returns a unique request ID.
        If a pending request for this exact resource already exists, it returns the existing ID.
        """
        request_id = self._generate_id(adapter_name, url)
        if (
            request_id not in self._requests
            or self._requests[request_id].status != "pending"
        ):
            request = ManualOverrideRequest(
                request_id=request_id, adapter_name=adapter_name, url=url
            )
            self._requests[request_id] = request
        return request_id

    def submit_manual_data(
        self, request_id: str, raw_content: str, content_type: str
    ) -> bool:
        """Submits manual data for a pending request."""
        if (
            request_id in self._requests
            and self._requests[request_id].status == "pending"
        ):
            self._data[request_id] = (raw_content, content_type)
            self._requests[request_id].status = "submitted"
            return True
        return False

    def skip_request(self, request_id: str) -> bool:
        """Marks a pending request as skipped."""
        if (
            request_id in self._requests
            and self._requests[request_id].status == "pending"
        ):
            self._requests[request_id].status = "skipped"
            return True
        return False

    def get_pending_requests(self) -> List[ManualOverrideRequest]:
        """Returns a list of all requests that are currently pending."""
        return [req for req in self._requests.values() if req.status == "pending"]

    def get_manual_data(self, adapter_name: str, url: str) -> Optional[Tuple[str, str]]:
        """
        Retrieves submitted manual data for a given adapter and URL, if it exists.
        Once retrieved, the data is consumed and will not be returned again.
        """
        request_id = self._generate_id(adapter_name, url)
        if request_id in self._data:
            # Data is single-use; remove it after retrieval.
            return self._data.pop(request_id)
        return None

    def clear_old_requests(self, max_age_hours: int = 24):
        """Removes requests and associated data older than a specified age."""
        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        old_request_ids = [
            req_id for req_id, req in self._requests.items() if req.timestamp < cutoff
        ]
        for req_id in old_request_ids:
            self._requests.pop(req_id, None)
            self._data.pop(req_id, None)
