# ARCHIVE_PROJECT.py - The Balanced Manifest-Driven Scribe
import json
from pathlib import Path

# --- Configuration ---
PROJECT_ROOT = Path(__file__).parent
NUM_ARCHIVE_PARTS = 5
MANIFEST_FILENAME_TEMPLATE = "MANIFEST_PART{}.json"
OUTPUT_FILENAME_TEMPLATE = "FORTUNA_ALL_PART{}.JSON"


def run_archiver():
    """
    Generates balanced FORTUNA_ALL JSON archives based on the
    size-balanced manifest files.
    """
    print("--- Fortuna Faucet Balanced Scribe ---")
    print("Generating archives from size-balanced manifests...")

    total_files_archived = 0
    total_warnings = 0

    for part_num in range(1, NUM_ARCHIVE_PARTS + 1):
        manifest_file = MANIFEST_FILENAME_TEMPLATE.format(part_num)
        manifest_path = PROJECT_ROOT / manifest_file
        archive_content = {}

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                file_list = json.load(f)
        except FileNotFoundError:
            print(f"[ERROR] Manifest file not found: {manifest_file}. Is it generated? Skipping.")
            total_warnings += 1
            continue
        except json.JSONDecodeError:
            print(f"[ERROR] Could not decode JSON from {manifest_file}. Skipping.")
            total_warnings += 1
            continue

        print(f"Processing {manifest_file} for PART {part_num}...")
        for relative_path in file_list:
            file_path = PROJECT_ROOT / relative_path
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                archive_content[relative_path] = content
                total_files_archived += 1
            except FileNotFoundError:
                print(f"[WARNING] File listed in manifest not found: {relative_path}")
                total_warnings += 1
            except Exception as e:
                print(f"[ERROR] Could not read file {relative_path}: {e}")
                total_warnings += 1

        if not archive_content:
            print(f"Skipping empty PART {part_num}.")
            continue

        # Write the JSON archive file for the current part
        output_path = PROJECT_ROOT / OUTPUT_FILENAME_TEMPLATE.format(part_num)
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(archive_content, f, indent=4)
            print(f"✅ Successfully wrote {len(archive_content)} files to {output_path.name}")
        except Exception as e:
            print(f"[FATAL] Failed to write {output_path.name}: {e}")
            # Exit if we can't write, as this is a critical failure
            return

    print("\\n--- Scribe Process Complete ---")
    print(f"Total files archived: {total_files_archived}")
    print(f"Total warnings/errors encountered: {total_warnings}")
    if total_warnings == 0:
        print("\\n[SUCCESS] All manifest-driven archives are complete and balanced!")
    else:
        print("\\n[NOTE] Process completed with warnings. Please review the log.")


if __name__ == "__main__":
    run_archiver()
