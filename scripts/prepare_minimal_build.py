# scripts/prepare_minimal_build.py
import os
import shutil

# This script prepares the source tree for a 'minimal' build.
# A minimal build includes only the core application and a small, curated
# set of essential data adapters, excluding the larger, more specialized ones.

ADAPTERS_TO_KEEP = [
    "__init__.py",
    "base_adapter.py",
    "handler_factory.py",
    # --- Essential Adapters ---
    "betfair_adapter.py",
    "sporting_life_adapter.py",
    "racing_post_adapter.py",
]


def main():
    """
    Removes non-essential adapter files from the python_service/adapters
    directory to create a minimal build artifact.
    """
    adapters_dir = os.path.join("python_service", "adapters")
    if not os.path.isdir(adapters_dir):
        print(f"[ERROR] Adapters directory not found at: {adapters_dir}")
        exit(1)

    print(f"Scanning adapters directory: {adapters_dir}")
    removed_count = 0
    for filename in os.listdir(adapters_dir):
        if filename not in ADAPTERS_TO_KEEP:
            file_path = os.path.join(adapters_dir, filename)
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    print(f"  - Removed file: {filename}")
                    removed_count += 1
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
                    print(f"  - Removed directory: {filename}")
                    removed_count += 1
            except OSError as e:
                print(f"[ERROR] Failed to remove {file_path}: {e}")
                exit(1)

    print(
        f"\nMinimal build preparation complete. Removed {removed_count} non-essential adapter(s)."
    )


if __name__ == "__main__":
    main()
