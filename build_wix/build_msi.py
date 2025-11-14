#!/usr/bin/env python3
import os
import sys
import shutil
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DIST_DIR = PROJECT_ROOT / 'dist'
FRONTEND_BUILD_DIR = PROJECT_ROOT / 'frontend_build'
WIX_STAGING_DIR = PROJECT_ROOT / 'build_wix' / 'staging'
MSI_SOURCE_DIR = PROJECT_ROOT / 'build_wix' / 'msi_source'
EXECUTABLE_NAME = 'fortuna-backend.exe'

def run_command(cmd, cwd=None):
    """Runs a command and exits if it fails."""
    print(f'▶ Running: {" ".join(cmd)}')
    try:
        subprocess.run(cmd, cwd=cwd, check=True, text=True, encoding='utf-8', errors='ignore')
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        sys.exit(f'✗ Command failed: {e}')

def main():
    """Main build process for the WiX MSI installer."""
    print('=== Starting Fortuna WiX MSI Build ===')

    # Step 1: Verify assets
    print('--- Step 1: Verifying required assets ---')
    exe_path = DIST_DIR / EXECUTABLE_NAME
    if not exe_path.exists():
        sys.exit(f'✗ Executable not found at {exe_path}. It should be downloaded by the workflow.')
    if not FRONTEND_BUILD_DIR.exists():
        sys.exit(f'✗ Frontend build directory not found at {FRONTEND_BUILD_DIR}. It should be downloaded by the workflow.')
    print('✓ Backend executable and frontend assets found.')

    # Step 2: Stage all files for WiX
    print(f'--- Step 2: Staging all files in {WIX_STAGING_DIR} ---')
    if WIX_STAGING_DIR.exists():
        shutil.rmtree(WIX_STAGING_DIR)

    # Stage backend executable and the entire UI directory
    ui_staging_dir = WIX_STAGING_DIR / 'ui'
    shutil.copytree(FRONTEND_BUILD_DIR, ui_staging_dir)
    shutil.copy(exe_path, WIX_STAGING_DIR / EXECUTABLE_NAME)
    print('✓ All assets copied to staging directory.')

    # Step 3: Generate WiX file list ONLY for the frontend files
    print("--- Step 3: Generating WiX file list for frontend with 'heat' ---")
    MSI_SOURCE_DIR.mkdir(exist_ok=True)
    files_wxs = MSI_SOURCE_DIR / 'frontend_files.wxs'

    # The `heat` command now targets the UI subdirectory and the FrontendFiles ComponentGroup
    run_command([
        'heat', 'dir', str(ui_staging_dir),
        '-o', str(files_wxs),
        '-gg', '-sfrag', '-srd',
        '-cg', 'FrontendFiles', # Target the correct ComponentGroup
        '-dr', 'UIDirectory',    # Target the correct Directory Id from Product.wxs
        '-var', 'var.SourceDir'
    ])
    print(f'✓ WiX file fragment for frontend created at {files_wxs}')

    # Step 4: Compile WiX project
    print("--- Step 4: Compiling WiX project with 'candle' ---")
    obj_dir = MSI_SOURCE_DIR / 'obj'
    obj_dir.mkdir(exist_ok=True)

    # We now pass the SourceDir variable pointing to the root of our staged files
    candle_cmd = [
        'candle',
        '-ext', 'WixUtilExtension',
        f'-dSourceDir={WIX_STAGING_DIR}',
        str(PROJECT_ROOT / 'build_wix' / 'Product.wxs'),
        str(files_wxs),
        '-o', f'{obj_dir}/'
    ]
    run_command(candle_cmd)
    print('✓ WiX compilation successful.')

    # Step 5: Link WiX project into MSI
    print("--- Step 5: Linking MSI with 'light' ---")
    import glob
    obj_files = glob.glob(str(obj_dir / '*.wixobj'))
    if not obj_files:
        sys.exit('✗ Linking failed: No .wixobj files found to link.')

    output_msi = DIST_DIR / 'Fortuna-Full-App-Service.msi'

    # Light command remains the same
    light_cmd = [
        'light',
        '-ext', 'WixUtilExtension',
        '-o', str(output_msi)
    ] + obj_files
    run_command(light_cmd)
    print(f'✓ MSI created successfully at {output_msi}')

    print('\n=== BUILD COMPLETE ===')

if __name__ == '__main__':
    main()
