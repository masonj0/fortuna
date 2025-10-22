import os
import glob

def main():
    """
    Prepares the repository for a minimal build by removing adapter files that are
    not part of the core set required for the minimal version. This is used in the
    CI/CD pipeline to create a smaller installer.
    """
    adapters_dir = os.path.join("python_service", "adapters")

    # These are the only adapters included in the minimal build, based on engine.py
    core_adapters = [
        "greyhound_adapter.py",
        "the_racing_api_adapter.py",
        "gbgb_api_adapter.py",
    ]

    # These files are essential base classes, utilities, or initializers
    essential_files = [
        "__init__.py",
        "base.py",
        "utils.py",
        "betfair_auth_mixin.py", # Kept as it might be linked to base classes
    ]

    files_to_keep = set(core_adapters + essential_files)

    print("Preparing for minimal build...")
    print(f"Adapters directory: {adapters_dir}")
    print(f"Core adapter files to keep: {core_adapters}")

    if not os.path.isdir(adapters_dir):
        print(f"Error: Adapters directory not found at '{adapters_dir}'")
        return

    # Get all python files in the adapters directory
    adapter_files = [f for f in os.listdir(adapters_dir) if f.endswith(".py")]

    deleted_count = 0
    for filename in adapter_files:
        if filename not in files_to_keep:
            try:
                filepath = os.path.join(adapters_dir, filename)
                os.remove(filepath)
                print(f"  - Deleted non-core adapter: {filename}")
                deleted_count += 1
            except OSError as e:
                print(f"Error deleting file {filename}: {e}")

    print(f"\nMinimal build preparation complete. Deleted {deleted_count} adapter file(s).")

if __name__ == "__main__":
    main()
