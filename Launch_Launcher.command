#!/bin/bash
# FABLE launcher (macOS). Double-click in Finder to open the desktop launcher.
cd "$(dirname "$0")" || exit 1
if [ -x ".venv/bin/python" ]; then PY=".venv/bin/python"; else PY="python3"; fi
"$PY" src/launcher.py || {
  echo
  echo "The launcher did not start. Install the tool first:"
  echo "    python3 -m venv .venv && source .venv/bin/activate"
  echo "    pip install -e \".[excel]\""
  read -r -p "Press Enter to close."
}
