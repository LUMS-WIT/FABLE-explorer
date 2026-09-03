"""Golden-file test for the bundle builder.

``fixtures/golden_run/`` is a frozen CSV run directory (6 Pakistan pathways,
recalculated in Excel on 2026-06-19). ``fixtures/expected_summary.json`` is the
bundle shape it must produce. Regenerate the expected file deliberately with::

    python -m fable.tests.regen_expected

A diff here means the bundle builder — or, once wired up, the LibreOffice
engine feeding it — changed what the viewer receives.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from fable.compute.bundle import build_bundle
from fable.compute.validate import gate

FIXTURES = Path(__file__).parent / "fixtures"
GOLDEN_RUN = FIXTURES / "golden_run"
EXPECTED = json.loads((FIXTURES / "expected_summary.json").read_text())


@pytest.fixture(scope="module")
def bundle():
    return build_bundle(
        GOLDEN_RUN,
        workbook_path=Path("workbooks/FABLEPAKUP50.xlsx"),
        country="Pakistan",
        recalc_engine="precomputed-csv",
        baseline_pathway="Current Trends",
    )


def test_pathways_and_baseline(bundle):
    assert bundle.pathways == EXPECTED["pathways"]
    assert bundle.baseline_pathway == EXPECTED["baseline_pathway"]


def test_table_shapes_match_snapshot(bundle):
    got = {t.key: {"rows": t.row_count, "cols": len(t.columns)} for t in bundle.tables}
    assert got == EXPECTED["tables"]


def test_deviation_summary_shape(bundle):
    assert bundle.deviation_summary.row_count == EXPECTED["deviation_rows"]
    assert len(bundle.deviation_summary.columns) == EXPECTED["deviation_cols"]


def test_run_quality_ok(bundle):
    assert bundle.run_quality.status == "ok"
    assert bundle.run_quality.pathways_failed == 0
    assert all(c.ok for c in bundle.run_quality.checks)


def test_json_is_finite_and_roundtrips(bundle):
    text = bundle.to_json()
    assert "NaN" not in text and "Infinity" not in text
    reparsed = json.loads(text)
    assert reparsed["schema_version"] == EXPECTED["schema_version"]


def test_publish_gate_accepts_golden_bundle(bundle):
    result = gate(bundle)
    assert result.schema_ok, result.errors
    assert result.publishable, result.errors


def test_degraded_when_pathway_failed(bundle, tmp_path):
    # Simulate a manifest with one failed pathway -> bundle must degrade,
    # not raise, and the gate must still allow publishing a partial run.
    run = tmp_path / "run"
    (run / "combined_tables").mkdir(parents=True)
    for csv in (GOLDEN_RUN / "combined_tables").glob("*.csv"):
        (run / "combined_tables" / csv.name).write_bytes(csv.read_bytes())
    (run / "run_manifest.csv").write_text(
        "Pathway,Row,Status,Error,Seconds\n"
        "Current Trends,10,ok,,1\n"
        "Balanced,11,failed,boom,1\n"
    )
    b = build_bundle(run, baseline_pathway="Current Trends")
    assert b.run_quality.status == "degraded"
    assert b.run_quality.pathways_failed == 1
    assert gate(b).publishable is True
