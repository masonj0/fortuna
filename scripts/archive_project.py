# scripts/archive_project.py
import os
import zipfile
from datetime import datetime

def main():
    """
    Creates a zip archive of the entire project repository, excluding
    the .git directory and the archive file itself.
    """
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    now = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    archive_name = f"fortuna_archive_{now}.zip"
    archive_path = os.path.join(project_root, archive_name)

    print(f"Archiving project to: {archive_path}")

    with zipfile.ZipFile(archive_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(project_root):
            if '.git' in root:
                continue
            for file in files:
                if file == archive_name:
                    continue
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, project_root)
                zipf.write(file_path, arcname)
    print("Archive complete.")

if __name__ == "__main__":
    main()
