#!/usr/bin/env python3
import os
import sys
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DIST_DIR = PROJECT_ROOT / 'dist'
BUILD_DIR = PROJECT_ROOT / 'build'
MSI_SOURCE_DIR = PROJECT_ROOT / 'build_wix' / 'msi_source'
EXECUTABLE_NAME = 'fortuna-backend.exe'

def run_command(cmd, cwd=None):
    print(f'▶ Running: {" ".join(cmd)}')
    # FIX: Explicitly use UTF-8 for decoding the output, and ignore errors for robustness.
    # This resolves the UnicodeDecodeError when reading the external WiX process's output.
    subprocess.run(cmd, cwd=cwd, check=True, text=True, encoding='utf-8', errors='ignore')

def main():
    print('=== Starting Fortuna WiX MSI Build ===')

    exe_path = DIST_DIR / EXECUTABLE_NAME

    # 1. Build Executable with PyInstaller (if it doesn't exist)
    if not exe_path.exists():
        print('--- Step 1: Building executable with PyInstaller ---')
        run_command(['pyinstaller', str(PROJECT_ROOT / 'fortuna-backend.spec')])
        if not exe_path.exists():
            sys.exit('✗ PyInstaller build failed: Executable not found.')
        print(f'✓ Executable created at {exe_path}')
    else:
        print(f'--- Step 1: Found existing executable at {exe_path}, skipping build. ---')

    # 2. Generate WiX file list from the dist directory
    print("--- Step 2: Generating WiX file list with 'heat' ---")
    MSI_SOURCE_DIR.mkdir(exist_ok=True)
    files_wxs = MSI_SOURCE_DIR / 'files.wxs'
    run_command(['heat', 'dir', str(DIST_DIR), '-o', str(files_wxs), '-gg', '-sfrag', '-srd', '-cg', 'MainFiles', '-dr', 'INSTALLFOLDER'])
    print(f'✓ WiX file fragment created at {files_wxs}')

    # 3. Compile WiX project
    print("--- Step 3: Compiling WiX project with 'candle' ---")
    obj_dir = MSI_SOURCE_DIR / 'obj'
    obj_dir.mkdir(exist_ok=True)
    run_command(['candle', str(PROJECT_ROOT / 'build_wix' / 'Product.wxs'), str(files_wxs), '-o', f'{obj_dir}/'])
    print('✓ WiX compilation successful.')

    # 4. Link WiX project into MSI
    print("--- Step 4: Linking MSI with 'light' ---")
    output_msi = PROJECT_ROOT / 'dist' / 'Fortuna-Backend-Service.msi'
    run_command(['light', '-o', str(output_msi), f'{obj_dir}/*.wixobj'])
    print(f'✓ MSI created successfully at {output_msi}')

    print('\n=== BUILD COMPLETE ===')

if __name__ == '__main__':
    main()
