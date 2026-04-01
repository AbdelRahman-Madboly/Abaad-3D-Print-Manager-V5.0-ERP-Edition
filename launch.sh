#!/bin/bash
# Abaad 3D Print Manager v5.0 — Daily launcher (macOS / Linux)

# Locate the script's own directory so it works from any cwd
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activate virtual environment
if [ ! -f "venv/bin/activate" ]; then
    echo "ERROR: Virtual environment not found."
    echo "Please run ./setup.sh first."
    exit 1
fi

source venv/bin/activate

# Launch the application
python main.py