"""Rewrite ``fixtures/expected_summary.json`` from the current builder output.

    python -m fable.tests.regen_expected

Run this only when a bundle-shape change is intentional, and eyeball the diff.
"""

from __future__ import annotations

import json
from pathlib import Path

from fable.compute.bundle import build_bundle

FIXTURES = Path(__file__).parent / "fixtures"


def main() -> None:
    b = build_bundle(
        FIXTURES / "golden_run",
        workbook_path=Path("workbooks/FABLEPAKUP50.xlsx"),
        country="Pakistan",
        recalc_engine="precomputed-csv",
        baseline_pathway="Current Trends",
    )
    summary = {
        "schema_version": b.schema_version,
        "pathways": b.pathways,
        "baseline_pathway": b.baseline_pathway,
        "status": b.run_quality.status,
        "tables": {
            t.key: {"rows": t.row_count, "cols": len(t.columns)} for t in b.tables
        },
        "deviation_rows": b.deviation_summary.row_count,
        "deviation_cols": len(b.deviation_summary.columns),
    }
    out = FIXTURES / "expected_summary.json"
    out.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
