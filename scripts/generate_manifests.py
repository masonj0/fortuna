# scripts/generate_manifests.py
import json
import os
from pathlib import Path

# --- Configuration ---
ROOT_DIR = Path(".")
OUTPUT_DIR = Path(".")
NUM_MANIFESTS = 5 # We will create 5 balanced manifests

# --- Inclusion/Exclusion Rules ---
# To keep the manifests clean and focused, we define specific directories to include.
# Everything else will be ignored.
INCLUDE_ONLY_DIRS = {
    "python_service",
    "web_platform",
    "electron",
    "scripts",
    "wix",
    ".github",
    "web_service", # Include the new web service architecture
}

EXCLUDE_DIRS = {
    ".git",
    ".idea",
    ".vscode",
    "node_modules",
    ".next",
    ".venv",
    "dist",
    "build",
    "__pycache__",
    "attic",
    "installer",
    "ReviewableJSON",
    "PREV_src",
    ".pytest_cache",
}

EXCLUDE_FILES = {
    # Exclude deactivated workflows
    ".ymlx",
    # Exclude the manifests and archives themselves
    "MANIFEST_PART1.json",
    "MANIFEST_PART2.json",
    "MANIFEST_PART3.json",
    "MANIFEST_PART4.json",
    "MANIFEST_PART5.json",
    "FORTUNA_ALL_PART1.JSON",
    "FORTUNA_ALL_PART2.JSON",
    "FORTUNA_ALL_PART3.JSON",
    "FORTUNA_ALL_PART4.JSON",
    "FORTUNA_ALL_PART5.JSON",
    # Exclude self and other key scripts from being archived
    "generate_manifests.py",
    "ARCHIVE_PROJECT.py",
    # Exclude environment files and build specs
    ".env",
    ".env.local.example",
    "env",
    "api.spec",
    "fortuna-api.spec",
}


def get_all_project_files():
    """Walk the directory to find all files, respecting inclusions and exclusions."""
    all_files_with_size = []

    # Start with a curated list of top-level files to include
    top_level_files = [
        "AGENTS.md", "ARCHITECTURAL_MANDATE.md", "HISTORY.md", "README.md",
        "WISDOM.md", "PSEUDOCODE.MD", "VERSION.txt", "fortuna-backend-electron.spec",
        "fortuna-backend-webservice.spec", "fortuna-webservice-electron.spec",
        "fortuna-webservice-service.spec", "pyproject.toml", "pytest.ini",
        "requirements.txt", "requirements-dev.txt", "package.json", "package-lock.json",
        ".github/workflows/build-msi-supreme-combo.yml"
    ]
    for file_name in top_level_files:
        file_path = ROOT_DIR / file_name
        if file_path.exists():
            all_files_with_size.append((str(file_path.as_posix()), os.path.getsize(file_path)))

    # Walk through the explicitly included directories
    for include_dir in INCLUDE_ONLY_DIRS:
        walk_path = ROOT_DIR / include_dir
        if not walk_path.is_dir():
            continue
        for root, dirs, files in os.walk(walk_path, topdown=True):
            # Still respect the nested exclude directories like __pycache__
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]

            for name in files:
                if name in EXCLUDE_FILES or name.endswith((".bmp", ".png", ".ico", ".ymlx")):
                    continue

                file_path = Path(root) / name
                try:
                    # Use forward slashes for cross-platform compatibility
                    posix_path = str(file_path.as_posix())
                    size = os.path.getsize(file_path)
                    all_files_with_size.append((posix_path, size))
                except FileNotFoundError:
                    print(f"[WARNING] File not found while scanning: {file_path}")
                    continue

    # Consolidate and remove duplicates that might arise from overlapping rules
    return list(set(all_files_with_size))


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
