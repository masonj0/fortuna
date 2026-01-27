import os
import json

adapter_dir = "web_service/backend/adapters/"
bundle = {}

for filename in os.listdir(adapter_dir):
    if filename.endswith("adapter.py"):
        filepath = os.path.join(adapter_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            bundle[filename] = f.read()

print(json.dumps(bundle, indent=2))
