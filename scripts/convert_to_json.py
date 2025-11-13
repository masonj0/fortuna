# convert_to_json.py
# This script now contains the full, enlightened logic to handle all manifest formats and path styles.

import json
import os
import sys
from multiprocessing import Process
from multiprocessing import Queue

# --- Configuration ---
MANIFEST_FILES = [
    "MANIFEST_PART1_BACKEND.json",
    "MANIFEST_PART2_FRONTEND.json",
    "MANIFEST_PART3_SUPPORT.json",
    "MANIFEST_PART4_ROOT.json",
]
OUTPUT_DIR = "ReviewableJSON"
FILE_PROCESSING_TIMEOUT = 10
EXCLUDED_FILES = ["package-lock.json"]


def read_json_manifest(manifest_path: str) -> list[str]:
    """Reads a JSON manifest file and returns a list of file paths."""
    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


# --- SANDBOXED FILE READ (Unchanged) ---
def _sandboxed_file_read(file_path, q):
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        q.put({"file_path": file_path, "content": content})
    except Exception as e:
        q.put({"error": str(e)})


def convert_file_to_json_sandboxed(file_path):
    q = Queue()
    p = Process(target=_sandboxed_file_read, args=(file_path, q))
    p.start()
    p.join(timeout=FILE_PROCESSING_TIMEOUT)

    try:
        if p.is_alive():
            p.terminate()
            p.join()
            return {"error": f"Timeout: File processing took longer than {FILE_PROCESSING_TIMEOUT} seconds."}

        if not q.empty():
            return q.get()
        return {"error": "Unknown error in sandboxed read process."}
    finally:
        # ✅ Properly close and flush the queue
        try:
            while not q.empty():
                q.get_nowait()
        except Exception:
            pass
        q.close()
        q.join_thread()


# --- Main Orchestrator ---
def main():
    print(f"\n{'=' * 60}\nStarting IRONCLAD JSON backup process... (Enlightened Scribe Edition)\n{'=' * 60}")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    all_local_paths = []
    for manifest in MANIFEST_FILES:
        print(f"--> Parsing manifest: {manifest}")
        paths = read_json_manifest(manifest)
        if paths:
            all_local_paths.extend(paths)
            print(f"    --> Found {len(paths)} valid file paths.")
        else:
            print(f"    [WARNING] Manifest not found or is empty: {manifest}")

    if not all_local_paths:
        print("\n[FATAL] No valid file paths found in any manifest. Aborting.")
        sys.exit(1)

    unique_local_paths = sorted(list(set(all_local_paths)))
    print(f"\nFound a total of {len(unique_local_paths)} unique files to process.")
    processed_count, failed_count = 0, 0

    for local_path in unique_local_paths:
        if os.path.basename(local_path) in EXCLUDED_FILES:
            print(f"\n--> Skipping excluded file: {local_path}")
            failed_count += 1
            continue
        print(f"\nProcessing: {local_path}")
        json_data = convert_file_to_json_sandboxed(local_path)
        if json_data and "error" not in json_data:
            output_path = os.path.join(OUTPUT_DIR, local_path + ".json")
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(json_data, f, indent=4)
            print(f"    [SUCCESS] Saved backup to {output_path}")
            processed_count += 1
        else:
            error_msg = json_data.get("error", "Unknown error") if json_data else "File not found"
            print(f"    [ERROR] Failed to process {local_path}: {error_msg}")
            failed_count += 1

    print(f"\n{'=' * 60}")
    print("Backup process complete.")
    print(f"Successfully processed: {processed_count}/{len(unique_local_paths)}")
    print(f"Failed/Skipped: {failed_count}")
    print(f"{'=' * 60}")

    if failed_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
