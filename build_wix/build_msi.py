#!/usr/bin/env python3
import os
import sys
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
DIST_DIR = PROJECT_ROOT / 'dist'
BUILD_DIR = PROJECT_ROOT / 'build'
MSI_SOURCE_DIR = PROJECT_ROOT / 'build_wix' / 'msi_source'
EXECUTABLE_NAME = 'fortuna-backend.exe' if sys.platform == 'win32' else 'fortuna-backend'

def run_command(cmd, cwd=None):
    print(f'▶ Running: {" ".join(cmd)}')
    subprocess.run(cmd, cwd=cwd, check=True, text=True, encoding='utf-8', errors='ignore')

def inject_service_logic(wxs_file, exe_name):
    print(f"--- Injecting service logic into {wxs_file} for {exe_name} ---")
    try:
        ET.register_namespace('', "http://schemas.microsoft.com/wix/2006/wi")
        tree = ET.parse(wxs_file)
        root = tree.getroot()

        ns = {'wix': 'http://schemas.microsoft.com/wix/2006/wi'}

        target_component = None
        for component in root.findall('.//wix:Component', ns):
            file_element = component.find(f".//wix:File[@Source='{exe_name}']", ns)
            if file_element is not None:
                target_component = component
                break

        if target_component is None:
            sys.exit(f"✗ Could not find Component containing File with Source='{exe_name}'")

        print(f"✓ Found target component: {target_component.attrib['Id']}")

        # Add ServiceInstall element
        si = ET.SubElement(target_component, 'ServiceInstall', {
            'Id': 'ServiceInstaller', 'Type': 'ownProcess', 'Name': 'FortunaBackendService',
            'DisplayName': 'Fortuna Backend Service',
            'Description': 'Provides access to the Fortuna racing data engine.',
            'Start': 'auto', 'Account': 'LocalSystem', 'ErrorControl': 'normal'
        })

        # Add ServiceControl elements
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
    run_command(['heat', 'dir', str(heat_source_dir), '-o', str(files_wxs), '-gg', '-sfrag', '-srd', '-cg', 'MainFiles', '-var', 'var.heat_source'])
    print(f'✓ WiX file fragment created at {files_wxs}')

    # 2.5 Inject Service Logic
    inject_service_logic(str(files_wxs), EXECUTABLE_NAME)

    # 3. Compile WiX project
    print("--- Step 3: Compiling WiX project with 'candle' ---")
    obj_dir = MSI_SOURCE_DIR / 'obj'
    obj_dir.mkdir(exist_ok=True)
    candle_cmd = [
        'candle',
        '-dheat_source=' + str(heat_source_dir),
        str(PROJECT_ROOT / 'build_wix' / 'Product.wxs'),
        str(files_wxs),
        '-o', f'{obj_dir}/'
    ]
    run_command(candle_cmd)
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
