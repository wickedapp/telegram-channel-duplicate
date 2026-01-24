#!/usr/bin/env python3
"""
Build script for Telegram Channel Duplicator Windows Installer

This script automates the build process:
1. Cleans up previous builds
2. Obfuscates source code with PyArmor
3. Bundles everything with PyInstaller

Usage:
    python installer/build_installer.py

Requirements:
    - PyArmor 9.x: pip install pyarmor
    - PyInstaller: pip install pyinstaller
"""

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path


# Configuration
APP_NAME = "Telegram转发助手"

# Directories
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
SRC_DIR = PROJECT_ROOT / "src"
INSTALLER_DIR = PROJECT_ROOT / "installer"
DIST_OBFUSCATED = PROJECT_ROOT / "dist_obfuscated"
DIST_DIR = PROJECT_ROOT / "dist"
BUILD_DIR = PROJECT_ROOT / "build"

# Files to include
CONFIG_TEMPLATE = PROJECT_ROOT / "config.yaml.template"
ENV_TEMPLATE = PROJECT_ROOT / ".env.template"
ASSETS_DIR = INSTALLER_DIR / "assets"


def print_step(step_num: int, message: str) -> None:
    """Print a formatted step message."""
    print(f"\n{'='*60}")
    print(f"Step {step_num}: {message}")
    print('='*60)


def print_info(message: str) -> None:
    """Print an info message."""
    print(f"[INFO] {message}")


def print_error(message: str) -> None:
    """Print an error message."""
    print(f"[ERROR] {message}", file=sys.stderr)


def print_success(message: str) -> None:
    """Print a success message."""
    print(f"[SUCCESS] {message}")


def get_path_separator() -> str:
    """Get the correct path separator for PyInstaller --add-data."""
    # Windows uses ';', Unix uses ':'
    return ';' if platform.system() == 'Windows' else ':'


def run_command(cmd: list[str], description: str, cwd: Path = None) -> bool:
    """
    Run a command and return True on success, False on failure.

    Args:
        cmd: Command and arguments as a list
        description: Human-readable description of what the command does
        cwd: Working directory for the command

    Returns:
        True if command succeeded, False otherwise
    """
    print_info(f"Running: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            cwd=cwd or PROJECT_ROOT,
            check=True,
            capture_output=False,  # Show output in real-time
        )
        return True
    except subprocess.CalledProcessError as e:
        print_error(f"{description} failed with exit code {e.returncode}")
        return False
    except FileNotFoundError:
        print_error(f"Command not found: {cmd[0]}")
        print_error(f"Please install it with: pip install {cmd[0]}")
        return False


def clean_previous_builds() -> None:
    """Remove previous build artifacts."""
    print_step(2, "Cleaning previous builds")

    dirs_to_clean = [DIST_OBFUSCATED, DIST_DIR, BUILD_DIR]

    for dir_path in dirs_to_clean:
        if dir_path.exists():
            print_info(f"Removing {dir_path}")
            shutil.rmtree(dir_path)
        else:
            print_info(f"Directory does not exist, skipping: {dir_path}")

    # Also clean any .spec files
    for spec_file in PROJECT_ROOT.glob("*.spec"):
        print_info(f"Removing {spec_file}")
        spec_file.unlink()

    print_success("Cleanup complete")


def install_package(package: str) -> bool:
    """Install a Python package using pip."""
    print_info(f"Installing {package}...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", package],
            capture_output=False,
            check=True,
        )
        return True
    except subprocess.CalledProcessError:
        print_error(f"Failed to install {package}")
        return False


def install_requirements() -> bool:
    """Install all requirements from requirements.txt."""
    print_step(0, "Installing dependencies")

    requirements_file = PROJECT_ROOT / "requirements.txt"
    if not requirements_file.exists():
        print_error("requirements.txt not found")
        return False

    print_info("Installing packages from requirements.txt...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", str(requirements_file)],
            capture_output=False,
            check=True,
        )
        print_success("All dependencies installed")
        return True
    except subprocess.CalledProcessError:
        print_error("Failed to install dependencies from requirements.txt")
        return False


def check_prerequisites() -> bool:
    """Check that required tools are installed, install if missing."""
    print_step(1, "Checking prerequisites")

    # Check Python version
    print_info(f"Python version: {sys.version}")

    # Check PyArmor (PyArmor 9.x uses 'pyarmor' command directly)
    pyarmor_ok = False
    try:
        result = subprocess.run(
            ["pyarmor", "--version"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            version = result.stdout.strip().split('\n')[0] or result.stderr.strip().split('\n')[0]
            print_info(f"PyArmor: {version}")
            pyarmor_ok = True
    except FileNotFoundError:
        pass

    if not pyarmor_ok:
        print_info("PyArmor not found, installing...")
        if not install_package("pyarmor"):
            return False
        print_success("PyArmor installed")

    # Check PyInstaller
    pyinstaller_ok = False
    try:
        result = subprocess.run(
            [sys.executable, "-m", "PyInstaller", "--version"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print_info(f"PyInstaller: {result.stdout.strip()}")
            pyinstaller_ok = True
    except FileNotFoundError:
        pass

    if not pyinstaller_ok:
        print_info("PyInstaller not found, installing...")
        if not install_package("pyinstaller"):
            return False
        print_success("PyInstaller installed")

    # Check required files exist
    required_files = [
        (SRC_DIR, "src/ directory"),
        (INSTALLER_DIR / "tray_app.py", "installer/tray_app.py"),
        (INSTALLER_DIR / "assets" / "icon.ico", "installer/assets/icon.ico"),
        (CONFIG_TEMPLATE, "config.yaml.template"),
        (ENV_TEMPLATE, ".env.template"),
    ]

    all_present = True
    for path, description in required_files:
        if path.exists():
            print_info(f"Found: {description}")
        else:
            print_error(f"Missing: {description}")
            all_present = False

    if not all_present:
        return False

    print_success("All prerequisites met")
    return True


def run_pyarmor_obfuscation() -> bool:
    """Run PyArmor to obfuscate the source code."""
    print_step(3, "Obfuscating source code with PyArmor")

    # PyArmor 9.x command (uses 'pyarmor' directly)
    cmd = [
        "pyarmor",
        "gen",
        "--output", str(DIST_OBFUSCATED),
        str(SRC_DIR),
        str(INSTALLER_DIR),
    ]

    if not run_command(cmd, "PyArmor obfuscation"):
        return False

    # Verify obfuscation output
    obfuscated_src = DIST_OBFUSCATED / "src"
    obfuscated_installer = DIST_OBFUSCATED / "installer"

    if not obfuscated_src.exists():
        print_error(f"Obfuscated src/ not found at {obfuscated_src}")
        return False

    if not obfuscated_installer.exists():
        print_error(f"Obfuscated installer/ not found at {obfuscated_installer}")
        return False

    print_success("Source code obfuscated successfully")
    return True


def run_pyinstaller_bundle() -> bool:
    """Run PyInstaller to create the executable bundle."""
    print_step(4, "Bundling with PyInstaller")

    sep = get_path_separator()

    # Hidden imports required because PyArmor obfuscation hides them from PyInstaller
    hidden_imports = [
        # Standard library
        "asyncio",
        "asyncio.base_events",
        "asyncio.events",
        "asyncio.futures",
        "asyncio.locks",
        "asyncio.protocols",
        "asyncio.queues",
        "asyncio.runners",
        "asyncio.streams",
        "asyncio.tasks",
        "asyncio.transports",
        "asyncio.windows_events",
        "asyncio.windows_utils",
        "concurrent.futures",
        "threading",
        "queue",
        "logging",
        "logging.handlers",
        "json",
        "re",
        "pathlib",
        "webbrowser",
        "subprocess",
        "signal",
        "tkinter",
        "tkinter.ttk",
        "tkinter.messagebox",
        "tkinter.scrolledtext",
        # Third-party packages
        "telethon",
        "telethon.client",
        "telethon.events",
        "telethon.tl",
        "telethon.tl.types",
        "telethon.errors",
        "telethon.sessions",
        "pystray",
        "pystray._base",
        "pystray._win32",
        "PIL",
        "PIL.Image",
        "PIL.ImageDraw",
        "yaml",
        "dotenv",
        "mysql",
        "mysql.connector",
        # Local modules
        "config_manager",
        "db_config",
        "message_logger",
        "setup_wizard",
        "config",
        "duplicator",
        "filters",
        "transformer",
        # PyArmor runtime
        "pyarmor_runtime_000000",
    ]

    # Build the PyInstaller command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        f"--name={APP_NAME}",
        f"--icon={INSTALLER_DIR / 'assets' / 'icon.ico'}",
        # Add obfuscated source code (src modules)
        f"--add-data={DIST_OBFUSCATED / 'src'}{sep}src",
        # Add obfuscated installer modules
        f"--add-data={DIST_OBFUSCATED / 'installer'}{sep}installer",
        # Add config templates
        f"--add-data={CONFIG_TEMPLATE}{sep}.",
        f"--add-data={ENV_TEMPLATE}{sep}.",
        # Add assets
        f"--add-data={ASSETS_DIR}{sep}assets",
        # Add PyArmor runtime
        f"--add-data={DIST_OBFUSCATED / 'pyarmor_runtime_000000'}{sep}pyarmor_runtime_000000",
        # No console window (GUI app)
        "--noconsole",
        # Clean build
        "--clean",
        # Confirm yes to overwrite
        "-y",
    ]

    # Add all hidden imports
    for module in hidden_imports:
        cmd.append(f"--hidden-import={module}")

    # Collect all submodules for these packages
    collect_all_packages = [
        "telethon",
        "pystray",
        "PIL",
        "yaml",
        "dotenv",
    ]
    for pkg in collect_all_packages:
        cmd.append(f"--collect-all={pkg}")

    # Entry point (obfuscated tray_app.py)
    cmd.append(str(DIST_OBFUSCATED / "installer" / "tray_app.py"))

    print_info(f"Path separator for this platform: '{sep}'")

    if not run_command(cmd, "PyInstaller bundling"):
        return False

    # Verify output
    if platform.system() == "Windows":
        exe_path = DIST_DIR / APP_NAME / f"{APP_NAME}.exe"
    else:
        # On macOS/Linux, PyInstaller creates different structures
        exe_path = DIST_DIR / APP_NAME / APP_NAME
        if not exe_path.exists():
            # macOS might create .app bundle
            exe_path = DIST_DIR / f"{APP_NAME}.app"

    if not DIST_DIR.exists():
        print_error(f"Distribution directory not found at {DIST_DIR}")
        return False

    print_success("PyInstaller bundling complete")
    return True


def print_summary() -> None:
    """Print build summary."""
    print(f"\n{'='*60}")
    print("BUILD COMPLETE")
    print('='*60)

    # Find the output
    if (DIST_DIR / APP_NAME).exists():
        output_dir = DIST_DIR / APP_NAME
        print_info(f"Output directory: {output_dir}")

        # List contents
        print_info("Contents:")
        for item in output_dir.iterdir():
            size = ""
            if item.is_file():
                size_bytes = item.stat().st_size
                if size_bytes > 1024 * 1024:
                    size = f" ({size_bytes / 1024 / 1024:.1f} MB)"
                elif size_bytes > 1024:
                    size = f" ({size_bytes / 1024:.1f} KB)"
                else:
                    size = f" ({size_bytes} bytes)"
            print(f"  - {item.name}{size}")

    print(f"\nTo run the application:")
    if platform.system() == "Windows":
        print(f"  {DIST_DIR / APP_NAME / APP_NAME}.exe")
    else:
        print(f"  {DIST_DIR / APP_NAME / APP_NAME}")


def main() -> int:
    """
    Main build process.

    Returns:
        0 on success, 1 on failure
    """
    print(f"""
{'='*60}
Telegram Channel Duplicator - Build Script
{'='*60}
Platform: {platform.system()} {platform.release()}
Python: {sys.version.split()[0]}
Project Root: {PROJECT_ROOT}
""")

    # Change to project root
    os.chdir(PROJECT_ROOT)
    print_info(f"Working directory: {os.getcwd()}")

    # Install dependencies from requirements.txt
    if not install_requirements():
        print_error("Failed to install dependencies.")
        return 1

    # Check prerequisites (and install build tools if missing)
    if not check_prerequisites():
        print_error("Prerequisites check failed.")
        return 1

    # Clean previous builds
    clean_previous_builds()

    # Run PyArmor obfuscation
    if not run_pyarmor_obfuscation():
        print_error("PyArmor obfuscation failed.")
        return 1

    # Run PyInstaller bundling
    if not run_pyinstaller_bundle():
        print_error("PyInstaller bundling failed.")
        return 1

    # Print summary
    print_summary()

    return 0


if __name__ == "__main__":
    sys.exit(main())
