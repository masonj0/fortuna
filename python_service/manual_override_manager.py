# python_service/manual_override_manager.py
import json
import structlog
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path
from pydantic import BaseModel

log = structlog.get_logger(__name__)

class ManualOverrideRequest(BaseModel):
    """Represents a request for manual data entry"""
    request_id: str
    adapter_name: str
    url: str
    date: str
    timestamp: datetime
    error_message: str
    status: str = "pending"  # pending, completed, skipped

class ManualOverrideResponse(BaseModel):
    """Container for manually provided data"""
    request_id: str
    raw_content: str
    content_type: str  # 'html', 'json', 'text'
    provided_at: datetime

class ManualOverrideManager:
    """
    Manages the queue of failed fetches requiring manual intervention
    and processes manually-provided data through adapter parsers.
    """

    def __init__(self, storage_path: str = "data/manual_overrides"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.pending_requests: Dict[str, ManualOverrideRequest] = {}
        self.completed_responses: Dict[str, ManualOverrideResponse] = {}
        self._load_state()

    def register_failed_fetch(
        self,
        adapter_name: str,
        url: str,
        date: str,
        error: Exception
    ) -> str:
        """
        Register a failed fetch that requires manual intervention.
        Returns a unique request_id for tracking.
        """
        request_id = f"{adapter_name}_{date}_{hash(url) % 10000}"

        request = ManualOverrideRequest(
            request_id=request_id,
            adapter_name=adapter_name,
            url=url,
            date=date,
            timestamp=datetime.now(),
            error_message=str(error),
            status="pending"
        )

        self.pending_requests[request_id] = request
        self._save_state()

        log.info(
            "Registered manual override request",
            request_id=request_id,
            adapter=adapter_name,
            url=url
        )

        return request_id

    def submit_manual_data(
        self,
        request_id: str,
        raw_content: str,
        content_type: str = "html"
    ) -> bool:
        """
        Submit manually-provided content for a pending request.
        Returns True if successful, False if request not found.
        """
        if request_id not in self.pending_requests:
            log.warning("Manual override request not found", request_id=request_id)
            return False

        response = ManualOverrideResponse(
            request_id=request_id,
            raw_content=raw_content,
            content_type=content_type,
            provided_at=datetime.now()
        )

        self.completed_responses[request_id] = response
        self.pending_requests[request_id].status = "completed"
        self._save_state()

        log.info("Manual data submitted", request_id=request_id)
        return True

    def skip_request(self, request_id: str) -> bool:
        """Mark a request as skipped (user chose not to provide data)"""
        if request_id not in self.pending_requests:
            return False

        self.pending_requests[request_id].status = "skipped"
        self._save_state()
        return True

    def get_pending_requests(self) -> List[ManualOverrideRequest]:
        """Get all pending manual override requests"""
        return [
            req for req in self.pending_requests.values()
            if req.status == "pending"
        ]

    def get_completed_data(self, request_id: str) -> Optional[str]:
        """Retrieve the manually-provided data for a request"""
        response = self.completed_responses.get(request_id)
        return response.raw_content if response else None

    def clear_old_requests(self, max_age_hours: int = 24):
        """Remove requests older than max_age_hours"""
        cutoff = datetime.now().timestamp() - (max_age_hours * 3600)

        to_remove = [
            rid for rid, req in self.pending_requests.items()
            if req.timestamp.timestamp() < cutoff
        ]

        for rid in to_remove:
            del self.pending_requests[rid]
            if rid in self.completed_responses:
                del self.completed_responses[rid]

        if to_remove:
            self._save_state()
            log.info("Cleared old manual override requests", count=len(to_remove))

    def _save_state(self):
        """Persist state to disk"""
        state = {
            "pending": {k: v.model_dump() for k, v in self.pending_requests.items()},
            "completed": {k: v.model_dump() for k, v in self.completed_responses.items()}
        }

        with open(self.storage_path / "state.json", "w") as f:
            json.dump(state, f, indent=2, default=str)

    def _load_state(self):
        """Load state from disk"""
        state_file = self.storage_path / "state.json"
        if not state_file.exists():
            return

        try:
            with open(state_file, "r") as f:
                state = json.load(f)

            self.pending_requests = {
                k: ManualOverrideRequest(**v)
                for k, v in state.get("pending", {}).items()
            }
            self.completed_responses = {
                k: ManualOverrideResponse(**v)
                for k, v in state.get("completed", {}).items()
            }

            log.info("Loaded manual override state from disk")
        except Exception as e:
            log.error("Failed to load manual override state", error=str(e))
