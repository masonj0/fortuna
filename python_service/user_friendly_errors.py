# python_service/user_friendly_errors.py

"""
Centralized dictionary for mapping technical exceptions to user-friendly messages.
"""

ERROR_MAP = {
    "AdapterHttpError": {
        "message": "A data source is currently unavailable.",
        "suggestion": "This is usually temporary. Please try again in a few minutes. If the problem persists, the website may be down for maintenance."
    },
    "AdapterConfigError": {
        "message": "A data adapter is misconfigured.",
        "suggestion": "Please check that all required API keys and settings are present in your .env file."
    },
    "default": {
        "message": "An unexpected error occurred.",
        "suggestion": "Please check the application logs for more details or contact support."
    }
}
