"""
scripts/install.py
==================
Cross-platform installer for Abaad 3D Print Manager v5.0.
Stdlib only — no third-party imports.

Steps
-----
1. Check Python >= 3.10
2. Create venv/ in project root
3. Install requirements.txt into the venv
4. (Database is created automatically on first launch by DatabaseManager)
5. Print success summary with launch instructions

Phase 2 changes:
  - Removed Step 4 "Database setup / migration" — the v5 SQLite database is
    created automatically on first launch by DatabaseManager; no migration
    script is needed for fresh installs.
"""

import os
import subprocess
import sys
import platform
from pathlib import Path

# ---------------------------------------------------------------------------
# ANSI colour helpers
# ---------------------------------------------------------------------------

_RESET  = "\033[0m"
_GREEN  = "\033[32m"
_RED    = "\033[31m"
_YELLOW = "\033[33m"
_BOLD   = "\033[1m"

if platform.system() == "Windows":
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        _RESET = _GREEN = _RED = _YELLOW = _BOLD = ""


def ok(msg: str) -> None:
    print(f"{_GREEN}✓{_RESET}  {msg}")


def err(msg: str) -> None:
    print(f"{_RED}✗{_RESET}  {msg}")


def warn(msg: str) -> None:
    print(f"{_YELLOW}⚠{_RESET}  {msg}")


def header(msg: str) -> None:
    print(f"\n{_BOLD}{msg}{_RESET}")


# ---------------------------------------------------------------------------
# Project root
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
VENV_DIR     = PROJECT_ROOT / "venv"
REQS_FILE    = PROJECT_ROOT / "requirements.txt"

IS_WINDOWS   = platform.system() == "Windows"
DOWNLOAD_URL = "https://www.python.org/downloads/"


def _find_venv_python() -> str:
    candidates = []
    if IS_WINDOWS:
        candidates = [
            VENV_DIR / "Scripts" / "python.exe",
            VENV_DIR / "Scripts" / "python3.exe",
            VENV_DIR / "bin"     / "python.exe",
            VENV_DIR / "bin"     / "python",
        ]
    else:
        candidates = [
            VENV_DIR / "bin" / "python",
            VENV_DIR / "bin" / "python3",
        ]

    for p in candidates:
        if p.exists():
            return str(p)

    return sys.executable


# ---------------------------------------------------------------------------
# Step 1 — Python version check
# ---------------------------------------------------------------------------

def check_python() -> None:
    header("Step 1 — Checking Python version")
    major, minor = sys.version_info[:2]
    version_str  = f"{major}.{minor}.{sys.version_info.micro}"
    if (major, minor) < (3, 10):
        err(
            f"Python {version_str} found, but 3.10+ is required.\n"
            f"   Download a newer version from: {DOWNLOAD_URL}"
        )
        sys.exit(1)
    ok(f"Python {version_str} — OK")


# ---------------------------------------------------------------------------
# Step 2 — Create virtual environment
# ---------------------------------------------------------------------------

def create_venv() -> None:
    header("Step 2 — Creating virtual environment")
    if VENV_DIR.exists():
        warn(f"venv/ already exists at {VENV_DIR} — skipping creation")
        return
    try:
        subprocess.check_call([sys.executable, "-m", "venv", str(VENV_DIR)])
        ok(f"Virtual environment created at {VENV_DIR}")
    except subprocess.CalledProcessError as exc:
        err(f"Failed to create virtual environment: {exc}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Step 3 — Install requirements
# ---------------------------------------------------------------------------

def install_requirements() -> None:
    header("Step 3 — Installing dependencies")
    if not REQS_FILE.exists():
        err(f"requirements.txt not found at {REQS_FILE}")
        sys.exit(1)

    python = _find_venv_python()
    if python == sys.executable:
        warn(f"Using Python: {python}")
    else:
        ok(f"Venv Python: {python}")

    try:
        subprocess.call(
            [python, "-m", "pip", "install", "--upgrade", "pip"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.check_call(
            [python, "-m", "pip", "install", "-r", str(REQS_FILE)]
        )
        ok("All dependencies installed")
    except subprocess.CalledProcessError as exc:
        err(f"Dependency installation failed: {exc}")
        sys.exit(1)


# ---------------------------------------------------------------------------
# Step 4 — Database note (no action needed)
# ---------------------------------------------------------------------------

def note_database() -> None:
    header("Step 4 — Database")
    ok("The v5 SQLite database is created automatically on first launch — "
       "no migration required.")


# ---------------------------------------------------------------------------
# Step 5 — Success summary
# ---------------------------------------------------------------------------

def print_success() -> None:
    header("Installation complete!")
    print()
    if IS_WINDOWS:
        print("  To launch the application:")
        print(f"    {_BOLD}Launch_App.bat{_RESET}")
        print()
        print("  Or manually:")
        print(f"    {_BOLD}venv\\Scripts\\activate{_RESET}")
        print(f"    {_BOLD}python main.py{_RESET}")
    else:
        print("  To launch the application:")
        print(f"    {_BOLD}./launch.sh{_RESET}")
        print()
        print("  Or manually:")
        print(f"    {_BOLD}source venv/bin/activate{_RESET}")
        print(f"    {_BOLD}python main.py{_RESET}")

    print()
    print(f"  Default login:  admin / admin123")
    print(f"  {_YELLOW}⚠  Change the default password after first login!{_RESET}")
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"\n{_BOLD}Abaad 3D Print Manager v5.0 — Installer{_RESET}")
    print("=" * 44)

    check_python()
    create_venv()
    install_requirements()
    note_database()
    print_success()


if __name__ == "__main__":
    main()
