# python_service/db/init.py
import sqlite3
import os
from ..config import get_settings


def initialize_database():
    """
    Initializes the database based on the configuration.
    Currently supports a simple SQLite fallback for local testing.
    """
    settings = get_settings()
    db_type = getattr(settings, "DATABASE_TYPE", "sqlite").lower()

    if db_type == "sqlite":
        # DATABASE_URL for sqlite will be like 'sqlite:///./fortuna.db'
        db_path = settings.DATABASE_URL.split("///")[1]

        # Ensure the directory for the database exists
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # The schema is based on the provided pg_schemas, adapted for SQLite
            # This is a simplified version for demonstration.
            cursor.execute(
                """
            CREATE TABLE IF NOT EXISTS races (
                id TEXT PRIMARY KEY,
                venue TEXT NOT NULL,
                race_number INTEGER NOT NULL,
                start_time TEXT NOT NULL,
                source TEXT,
                field_size INTEGER
            )
            """
            )

            cursor.execute(
                """
            CREATE TABLE IF NOT EXISTS runners (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                race_id TEXT,
                number INTEGER,
                name TEXT,
                odds REAL,
                FOREIGN KEY (race_id) REFERENCES races (id)
            )
            """
            )

            conn.commit()
            conn.close()
            print("SQLite database initialized successfully.")
        except sqlite3.Error as e:
            print(f"Error initializing SQLite database: {e}")
            raise
