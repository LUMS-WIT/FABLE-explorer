#!/usr/bin/env bash
# Launch the FABLE Pakistan Streamlit dashboard.
# Works on Mac and Linux — no Excel required (reads existing run outputs).

set -euo pipefail
cd "$(dirname "$0")"

SCRIPT="src/dashboard.py"

if [ ! -f "$SCRIPT" ]; then
  echo "Missing: $SCRIPT"
  exit 1
fi

if [ -f ".venv/bin/python" ]; then
  echo "Starting FABLE Pakistan Dashboard..."
  .venv/bin/python -m streamlit run "$SCRIPT"
elif command -v python3 &>/dev/null; then
  echo "Starting FABLE Pakistan Dashboard..."
  python3 -m streamlit run "$SCRIPT"
elif command -v python &>/dev/null; then
  echo "Starting FABLE Pakistan Dashboard..."
  python -m streamlit run "$SCRIPT"
else
  echo ""
  echo "Could not find a working Python installation."
  echo ""
  echo "What to do:"
  echo "  1. Install Python 3.9+ (https://python.org)"
  echo "  2. Run: pip install -e . && pip install streamlit"
  echo "  3. Re-run this script."
  echo ""
  exit 1
fi
