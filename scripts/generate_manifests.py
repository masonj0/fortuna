# scripts/generate_manifests.py
import os
import json
from pathlib import Path

# --- Configuration ---
ROOT_DIR = Path('.')
OUTPUT_DIR = Path('.')

EXCLUDE_DIRS = {
    '.git', '.idea', '.vscode', 'node_modules', '.next', '.venv',
    'dist', 'build', '__pycache__', 'attic', 'installer',
    'ReviewableJSON', 'PREV_src', '.pytest_cache'
}

EXCLUDE_FILES = {
    'MANIFEST_PART1_BACKEND.json', 'MANIFEST_PART2_FRONTEND.json',
    'MANIFEST_PART3_SUPPORT.json', 'MANIFEST_PART4_ROOT.json',
    'FORTUNA_ALL_PART1.JSON', 'FORTUNA_ALL_PART2.JSON',
    'FORTUNA_ALL_PART3.JSON', 'FORTUNA_ALL_PART4.JSON',
    'generate_manifests.py', '.env', '.env.example', '.env.local.example',
    'env', 'api.spec', 'fortuna-api.spec' # Exclude spec files
}

# Define the structure of our manifests with the correct filenames and mappings
MANIFESTS_CONFIG = {
    "MANIFEST_PART1_BACKEND.json": ['python_service'],
    "MANIFEST_PART2_FRONTEND.json": ['web_platform', 'electron'],
    "MANIFEST_PART3_SUPPORT.json": ['pg_schemas', 'tests'],
    "MANIFEST_PART4_ROOT.json": []  # This will hold all remaining files
}

def is_excluded(path, entry_name):
    """Check if a file or directory should be excluded."""
    if entry_name.startswith('PREV_') or entry_name in EXCLUDE_DIRS or entry_name in EXCLUDE_FILES:
        return True
    # Exclude files in the root `dist` directory that might be created by PyInstaller
    if path.parent == ROOT_DIR and path.name == 'dist':
        return True
    return False

def main():
    """Walk the directory and generate categorized manifest files."""
    all_files = []
    for root, dirs, files in os.walk(ROOT_DIR, topdown=True):
        # Prevent walking into excluded directories
        dirs[:] = [d for d in dirs if not is_excluded(Path(root) / d, d)]

        for name in files:
            file_path = Path(root) / name
            if not is_excluded(file_path, name):
                # Use forward slashes for cross-platform compatibility
                all_files.append(str(file_path.as_posix()))

    # Initialize manifest lists
    manifest_files = {manifest: [] for manifest in MANIFESTS_CONFIG}
    categorized_files = set()

    # Assign files to manifests based on top-level directory
    for f_path_str in all_files:
        assigned = False
        for manifest, dirs in MANIFESTS_CONFIG.items():
            for d in dirs:
                if f_path_str.startswith(d + '/'):
                    manifest_files[manifest].append(f_path_str)
                    categorized_files.add(f_path_str)
                    assigned = True
                    break
            if assigned:
                break

    # All remaining files go into the root manifest
    root_files = sorted([f for f in all_files if f not in categorized_files])
    manifest_files["MANIFEST_PART4_ROOT.json"] = root_files

    # Write the updated manifest files
    for manifest_name, files in manifest_files.items():
        output_path = OUTPUT_DIR / manifest_name
        sorted_files = sorted(list(set(files))) # Sort and ensure uniqueness
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(sorted_files, f, indent=4)
        print(f"✅ Wrote {len(sorted_files)} entries to {output_path}")

if __name__ == '__main__':
    main()
