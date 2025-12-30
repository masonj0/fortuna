# python_service/credentials_manager.py
try:
    import keyring

    # This check is crucial for cross-platform compatibility
    import keyring.backends.windows

    IS_WINDOWS = True
except ImportError:
    keyring = None
    IS_WINDOWS = False


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
