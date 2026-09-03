"""End-to-end orchestration: workbook -> CSV run dir -> bundle.json -> gate.

Every stage is independently callable (see :mod:`fable.compute.cli`); this
module just wires them together and writes the two artefacts the viewer and CI
consume:

    <out>/bundle.json          the data contract
    <out>/gate.json            publish decision + warnings
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from .. import __version__
from .bundle import build_bundle
from .engines import get_engine
from .model import Bundle
from .validate import GateResult, gate

GENERATOR = f"fable-compute {__version__}"


def _load_previous(path: Optional[Path]) -> Optional[Bundle]:
    if not path or not Path(path).exists():
        return None
    try:
        raw = json.loads(Path(path).read_text())
    except Exception:
        return None
    # Only the fields the regression check needs; keep it lenient.
    from .model import Grid, RunQuality, Source, Table

    try:
        return Bundle(
            source=Source(**raw["source"]),
            pathways=raw["pathways"],
            baseline_pathway=raw["baseline_pathway"],
            tables=[
                Table(
                    key=t["key"], sheet=t["sheet"], table=t["table"],
                    columns=t["columns"], rows=t["rows"],
                    pathway_col=t["pathway_col"], year_col=t.get("year_col"),
                    dimension_cols=t.get("dimension_cols", []),
                    numeric_cols=t.get("numeric_cols", []),
                )
                for t in raw["tables"]
            ],
            deviation_summary=Grid(**raw["deviation_summary"]),
            run_quality=RunQuality(
                pathways_expected=raw["run_quality"]["pathways_expected"],
                pathways_ok=raw["run_quality"]["pathways_ok"],
                pathways_failed=raw["run_quality"]["pathways_failed"],
                status=raw["run_quality"].get("status", "ok"),
            ),
            schema_version=raw.get("schema_version", "1.0.0"),
            generator=raw.get("generator", ""),
        )
    except Exception:
        return None


def _write_artifacts(bundle: Bundle, result: GateResult, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    bundle.write(out_dir / "bundle.json")
    (out_dir / "gate.json").write_text(
        json.dumps(asdict(result), indent=2), encoding="utf-8"
    )


def bundle_from_run_dir(
    run_dir: Path,
    out_dir: Path,
    *,
    workbook_path: Optional[Path] = None,
    country: str = "Unknown",
    recalc_engine: str = "precomputed-csv",
    baseline_pathway: Optional[str] = None,
    previous_bundle: Optional[Path] = None,
) -> tuple[Bundle, GateResult]:
    bundle = build_bundle(
        run_dir,
        workbook_path=workbook_path,
        country=country,
        recalc_engine=recalc_engine,
        baseline_pathway=baseline_pathway,
        generator=GENERATOR,
    )
    result = gate(bundle, previous=_load_previous(previous_bundle))
    _write_artifacts(bundle, result, out_dir)
    return bundle, result


def run_pipeline(
    workbook_path: Path,
    out_dir: Path,
    *,
    engine: str = "auto",
    output_root: Optional[Path] = None,
    country: str = "Unknown",
    baseline_pathway: Optional[str] = None,
    max_pathways: Optional[int] = None,
    workers: int = 1,
    pathway_slice: Optional[tuple[int, int]] = None,
    previous_bundle: Optional[Path] = None,
) -> tuple[Bundle, GateResult]:
    eng = get_engine(engine)
    output_root = output_root or (workbook_path.parent / "exports")
    run_dir = eng.recalc_all(
        workbook_path,
        Path(output_root),
        max_pathways=max_pathways,
        workers=workers,
        pathway_slice=pathway_slice,
    )
    return bundle_from_run_dir(
        run_dir,
        out_dir,
        workbook_path=workbook_path,
        country=country,
        recalc_engine=eng.name,
        baseline_pathway=baseline_pathway,
        previous_bundle=previous_bundle,
    )
