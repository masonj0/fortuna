# scripts/generate_manifests.py
import json
import os
from pathlib import Path

# --- Configuration ---
ROOT_DIR = Path(".")
OUTPUT_DIR = Path(".")
NUM_MANIFESTS = 5 # We will create 5 balanced manifests

# --- Inclusion/Exclusion Rules ---
# This script is now comprehensive. Instead of a narrow include list,
# it scans everything and uses a more precise exclusion list.
INCLUDE_ONLY_DIRS = None # Deactivated: We now scan all directories by default

EXCLUDE_DIRS = {
    # Standard git/ide/v-env exclusions
    ".git", ".idea", ".vscode", "node_modules", ".next", ".venv",
    # Build artifacts and caches
    "dist", "build", "__pycache__", ".pytest_cache", "out", "build_wix",
    # Agent-specific/Volatile directories
    "attic", "installer", "ReviewableJSON", "jules-scratch",
    # Legacy code not relevant to the current monolith
    "PREV_src", "python_service",
}

EXCLUDE_FILES_BY_EXTENSION = {
    # Archives and logs
    ".zip", ".json", ".log", ".db", ".sqlite3",
    # Binary/Image formats not useful for LLM context
    ".png", ".ico", ".bmp", ".exe", ".dll", ".pyd", ".pdf",
    # Deactivated workflows (keep them for history, but not for active context)
    ".ymlx"
}


def get_all_project_files():
    """
    Walks the entire project directory to find all relevant files for archiving,
    respecting a detailed set of exclusion rules.
    """
    all_files_with_size = []
    print("\n--- Starting Comprehensive File Audit ---")
    scanned_count = 0
    included_count = 0

    for root, dirs, files in os.walk(ROOT_DIR, topdown=True):
        current_path = Path(root)

        # 1. Directory Exclusion: Prune entire directory subtrees
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.endswith('.egg-info')]

        for name in files:
            scanned_count += 1
            file_path = current_path / name

            # 2. Filename/Extension Exclusion
            if name.startswith(('MANIFEST_PART', 'FORTUNA_ALL_PART', '.env')):
                continue
            if file_path.suffix in EXCLUDE_FILES_BY_EXTENSION:
                continue

            # Special case: allow '.spec' files which are critical configs
            if file_path.suffix == '.spec' and name not in ['api.spec']:
                 pass # keep it
            elif file_path.suffix in ['.spec']:
                 continue # exclude other .spec files

            try:
                posix_path = str(file_path.as_posix())
                size = os.path.getsize(file_path)
                all_files_with_size.append((posix_path, size))
                included_count += 1
            except FileNotFoundError:
                print(f"[WARNING] File not found during scan: {file_path}")
                continue

    print(f"Scanned {scanned_count} files, included {included_count} for manifest.")
    print("--- File Audit Complete ---\n")
    return all_files_with_size


def balance_files_by_size(files_with_size, num_bins):
    """
    Distributes files into a specified number of bins, balancing by size and count.
    Uses a hybrid greedy and round-robin approach for better distribution.
    """
    # Define categories for more granular balancing
    categories = {
        'large': [], 'medium': [], 'small': [], 'config': [], 'docs': [],
        'workflows': [], 'scripts': [], 'source': []
    }

    # Categorize files based on extension and size
    for path, size in files_with_size:
        ext = Path(path).suffix.lower()
        if 'github/workflows' in path:
            categories['workflows'].append((path, size))
        elif ext in ['.md', '.txt']:
            categories['docs'].append((path, size))
        elif ext in ['.json', '.toml', '.ini', '.spec', '.lock']:
            categories['config'].append((path, size))
        elif ext == '.py' and 'scripts' in path:
            categories['scripts'].append((path, size))
        elif ext in ['.py', '.js', '.ts', '.tsx', '.css', '.html', '.wxs']:
            if size > 50 * 1024:  # Over 50KB
                categories['large'].append((path, size))
            elif size > 10 * 1024: # Over 10KB
                categories['medium'].append((path, size))
            else:
                categories['small'].append((path, size))
        else:
            categories['source'].append((path, size))

    bins = [[] for _ in range(num_bins)]
    bin_sizes = [0] * num_bins

    # Distribute large files first using greedy approach
    for category in ['large', 'medium']:
        # Sort descending to place largest files first
        categories[category].sort(key=lambda x: x[1], reverse=True)
        for path, size in categories[category]:
            min_bin_index = bin_sizes.index(min(bin_sizes))
            bins[min_bin_index].append(path)
            bin_sizes[min_bin_index] += size

    # Distribute remaining files using round-robin to balance file count
    current_bin = 0
    for category in ['small', 'config', 'docs', 'workflows', 'scripts', 'source']:
        # Sort alphabetically for consistent distribution
        categories[category].sort(key=lambda x: x[0])
        for path, size in categories[category]:
            bins[current_bin].append(path)
            bin_sizes[current_bin] += size
            current_bin = (current_bin + 1) % num_bins

    # Print the balancing results for verification
    print("--- Manifest Balancing Results (Enhanced) ---")
    for i, (file_list, total_size) in enumerate(zip(bins, bin_sizes)):
        print(
            f" Manifest {i+1}: {len(file_list):>4} files, "
            f"Total size: {total_size / 1024 / 1024:>6.2f} MB"
        )
    print("------------------------------------------")

    return bins


def main():
    """Generate balanced manifest files based on file size."""
    print("--- Starting Manifest Generation (Size-Balanced) ---")
    all_files = get_all_project_files()
    print(f"Found {len(all_files)} total project files to consider.")

    balanced_manifests = balance_files_by_size(all_files, NUM_MANIFESTS)

    # Write the updated manifest files
    for i, file_list in enumerate(balanced_manifests):
        manifest_name = f"MANIFEST_PART{i+1}.json"
        output_path = OUTPUT_DIR / manifest_name
        sorted_files = sorted(file_list) # Sort alphabetically for consistency
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(sorted_files, f, indent=4)
        print(f"✅ Wrote {len(sorted_files)} entries to {output_path}")

    print("\n[SUCCESS] All manifest files have been generated and balanced.")


if __name__ == "__main__":
    main()
