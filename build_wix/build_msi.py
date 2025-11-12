#!/usr/bin/env python3
import os
import sys
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DIST_DIR = PROJECT_ROOT / 'dist'
FRONTEND_BUILD_DIR = PROJECT_ROOT / 'frontend_build'
WIX_STAGING_DIR = PROJECT_ROOT / 'build_wix' / 'staging'
MSI_SOURCE_DIR = PROJECT_ROOT / 'build_wix' / 'msi_source'
EXECUTABLE_NAME = 'fortuna-backend.exe'

def run_command(cmd, cwd=None):
    print(f'▶ Running: {" ".join(cmd)}')
    subprocess.run(cmd, cwd=cwd, check=True, text=True, encoding='utf-8', errors='ignore')

def inject_service_logic(wxs_file, exe_name):
    # (function remains the same as before)
    print(f"--- Injecting service logic into {wxs_file} for {exe_name} ---")
    try:
        ET.register_namespace('', "http://schemas.microsoft.com/wix/2006/wi")
        tree = ET.parse(wxs_file)
        root = tree.getroot()
        ns = {'wix': 'http://schemas.microsoft.com/wix/2006/wi'}
        target_component = None
        for component in root.findall('.//wix:Component', ns):
            file_element = component.find(f".//wix:File[@Source='.\\{exe_name}']", ns)
            if file_element is not None:
                target_component = component
                break
        if target_component is None:
             sys.exit(f"✗ Could not find Component containing File with Source='.\\{exe_name}'")
        print(f"✓ Found target component: {target_component.attrib['Id']}")
        si = ET.SubElement(target_component, 'ServiceInstall', {
            'Id': 'ServiceInstaller', 'Type': 'ownProcess', 'Name': 'FortunaBackendService',
            'DisplayName': 'Fortuna Backend Service',
            'Description': 'Provides access to the Fortuna racing data engine.',
            'Start': 'auto', 'Account': 'LocalSystem', 'ErrorControl': 'normal'
        })
        ET.SubElement(target_component, 'ServiceControl', {
            'Id': 'StartService', 'Name': 'FortunaBackendService', 'Start': 'install', 'Wait': 'no'
        })
        ET.SubElement(target_component, 'ServiceControl', {
            'Id': 'StopService', 'Name': 'FortunaBackendService', 'Stop': 'both', 'Remove': 'uninstall', 'Wait': 'yes'
        })
        tree.write(wxs_file, encoding='utf-8', xml_declaration=True)
        print("✓ Service logic injected successfully.")
    except Exception as e:
        sys.exit(f"✗ Failed to inject service logic: {e}")

def main():
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
    WIX_STAGING_DIR.mkdir()

    # Copy backend and frontend to staging
    shutil.copy(exe_path, WIX_STAGING_DIR / EXECUTABLE_NAME)
    shutil.copytree(FRONTEND_BUILD_DIR, WIX_STAGING_DIR / 'ui')
    print('✓ All assets copied to staging directory.')

    # Step 3. Generate WiX file list from the staging directory
    print("--- Step 3: Generating WiX file list with 'heat' ---")
    MSI_SOURCE_DIR.mkdir(exist_ok=True)
    files_wxs = MSI_SOURCE_DIR / 'files.wxs'
    run_command([
        'heat', 'dir', str(WIX_STAGING_DIR),
        '-o', str(files_wxs),
        '-gg', '-sfrag', '-srd',
        '-cg', 'MainFilesGroup',
        '-dr', 'INSTALLFOLDER',
        '-var', 'var.SourceDir'
    ])
    print(f'✓ WiX file fragment created at {files_wxs}')

    # Step 4: Inject Service Logic
    inject_service_logic(str(files_wxs), EXECUTABLE_NAME)

    # Step 5: Compile WiX project
    print("--- Step 5: Compiling WiX project with 'candle' ---")
    obj_dir = MSI_SOURCE_DIR / 'obj'
    obj_dir.mkdir(exist_ok=True)
    candle_cmd = [
        'candle',
        f'-dSourceDir={WIX_STAGING_DIR}',
        str(PROJECT_ROOT / 'build_wix' / 'Product.wxs'),
        str(files_wxs),
        '-o', f'{obj_dir}/'
    ]
    run_command(candle_cmd)
    print('✓ WiX compilation successful.')

    # Step 6: Link WiX project into MSI
    print("--- Step 6: Linking MSI with 'light' ---")
    import glob
    obj_files = glob.glob(str(obj_dir / '*.wixobj'))
    if not obj_files:
        sys.exit('✗ Linking failed: No .wixobj files found to link.')

    output_msi = DIST_DIR / 'Fortuna-Full-App-Service.msi'

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
