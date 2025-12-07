import json
from datetime import datetime
from pathlib import Path

freeze = Path('backend/backend-freeze.txt')
packages = []
if freeze.exists():
    for line in freeze.read_text().splitlines():
        if '==' in line:
            packages.append({
                'name': line.split('==')[0],
                'version': line.split('==')[1]
            })

sbom = {
    'spdxVersion': 'SPDX-2.3',
    'name': 'HatTrick Fusion Backend',
    'packages': packages
}

Path('sbom.json').write_text(json.dumps(sbom, indent=2))
