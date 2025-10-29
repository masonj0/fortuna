# python_service/initialize_db.py
from db.init import initialize_database

def main():
    """
    This script exists solely to initialize the database.
    It should be called before the main server process is started.
    """
    print("Initializing database...", flush=True)
    initialize_database()
    print("Database initialization complete.", flush=True)

if __name__ == "__main__":
    main()
