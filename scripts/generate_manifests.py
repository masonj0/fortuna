# scripts/generate_manifests.py
import json
import os
from pathlib import Path

# --- Configuration ---
ROOT_DIR = Path(".")
OUTPUT_DIR = Path(".")
NUM_MANIFESTS = 5 # We will create 5 balanced manifests

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
    """Walk the directory to find all files, respecting exclusions."""
    all_files_with_size = []
    for root, dirs, files in os.walk(ROOT_DIR, topdown=True):
        # Prevent walking into excluded directories
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith("PREV_")]

        for name in files:
            if name in EXCLUDE_FILES or name.endswith(".bmp"):
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

    return all_files_with_size


def balance_files_by_size(files_with_size, num_bins):
    """
    Distributes files into a specified number of bins, balancing the total size.
    Uses a greedy algorithm for efficiency.
    """
    # Sort files by size in descending order to handle largest files first
    files_with_size.sort(key=lambda x: x[1], reverse=True)

    bins = [[] for _ in range(num_bins)]
    bin_sizes = [0] * num_bins

    for path, size in files_with_size:
        # Find the bin with the smallest current total size
        min_bin_index = bin_sizes.index(min(bin_sizes))
        # Add the file to that bin
        bins[min_bin_index].append(path)
        # Update the bin's total size
        bin_sizes[min_bin_index] += size

    # Print the balancing results for verification
    print("--- Manifest Balancing Results ---")
    for i, (file_list, total_size) in enumerate(zip(bins, bin_sizes)):
        print(
            f" Manifest {i+1}: {len(file_list):>4} files, "
            f"Total size: {total_size / 1024 / 1024:>6.2f} MB"
        )
    print("---------------------------------")

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
