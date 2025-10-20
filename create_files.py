
import json
import os
import sys

def create_files_from_json(json_file):
    with open(json_file, 'r') as f:
        data = json.load(f)

    for filepath, content in data.items():
        try:
            dirpath = os.path.dirname(filepath)
            if dirpath:
                os.makedirs(dirpath, exist_ok=True)

            with open(filepath, 'w') as f:
                f.write(content)
        except Exception as e:
            print(f"Error creating file {filepath}: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        create_files_from_json(sys.argv[1])
    else:
        print("Usage: python create_files.py <json_file>")
