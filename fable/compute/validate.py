"""The publish gate.

A bundle is publishable when **both** hold:

* it validates against ``fable/contract/bundle.schema.json`` (structural), and
* ``run_quality.status`` is not ``"failed"`` (semantic).

An optional regression check compares against the previous published bundle and
flags tables whose row count moved by more than a tolerance — catches a
spreadsheet-engine upgrade silently dropping rows.

``jsonschema`` is an optional import: if it is missing the structural check is
skipped with a warning rather than failing the run.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from .model import Bundle, major

CONTRACT_DIR = Path(__file__).resolve().parents[1] / "contract"
SCHEMA_PATH = CONTRACT_DIR / "bundle.schema.json"


@dataclass
class GateResult:
    publishable: bool
    schema_ok: bool
    status: str
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def render(self) -> str:
        lines = [
            f"publishable : {self.publishable}",
            f"schema_ok   : {self.schema_ok}",
            f"run status  : {self.status}",
        ]
        for e in self.errors:
            lines.append(f"  ERROR   {e}")
        for w in self.warnings:
            lines.append(f"  warning {w}")
        return "\n".join(lines)


def _schema_check(bundle: Bundle) -> tuple[bool, List[str], List[str]]:
    if not SCHEMA_PATH.exists():
        return True, [], [f"no schema at {SCHEMA_PATH}, structural check skipped"]
    try:
        import jsonschema  # type: ignore
    except ImportError:
        return True, [], ["jsonschema not installed, structural check skipped"]

    schema = json.loads(SCHEMA_PATH.read_text())
    doc = json.loads(bundle.to_json())
    validator = jsonschema.Draft202012Validator(schema)
    errs = sorted(validator.iter_errors(doc), key=lambda e: list(e.path))
    msgs = [f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in errs[:25]]
    return (not errs), msgs, []


def regression_warnings(
    bundle: Bundle,
    previous: Optional[Bundle],
    *,
    row_tolerance: float = 0.10,
) -> List[str]:
    if previous is None:
        return []
    warns: List[str] = []
    if major(previous.schema_version) != major(bundle.schema_version):
        return [
            f"previous bundle schema {previous.schema_version} differs in major "
            f"version from {bundle.schema_version}; regression check skipped"
        ]
    prev_rows = {t.key: t.row_count for t in previous.tables}
    for t in bundle.tables:
        base = prev_rows.get(t.key)
        if not base:
            warns.append(f"table {t.key!r} is new vs previous bundle")
            continue
        if abs(t.row_count - base) > max(1, base * row_tolerance):
            warns.append(
                f"table {t.key!r} row count {t.row_count} vs previous {base} "
                f"(> {row_tolerance:.0%})"
            )
    for key in prev_rows.keys() - {t.key for t in bundle.tables}:
        warns.append(f"table {key!r} present previously, now missing")
    return warns


def gate(bundle: Bundle, *, previous: Optional[Bundle] = None) -> GateResult:
    schema_ok, schema_errs, schema_warns = _schema_check(bundle)

    errors = list(schema_errs)
    warnings = list(schema_warns)
    warnings += [f"quality check failed: {c.name} ({c.detail})"
                 for c in bundle.run_quality.checks if not c.ok]
    warnings += regression_warnings(bundle, previous)

    status = bundle.run_quality.status
    publishable = schema_ok and status != "failed"
    if status == "failed":
        errors.append("run_quality.status == 'failed'")

    return GateResult(
        publishable=publishable,
        schema_ok=schema_ok,
        status=status,
        errors=errors,
        warnings=warnings,
    )
