"""
Build script to create standalone executable for Field Mapper Tool
Run this script to create a single executable file: FieldMapper.exe
"""

import PyInstaller.__main__
import os
import sys
import shutil

# Get the current directory
current_dir = os.path.dirname(os.path.abspath(__file__))

print("="*60)
print("Building Field Mapper Tool - Standalone Executable")
print("="*60)
print("\nThis will create a single executable file: FieldMapper.exe")
print("The build process may take a few minutes...\n")

# Clean previous builds
print("Cleaning previous builds...")
for folder in ['build', 'dist', '__pycache__']:
    if os.path.exists(folder):
        try:
            shutil.rmtree(folder)
            print(f"  - Removed {folder}/")
        except Exception as e:
            print(f"  - Warning: Could not remove {folder}/: {e}")

# Remove old spec file if exists
spec_file = os.path.join(current_dir, 'FieldMapper.spec')
if os.path.exists(spec_file):
    try:
        os.remove(spec_file)
        print(f"  - Removed old {spec_file}")
    except Exception as e:
        print(f"  - Warning: Could not remove spec file: {e}")

print("\nStarting PyInstaller build...\n")

# PyInstaller arguments for Windows
if sys.platform == 'win32':
    # Windows format: use semicolon (;) as separator
    data_separator = ';'
    exe_extension = '.exe'
else:
    # Linux/Mac format: use colon (:) as separator
    data_separator = ':'
    exe_extension = ''

# Build arguments
args = [
    'field_mapper.py',                    # Main script
    '--name=FieldMapper',                 # Name of the executable
    '--onefile',                          # Create a single executable file
    '--windowed',                         # No console window (GUI only)
    '--noconfirm',                        # Overwrite output directory without asking
    '--clean',                            # Clean cache before building
    
    # Include data files
    f'--add-data=database_config.py{data_separator}.',  # Include config file
    
    # Hidden imports (modules that PyInstaller might miss)
    '--hidden-import=tkinter',
    '--hidden-import=tkinter.ttk',
    '--hidden-import=tkinter.filedialog',
    '--hidden-import=tkinter.messagebox',
    '--hidden-import=tkinter.scrolledtext',
    '--hidden-import=json',
    '--hidden-import=logging',
    '--hidden-import=threading',
    '--hidden-import=datetime',
    '--hidden-import=glob',
    '--hidden-import=os',
    '--hidden-import=sys',
    '--hidden-import=subprocess',
    '--hidden-import=platform',
    '--hidden-import=json_parser',
    '--hidden-import=field_loader',
    '--hidden-import=field_comparator',
    '--hidden-import=document_parser',
    '--hidden-import=chardet',  # Optional dependency for encoding detection
    
    # Collect all dependencies for docx (if used)
    '--collect-all=docx',
    
    # Exclude unnecessary modules to reduce size
    '--exclude-module=matplotlib',
    '--exclude-module=numpy',
    '--exclude-module=pandas',
    '--exclude-module=scipy',
    '--exclude-module=PIL',
]

try:
    # Run PyInstaller
    PyInstaller.__main__.run(args)
    
    # Check if executable was created
    exe_path = os.path.join(current_dir, 'dist', f'FieldMapper{exe_extension}')
    
    if os.path.exists(exe_path):
        file_size = os.path.getsize(exe_path) / (1024 * 1024)  # Size in MB
        
        print("\n" + "="*60)
        print("✓ BUILD SUCCESSFUL!")
        print("="*60)
        print(f"\nExecutable created: {exe_path}")
        print(f"File size: {file_size:.2f} MB")
        print("\nYou can now distribute this single executable file!")
        print("No additional files or Python installation required.")
        print("\nNote: The executable may take a few seconds to start")
        print("      as it extracts files to a temporary directory.")
        print("="*60)
    else:
        print("\n" + "="*60)
        print("✗ BUILD FAILED!")
        print("="*60)
        print(f"\nExpected executable not found at: {exe_path}")
        print("Please check the build output above for errors.")
        print("="*60)
        sys.exit(1)
        
except Exception as e:
    print("\n" + "="*60)
    print("✗ BUILD ERROR!")
    print("="*60)
    print(f"\nError during build: {str(e)}")
    print("\nPlease ensure:")
    print("  1. PyInstaller is installed: pip install pyinstaller")
    print("  2. All dependencies are installed: pip install -r requirements.txt")
    print("  3. You have write permissions in this directory")
    print("="*60)
    sys.exit(1)
