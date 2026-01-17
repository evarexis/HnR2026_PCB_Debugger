#!/usr/bin/env python3
"""
Automated build script for PCB Bring-Up Assistant
Builds standalone executables for distribution
"""

import os
import sys
import platform
import subprocess
import shutil
from pathlib import Path

class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_header(msg):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}{Colors.ENDC}\n")

def print_success(msg):
    print(f"{Colors.OKGREEN}✓ {msg}{Colors.ENDC}")

def print_error(msg):
    print(f"{Colors.FAIL}✗ {msg}{Colors.ENDC}")

def print_info(msg):
    print(f"{Colors.OKBLUE}ℹ {msg}{Colors.ENDC}")

def run_command(cmd, description):
    """Run a shell command and handle errors"""
    print_info(f"{description}...")
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        print_success(f"{description} - Done")
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"{description} - Failed")
        print(f"Error: {e.stderr}")
        return False

def check_dependencies():
    """Check if required dependencies are installed"""
    print_header("Checking Dependencies")
    
    dependencies = {
        'wxPython': 'wx',
        'sexpdata': 'sexpdata',
        'pydantic': 'pydantic',
        'PyInstaller': 'PyInstaller'
    }
    
    missing = []
    for name, module in dependencies.items():
        try:
            __import__(module)
            print_success(f"{name} is installed")
        except ImportError:
            print_error(f"{name} is NOT installed")
            missing.append(name)
    
    if missing:
        print_error(f"\nMissing dependencies: {', '.join(missing)}")
        print_info("Install with: pip install " + " ".join(missing))
        return False
    
    return True

def clean_build():
    """Clean previous build artifacts"""
    print_header("Cleaning Build Artifacts")
    
    dirs_to_clean = ['build', 'dist', '__pycache__']
    files_to_clean = ['*.spec']
    
    for dirname in dirs_to_clean:
        if os.path.exists(dirname):
            shutil.rmtree(dirname)
            print_success(f"Removed {dirname}/")
    
    for pattern in files_to_clean:
        for filepath in Path('.').glob(pattern):
            if filepath.name != 'build_executable.spec':  # Keep our spec file
                filepath.unlink()
                print_success(f"Removed {filepath}")

def build_executable():
    """Build the standalone executable"""
    print_header("Building Standalone Executable")
    
    system = platform.system()
    print_info(f"Building for {system}")
    
    # Determine build command based on OS
    if system == "Windows":
        separator = ";"
        exe_name = "PCB_BringUp_Assistant.exe"
    else:
        separator = ":"
        exe_name = "PCB_BringUp_Assistant"
    
    # Check if we have a custom spec file
    if os.path.exists("build_executable.spec"):
        print_info("Using custom build_executable.spec")
        cmd = "pyinstaller build_executable.spec"
    else:
        # Build with command line options
        cmd = (
            f"pyinstaller "
            f"--onefile "
            f"--windowed "
            f"--name PCB_BringUp_Assistant "
            f"run_bringup_assistant.py"
        )
        
        # Add icon if it exists
        if os.path.exists("icon.ico") and system == "Windows":
            cmd += " --icon=icon.ico"
        elif os.path.exists("icon.icns") and system == "Darwin":
            cmd += " --icon=icon.icns"
        
        # Add data files
        if os.path.exists("icon.png"):
            cmd += f" --add-data icon.png{separator}."
        if os.path.exists("README.md"):
            cmd += f" --add-data README.md{separator}."
    
    if not run_command(cmd, "Building executable"):
        return False
    
    # Check if executable was created
    exe_path = Path("dist") / exe_name
    if system == "Darwin":
        exe_path = Path("dist") / "PCB_BringUp_Assistant.app"
    
    if exe_path.exists():
        print_success(f"Executable created: {exe_path}")
        
        # Make executable on Unix systems
        if system in ["Linux", "Darwin"] and exe_path.suffix != ".app":
            os.chmod(exe_path, 0o755)
            print_success("Made executable")
        
        return True
    else:
        print_error("Executable was not created")
        return False

def test_executable():
    """Test the built executable"""
    print_header("Testing Executable")
    
    system = platform.system()
    if system == "Windows":
        exe_path = Path("dist") / "PCB_BringUp_Assistant.exe"
    elif system == "Darwin":
        exe_path = Path("dist") / "PCB_BringUp_Assistant.app" / "Contents" / "MacOS" / "PCB_BringUp_Assistant"
    else:
        exe_path = Path("dist") / "PCB_BringUp_Assistant"
    
    if not exe_path.exists():
        print_error("Executable not found for testing")
        return False
    
    print_info(f"Executable location: {exe_path}")
    print_info(f"Executable size: {exe_path.stat().st_size / 1024 / 1024:.2f} MB")
    print_success("Build completed successfully!")
    
    return True

def create_installer():
    """Create installer package (optional)"""
    print_header("Creating Installer (Optional)")
    
    system = platform.system()
    
    if system == "Windows":
        print_info("For Windows installer, use Inno Setup or NSIS")
        print_info("See INSTALLATION.md for instructions")
    elif system == "Darwin":
        print_info("For macOS DMG, use create-dmg")
        print_info("Example: create-dmg dist/PCB_BringUp_Assistant.app")
    else:
        print_info("For Linux, create .deb or .rpm packages")
        print_info("See INSTALLATION.md for instructions")

def main():
    """Main build process"""
    print_header("PCB Bring-Up Assistant - Build Script")
    print_info(f"Platform: {platform.system()} {platform.machine()}")
    print_info(f"Python: {sys.version.split()[0]}")
    
    # Step 1: Check dependencies
    if not check_dependencies():
        print_error("\nBuild failed: Missing dependencies")
        return 1
    
    # Step 2: Clean previous builds
    clean_build()
    
    # Step 3: Build executable
    if not build_executable():
        print_error("\nBuild failed: Could not create executable")
        return 1
    
    # Step 4: Test executable
    if not test_executable():
        print_error("\nBuild failed: Executable test failed")
        return 1
    
    # Step 5: Optional installer creation
    create_installer()
    
    print_header("Build Complete!")
    print_success("Your executable is ready in the dist/ folder")
    print_info("\nNext steps:")
    print("  1. Test the executable on your system")
    print("  2. Test on a clean system without Python installed")
    print("  3. Create installer package for distribution (optional)")
    print("  4. Share with users!\n")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())