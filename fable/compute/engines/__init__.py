"""Recalc-engine interface + registry.

An engine takes a FABLE workbook and produces a *CSV run directory* (the layout
consumed by :mod:`fable.compute.bundle`). Everything spreadsheet-specific and
fragile lives behind this boundary, so a new engine can be added — or a broken
one swapped out — without touching the contract, the bundle builder, or the
viewer.

Engines
-------
``xlwings``      Drives desktop Excel via COM. Highest fidelity, needs Excel +
                Windows/macOS. Wraps the legacy ``src/runner.py``.
``libreoffice`` Drives ``soffice --headless`` via a UNO macro. Runs on Linux /
                CI / containers, no Excel licence. Fidelity must be checked with
                the golden tests before trusting it.
``auto``        First engine whose :meth:`RecalcEngine.available` returns True,
                in the order (xlwings, libreoffice).
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional, Protocol, runtime_checkable

ProgressCallback = Callable[[int, int, str, str], None]


class EngineUnavailable(RuntimeError):
    """Raised by an engine that cannot run in the current environment."""


@runtime_checkable
class RecalcEngine(Protocol):
    name: str

    def available(self) -> tuple[bool, str]:
        """Return (usable_here, human_reason)."""

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
        """Recalc every selected pathway; return the CSV run directory.

        ``workers``        parallel spreadsheet processes (engine may ignore).
        ``pathway_slice``  ``(start, stop)`` index range for multi-machine sharding.
        ``run_dir``        reuse/resume an existing run directory.
        """


_ORDER = ("xlwings", "libreoffice")


def get_engine(name: str) -> RecalcEngine:
    name = name.lower()
    if name == "auto":
        return _auto()
    if name == "xlwings":
        from .xlwings_engine import XlwingsEngine

        return XlwingsEngine()
    if name == "libreoffice":
        from .libreoffice_engine import LibreOfficeEngine

        return LibreOfficeEngine()
    raise ValueError(f"unknown engine {name!r}; choose from auto, {', '.join(_ORDER)}")


def _auto() -> RecalcEngine:
    reasons = []
    for cand in _ORDER:
        eng = get_engine(cand)
        ok, why = eng.available()
        if ok:
            return eng
        reasons.append(f"{cand}: {why}")
    raise EngineUnavailable(
        "no recalc engine available in this environment:\n  " + "\n  ".join(reasons)
    )
