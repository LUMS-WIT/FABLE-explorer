"""In-memory representation of a results bundle + JSON (de)serialisation.

The bundle is deliberately plain: dataclasses, lists, and a columnar table
layout (``columns`` + ``rows``) so it round-trips through JSON with no custom
decoder and stays compact. ``fable/contract/bundle.schema.json`` is the
authoritative shape; ``schema.py`` checks this module against it.

JSON has no NaN / Infinity. Every non-finite float is written as ``null`` and
read back as ``None``; the viewer treats ``null`` as "missing".
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from . import BUNDLE_SCHEMA_VERSION

Scalar = Optional[Any]  # str | int | float | bool | None after cleaning


def _clean(value: Any) -> Scalar:
    """Coerce a single cell to a JSON-safe scalar (NaN/Inf -> None)."""
    if value is None:
        return None
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, (str, int, bool)):
        return value
    # numpy scalars, Timestamps, etc.
    try:
        f = float(value)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        s = str(value)
        return s if s and s.lower() != "nan" else None


@dataclass
class Table:
    """One output table, all pathways stacked, in columnar form."""

    key: str                       # "GHG__ResultsGHG"
    sheet: str                     # "GHG"
    table: str                     # "ResultsGHG"
    columns: List[str]
    rows: List[List[Scalar]]
    pathway_col: str
    year_col: Optional[str] = None
    dimension_cols: List[str] = field(default_factory=list)
    numeric_cols: List[str] = field(default_factory=list)

    @property
    def row_count(self) -> int:
        return len(self.rows)


@dataclass
class Grid:
    """A generic columns+rows grid (used for the deviation summary)."""

    columns: List[str]
    rows: List[List[Scalar]]

    @property
    def row_count(self) -> int:
        return len(self.rows)


@dataclass
class QualityCheck:
    name: str
    ok: bool
    detail: str = ""


@dataclass
class PathwayFailure:
    pathway: str
    error: str


@dataclass
class RunQuality:
    pathways_expected: int
    pathways_ok: int
    pathways_failed: int
    status: str = "ok"                         # ok | degraded | failed
    failures: List[PathwayFailure] = field(default_factory=list)
    checks: List[QualityCheck] = field(default_factory=list)

    def recompute_status(self) -> None:
        hard_fail = any(not c.ok for c in self.checks if c.name in _HARD_CHECKS)
        if hard_fail or self.pathways_ok == 0:
            self.status = "failed"
        elif self.pathways_failed or any(not c.ok for c in self.checks):
            self.status = "degraded"
        else:
            self.status = "ok"


_HARD_CHECKS = {"baseline_present", "has_pathways", "has_tables"}


@dataclass
class Source:
    workbook_filename: str
    workbook_sha256: str
    country: str
    recalc_engine: str                         # xlwings | libreoffice | precomputed-csv
    run_id: str
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
        .replace("+00:00", "Z")
    )


@dataclass
class Bundle:
    source: Source
    pathways: List[str]
    baseline_pathway: str
    tables: List[Table]
    deviation_summary: Grid
    run_quality: RunQuality
    schema_version: str = BUNDLE_SCHEMA_VERSION
    generator: str = ""

    # ---- serialisation -------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # asdict already recursed; just make sure key order is stable-ish
        return {
            "schema_version": d["schema_version"],
            "generator": d["generator"],
            "source": d["source"],
            "pathways": d["pathways"],
            "baseline_pathway": d["baseline_pathway"],
            "tables": d["tables"],
            "deviation_summary": d["deviation_summary"],
            "run_quality": d["run_quality"],
        }

    def to_json(self, *, indent: Optional[int] = None) -> str:
        return json.dumps(
            self.to_dict(),
            indent=indent,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":") if indent is None else None,
        )

    def write(self, path, *, indent: Optional[int] = None) -> None:
        from pathlib import Path

        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(self.to_json(indent=indent), encoding="utf-8")


def major(version: str) -> int:
    return int(version.split(".", 1)[0])
