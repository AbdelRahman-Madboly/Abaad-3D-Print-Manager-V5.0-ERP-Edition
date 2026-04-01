#!/bin/bash
# Abaad 3D Print Manager v5.0 — Setup (macOS / Linux)

set -e

echo ""
echo " Abaad 3D Print Manager v5.0 - Setup"
echo " ======================================"
echo ""

# Verify python3 is available
if ! command -v python3 &> /dev/null; then
    echo " ERROR: python3 was not found on your system."
    echo ""
    echo " Install Python 3.10+ using your package manager, for example:"
    echo "   macOS:  brew install python"
    echo "   Ubuntu: sudo apt install python3"
    echo "   Fedora: sudo dnf install python3"
    echo ""
    exit 1
fi

# Run the cross-platform installer
python3 scripts/install.py

# Ensure the launch script is executable after install
if [ -f "launch.sh" ]; then
    chmod +x launch.sh
    echo "  launch.sh marked as executable"
fi

echo ""