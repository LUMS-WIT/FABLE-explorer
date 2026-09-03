"""LibreOffice headless engine (no Excel licence, CI/container friendly).

Strategy
--------
1. Copy the workbook to a scratch dir (never mutate the upload).
2. Start ``soffice --headless --norestore`` with a private user profile.
3. For each pathway row in the ``PathwaysSelection`` table:
     * clear the SELECTION column, put ``x`` on the pathway's row,
     * ``calculateAll()``,
     * read every named table range on the nine output sheets,
     * append rows (tagged with ``RunPathway``) to the per-pathway and
       combined CSVs — exact same layout the xlwings engine emits.
4. Write ``run_manifest.csv`` (status per pathway) and quit soffice.

Steps 2-3 run inside LibreOffice through a Python-UNO macro
(``_uno_macro.py``, invoked with ``soffice ... "vnd.sun.star.script:..."``).
Fidelity against real Excel is verified by ``fable/tests`` golden data before
this engine is trusted for a country.

Status: interface + environment probe are complete; the UNO macro is tracked in
``fable/contract/CONTRACT.md`` under "LibreOffice engine". Until it lands,
``recalc_all`` raises :class:`EngineUnavailable` with a clear message so callers
fall back to ``xlwings`` or to an already-exported CSV run directory.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

from . import EngineUnavailable, ProgressCallback

_CANDIDATE_BINARIES = (
    "soffice",
    "libreoffice",
    "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    "/usr/bin/soffice",
    "/usr/lib/libreoffice/program/soffice",
)


def find_soffice() -> Optional[str]:
    for cand in _CANDIDATE_BINARIES:
        found = shutil.which(cand) if "/" not in cand else (cand if Path(cand).exists() else None)
        if found:
            return found
    return None


class LibreOfficeEngine:
    name = "libreoffice"

    def __init__(self) -> None:
        self.soffice = find_soffice()

    def available(self) -> tuple[bool, str]:
        if not self.soffice:
            return False, "soffice / libreoffice binary not found on PATH"
        # The probe passes; the recalc macro is not wired up yet.
        return False, "LibreOffice found, but the UNO recalc macro is not implemented yet"

    def recalc_all(
        self,
        workbook_path: Path,
        output_root: Path,
        *,
        max_pathways: Optional[int] = None,
        workers: int = 1,
        pathway_slice: Optional[tuple[int, int]] = None,
        excel_visible: bool = False,
        run_dir: Optional[Path] = None,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> Path:
        raise EngineUnavailable(
            "LibreOffice engine is not implemented yet. Use the xlwings engine, "
            "or pass an already-exported CSV run directory to `fable bundle`."
        )
