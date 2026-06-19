#!/usr/bin/env bash
# Launch the FABLE Pakistan GUI launcher.
# NOTE: The "Run Dashboard" button requires Windows + Microsoft Excel.
#       On Mac/Linux, the GUI will open but pathway execution will fail.
#       Use launch_dashboard.sh instead to explore existing run outputs.

set -euo pipefail
cd "$(dirname "$0")"

SCRIPT="src/launcher.py"

if [ ! -f "$SCRIPT" ]; then
  echo "Missing: $SCRIPT"
  exit 1
fi

if [ -f ".venv/bin/python" ]; then
  echo "Starting FABLE Pakistan Launcher..."
  .venv/bin/python "$SCRIPT"
elif command -v python3 &>/dev/null; then
  echo "Starting FABLE Pakistan Launcher..."
  python3 "$SCRIPT"
elif command -v python &>/dev/null; then
  echo "Starting FABLE Pakistan Launcher..."
  python "$SCRIPT"
else
  echo ""
  echo "Could not find a working Python installation."
  echo ""
  echo "What to do:"
  echo "  1. Install Python 3.9+ (https://python.org)"
  echo "  2. Run: pip install -e ."
  echo "  3. Re-run this script."
  echo ""
  exit 1
fi
