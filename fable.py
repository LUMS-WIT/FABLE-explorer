#!/usr/bin/env python
"""
FABLE Pakistan — unified entry point.

Commands:
  python fable.py run              Run all pathways (needs Excel)
  python fable.py dashboard        Launch the Streamlit dashboard

Pass --help after any command to see its options:
  python fable.py run --help
"""

import subprocess
import sys
from pathlib import Path

_SRC = Path(__file__).parent / "src"

_USAGE = """\
Usage: python fable.py <command> [options]

Commands:
  run         Run all pathways in the FABLE workbook and export CSVs
              (requires Excel to be installed)
  dashboard   Launch the interactive Streamlit dashboard
  launcher    Launch the Tkinter GUI launcher

Examples:
  python fable.py run
  python fable.py run --max-pathways 2   # quick test with first 2 pathways
  python fable.py run --excel-visible    # show Excel window while running
  python fable.py dashboard
  python fable.py launcher
"""


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(_USAGE)
        sys.exit(0)

    cmd, *rest = sys.argv[1:]

    if cmd == "run":
        subprocess.run(
            [sys.executable, str(_SRC / "runner.py")] + rest,
            check=True,
        )
    elif cmd == "dashboard":
        subprocess.run(
            ["streamlit", "run", str(_SRC / "dashboard.py")] + rest,
            check=True,
        )
    elif cmd == "launcher":
        subprocess.run(
            [sys.executable, str(_SRC / "launcher.py")] + rest,
            check=True,
        )
    else:
        print(f"Unknown command: {cmd!r}")
        print(_USAGE)
        sys.exit(1)


if __name__ == "__main__":
    main()
