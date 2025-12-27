# python_service/credentials_manager.py
import sys

keyring = None
IS_WINDOWS = False

# Only attempt to import keyring on a Windows system.
if sys.platform == "win32":
    IS_WINDOWS = True
    try:
        import keyring
        # This check is crucial for cross-platform compatibility
        import keyring.backends.windows
    except ImportError:
        # If imports fail even on Windows, gracefully disable keyring
        keyring = None
        IS_WINDOWS = False
        print("Warning: keyring or its Windows backend is not available. Secure credential storage is disabled.")


class SecureCredentialsManager:
    """Manages secrets in the system's native credential store."""

    SERVICE_NAME = "Fortuna"

    @staticmethod
    def save_credential(account: str, secret: str) -> bool:
        """Saves a secret for a given account (e.g., 'api_key', 'betfair_username')."""
        if not IS_WINDOWS:
            print("Credential storage is only supported on Windows.")
            return False
        try:
            keyring.set_password(SecureCredentialsManager.SERVICE_NAME, account, secret)
            return True
        except Exception as e:
            print(f"❌ Failed to save credential for {account}: {e}")
            return False

    @staticmethod
    def get_credential(account: str) -> str:
        """Retrieves a secret for a given account."""
        if not IS_WINDOWS:
            return None
        try:
            return keyring.get_password(SecureCredentialsManager.SERVICE_NAME, account)
        except Exception as e:
            print(f"❌ Failed to retrieve credential for {account}: {e}")
            return None

    @staticmethod
    def get_betfair_credentials() -> tuple[str, str]:
        """Convenience method to retrieve both Betfair username and password."""
        username = SecureCredentialsManager.get_credential("betfair_username")
        password = SecureCredentialsManager.get_credential("betfair_password")
        return username, password

    @staticmethod
    def delete_credential(account: str):
        """Deletes a specific credential."""
        if not IS_WINDOWS:
            return
        try:
            keyring.delete_password(SecureCredentialsManager.SERVICE_NAME, account)
        except Exception:
            pass
