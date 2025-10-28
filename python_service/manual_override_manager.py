# python_service/manual_override_manager.py
from typing import Dict, Optional

class ManualOverrideManager:
    """
    A singleton manager to handle in-memory storage of manual override data for adapters.
    This allows a user to provide page content directly, bypassing the live fetch.
    """
    _instance = None
    _overrides: Dict[str, str] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ManualOverrideManager, cls).__new__(cls)
        return cls._instance

    def set_override(self, adapter_name: str, content: str):
        """Stores the override content for a specific adapter."""
        self._overrides[adapter_name.lower()] = content

    def get_override(self, adapter_name: str) -> Optional[str]:
        """
        Retrieves the override content for a specific adapter and clears it.
        This ensures the override is used only once.
        """
        return self._overrides.pop(adapter_name.lower(), None)

# Instantiate the singleton for easy import
override_manager = ManualOverrideManager()
