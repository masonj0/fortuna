#!/usr/bin/env python3
import os
import sys
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DIST_DIR = PROJECT_ROOT / 'dist'
BUILD_DIR = PROJECT_ROOT / 'build'
MSI_SOURCE_DIR = PROJECT_ROOT / 'build_wix' / 'msi_source'
EXECUTABLE_NAME = 'fortuna-backend.exe' if sys.platform == 'win32' else 'fortuna-backend'

def run_command(cmd, cwd=None):
    print(f'▶ Running: {" ".join(cmd)}')
    # FIX: Explicitly use UTF-8 for decoding the output, and ignore errors for robustness.
    # This resolves the UnicodeDecodeError when reading the external WiX process's output.
    subprocess.run(cmd, cwd=cwd, check=True, text=True, encoding='utf-8', errors='ignore')

def main():
    print('=== Starting Fortuna WiX MSI Build ===')

    # Step 1: Locate or build the executable
    print(f'--- Step 1: Searching for {EXECUTABLE_NAME} in {DIST_DIR}... ---')
    found_exes = list(DIST_DIR.rglob(EXECUTABLE_NAME))

    if not found_exes:
        print(f'Executable not found in {DIST_DIR}. Attempting to build with PyInstaller...')
        try:
            run_command(['pyinstaller', str(PROJECT_ROOT / 'fortuna-backend.spec')])
            found_exes = list(DIST_DIR.rglob(EXECUTABLE_NAME))
            if not found_exes:
                sys.exit(f'✗ PyInstaller build failed: Executable "{EXECUTABLE_NAME}" not found in {DIST_DIR} after build.')
        except subprocess.CalledProcessError as e:
            sys.exit(f'✗ PyInstaller command failed with exit code {e.returncode}.')

    if len(found_exes) > 1:
        print(f'⚠️ WARNING: Found multiple executables. Using the first one: {found_exes[0]}')

    exe_path = found_exes[0]
    heat_source_dir = exe_path.parent
    print(f'✓ Using executable at {exe_path}')
    print(f'✓ Setting WiX heat source directory to {heat_source_dir}')


    # 2. Generate WiX file list from the dist directory
    print("--- Step 2: Generating WiX file list with 'heat' ---")
    MSI_SOURCE_DIR.mkdir(exist_ok=True)
    files_wxs = MSI_SOURCE_DIR / 'files.wxs'
    run_command(['heat', 'dir', str(heat_source_dir), '-o', str(files_wxs), '-gg', '-sfrag', '-srd', '-cg', 'MainFiles'])
    print(f'✓ WiX file fragment created at {files_wxs}')

    # 3. Compile WiX project
    print("--- Step 3: Compiling WiX project with 'candle' ---")
    obj_dir = MSI_SOURCE_DIR / 'obj'
    obj_dir.mkdir(exist_ok=True)
    run_command(['candle', str(PROJECT_ROOT / 'build_wix' / 'Product.wxs'), str(files_wxs), '-o', f'{obj_dir}/'])
    print('✓ WiX compilation successful.')

    # 4. Link WiX project into MSI
    print("--- Step 4: Linking MSI with 'light' ---")
    import glob
    obj_files = glob.glob(str(obj_dir / '*.wixobj'))
    if not obj_files:
        sys.exit('✗ Linking failed: No .wixobj files found to link.')

    output_msi = PROJECT_ROOT / 'dist' / 'Fortuna-Backend-Service.msi'

    light_cmd = ['light', '-o', str(output_msi)] + obj_files
    run_command(light_cmd)
    print(f'✓ MSI created successfully at {output_msi}')

    print('\n=== BUILD COMPLETE ===')

if __name__ == '__main__':
    main()
