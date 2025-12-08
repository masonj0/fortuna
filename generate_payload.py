import json
import os

files_to_read = [
    ".github/workflows/build-electron-clean-room.yml",
    ".github/workflows/build-electron-hybrid.yml",
    ".github/workflows/build-electron-msi-gpt5.yml",
    ".github/workflows/build-msi-hat-trick-fusion.yml",
    ".github/workflows/build-msi-hattrickfusion-ultimate.yml",
    ".github/workflows/build-msi-unified.yml",
    ".github/workflows/build-web-service-msi-jules.yml",
    ".github/workflows/codeql.yml",
]

payload = {}
for filepath in files_to_read:
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            payload[filepath] = f.read()
    except FileNotFoundError:
        payload[filepath] = f"ERROR: File not found at {filepath}"
    except Exception as e:
        payload[filepath] = f"ERROR: Could not read file {filepath}: {e}"

print(json.dumps(payload, indent=2))
