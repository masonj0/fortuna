# python_service/config.py
import os
from functools import lru_cache
from pathlib import Path
from typing import List
from typing import Optional

import structlog
from pydantic import Field
from pydantic import model_validator
from pydantic_settings import BaseSettings

from .credentials_manager import SecureCredentialsManager

# --- Encryption Setup ---
try:
    from cryptography.fernet import Fernet

    ENCRYPTION_ENABLED = True
except ImportError:
    ENCRYPTION_ENABLED = False

KEY_FILE = Path(".key")
CIPHER = None
if ENCRYPTION_ENABLED and KEY_FILE.exists():
    with open(KEY_FILE, "rb") as f:
        key = f.read()
    CIPHER = Fernet(key)


def decrypt_value(value: Optional[str]) -> Optional[str]:
    """If a value is encrypted, decrypts it. Otherwise, returns it as is."""
    if value and value.startswith("encrypted:") and CIPHER:
        try:
            return CIPHER.decrypt(value[10:].encode()).decode()
        except Exception:
            structlog.get_logger(__name__).error("Decryption failed on field.")
            return None
    return value


class Settings(BaseSettings):
    API_KEY: str = Field("", min_length=16)

    # --- API Gateway Configuration ---
    UVICORN_HOST: str = "127.0.0.1"
    UVICORN_PORT: int = 8000
    UVICORN_RELOAD: bool = True

    # --- Database Configuration ---
    DATABASE_TYPE: str = "sqlite"
    DATABASE_URL: str = "sqlite:///./fortuna.db"

    # --- Optional Betfair Credentials ---
    BETFAIR_APP_KEY: Optional[str] = None

    # --- Caching & Performance ---
    REDIS_URL: str = "redis://localhost:6379"
    CACHE_TTL_SECONDS: int = 1800  # 30 minutes
    MAX_CONCURRENT_REQUESTS: int = 10
    HTTP_POOL_CONNECTIONS: int = 100
    HTTP_POOL_MAXSIZE: int = 100
    HTTP_MAX_KEEPALIVE: int = 50
    DEFAULT_TIMEOUT: int = 30
    ADAPTER_TIMEOUT: int = 20

    # --- Logging ---
    LOG_LEVEL: str = "INFO"

    # --- Optional Adapter Keys ---
    NEXT_PUBLIC_API_KEY: Optional[
        str
    ] = None  # Allow frontend key to be present in .env
    TVG_API_KEY: Optional[str] = None
    RACING_AND_SPORTS_TOKEN: Optional[str] = None
    POINTSBET_API_KEY: Optional[str] = None
    GREYHOUND_API_URL: Optional[str] = None
    THE_RACING_API_KEY: Optional[str] = None

    # --- CORS Configuration ---
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:3001"]

    model_config = {"env_file": ".env", "case_sensitive": True}

    @model_validator(mode="after")
    def process_settings(self) -> "Settings":
        """
        This validator runs after the initial settings are loaded from .env and
        performs two key functions:
        1. If API_KEY is missing, it falls back to the SecureCredentialsManager.
        2. It decrypts any fields that were loaded from the .env file.
        """
        # 1. Fallback for API_KEY
        if not self.API_KEY:
            self.API_KEY = (
                SecureCredentialsManager.get_credential("api_key") or "MISSING"
            )

        # 2. Security validation for API_KEY
        insecure_keys = {"test", "changeme", "default", "secret", "password", "admin"}
        if self.API_KEY in insecure_keys:
            raise ValueError(
                f"The provided API_KEY '{self.API_KEY}' is on the list of insecure default values and is not allowed."
            )

        # 2. Decrypt sensitive fields
        self.BETFAIR_APP_KEY = decrypt_value(self.BETFAIR_APP_KEY)

        return self


@lru_cache()
def get_settings() -> Settings:
    """Loads settings and performs a proactive check for legacy paths."""
    log = structlog.get_logger(__name__)
    if ENCRYPTION_ENABLED and not KEY_FILE.exists():
        log.warning(
            "encryption_key_not_found",
            file=str(KEY_FILE),
            recommendation="Run 'python manage_secrets.py' to generate a key.",
        )

    settings = Settings()

    # --- Legacy Path Detection ---
    legacy_paths = ["attic/", "checkmate_web/", "vba_source/"]
    for path in legacy_paths:
        if os.path.exists(path):
            log.warning(
                "legacy_path_detected",
                path=path,
                recommendation="This directory is obsolete and should be removed for optimal performance and security.",
            )

    return settings
