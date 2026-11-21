"""Pathway designs: run any number of pathways without editing the workbook.

A FABLE workbook defines pathways as rows of the ``PathwaysSelection`` table
on the ``PATHWAYS selection`` sheet: a name plus one value per scenario lever
(diet, GDP, land expansion, afforestation, ...). Each lever cell has a
drop-down list backed by a named range (``LstDiet_scen`` -> 'SCENARIOS
selection'!B55:B58), so the allowed options can be read from the file.

A *design* is a CSV with one row per pathway: ``PATHWAY`` plus one column per
lever, using the lever keys printed by ``python -m fable.compute pathways
levers``. Levers left out of the CSV take the value of a base pathway. The
recalc engine writes each design row into a spare row of its private copy of
the workbook, selects it and recalculates, so a design can hold thousands of
pathways.

    python -m fable.compute pathways levers   WB.xlsx
    python -m fable.compute pathways template WB.xlsx -o design.csv
    python -m fable.compute pathways sample   WB.xlsx -n 1000 --vary Diet,Land,Affor -o design.csv
    python -m fable.compute pathways factorial WB.xlsx --vary Diet,Land,Affor -o design.csv
    python -m fable.compute run WB.xlsx --design design.csv --workers 8
"""

from __future__ import annotations

import itertools
import random
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import pandas as pd

# Levers that set how results are reported rather than what happens; left at
# the base pathway's value unless named explicitly in --vary.
SETTING_LEVERS = {"BaseYear", "GWP", "Price"}

PATHWAY_SHEET = "PATHWAYS selection"
PATHWAY_TABLE = "PathwaysSelection"
LEVERS_FILE = "pathway_levers.csv"  # written into every run directory


@dataclass
class Lever:
    code: str            # table header, e.g. "S3"
    key: str             # readable key used in design CSVs, e.g. "Diet"
    column: int          # 1-based worksheet column
    options: List[object] = field(default_factory=list)  # allowed values, workbook types
    source: str = ""     # named range or inline list the options came from

    def match(self, raw: object) -> object:
        """Return the workbook value equal to ``raw`` (compared as text)."""
        text = _norm(raw)
        for opt in self.options:
            if _norm(opt) == text:
                return opt
        if not self.options:
            return _coerce(raw)
        raise ValueError(
            f"{self.key}: '{raw}' is not an allowed option ({', '.join(map(str, self.options))})"
        )


@dataclass
class PathwayTable:
    levers: List[Lever]
    name_column: int
    selection_column: int
    first_row: int
    last_row: int
    pathways: pd.DataFrame  # PATHWAY + lever keys, the rows already in the workbook
    rows: List[int] = field(default_factory=list)  # worksheet row of each of those pathways

    @property
    def keys(self) -> List[str]:
        return [lv.key for lv in self.levers]


def _norm(v: object) -> str:
    if v is None:
        return ""
    if isinstance(v, float) and v.is_integer():
        v = int(v)
    return str(v).strip().lower()


def _coerce(v: object) -> object:
    if isinstance(v, str):
        s = v.strip()
        if re.fullmatch(r"-?\d+", s):
            return int(s)
        if re.fullmatch(r"-?\d*\.\d+", s):
            return float(s)
        return s
    return v


_KEY_FIXES = {"pop": "Population", "live": "Livestock", "affor": "Afforestation",
              "livedens": "LivestockDensity", "pa": "ProtectedAreas", "gwp": "GWP", "gdp": "GDP"}


def _lever_key(list_name: str, code: str) -> str:
    """LstDiet_scen -> Diet, LstScen_foodloss -> Foodloss, LstGDP_Scen -> GDP."""
    s = re.sub(r"^lst", "", list_name, flags=re.I)
    s = re.sub(r"_?scen$", "", s, flags=re.I)
    s = re.sub(r"^scen_?", "", s, flags=re.I)
    s = s.strip("_ ")
    if not s:
        return code
    fixed = _KEY_FIXES.get(s.lower())
    if fixed:
        return fixed
    return s[0].upper() + s[1:]


def _range_values(wb, sheet: str, ref: str) -> List[object]:
    cells = wb[sheet][ref.replace("$", "")]
    if not isinstance(cells, tuple):
        cells = ((cells,),)
    out: List[object] = []
    for row in cells:
        for c in row if isinstance(row, tuple) else (row,):
            v = c.value
            if v is None or not isinstance(v, (str, int, float)) or str(v).strip() == "":
                continue  # blank, or a formula object the workbook was never saved with a value for
            out.append(v)
    return out


def read_pathway_table(workbook_path: Path, wb=None) -> PathwayTable:
    """Parse the pathway table, its levers and their allowed options."""
    from openpyxl import load_workbook
    from openpyxl.utils.cell import range_boundaries

    own = wb is None
    if own:
        # data_only: option lists can be formulas; their saved values are what the drop-down shows
        wb = load_workbook(workbook_path, data_only=True, read_only=False)
    try:
        ws = wb[PATHWAY_SHEET]
        if PATHWAY_TABLE not in ws.tables:
            raise ValueError(f"table '{PATHWAY_TABLE}' not found on '{PATHWAY_SHEET}'")
        ref = ws.tables[PATHWAY_TABLE]
        ref = ref if isinstance(ref, str) else ref.ref
        c0, r0, c1, r1 = range_boundaries(ref)
        headers = [ws.cell(r0, c).value for c in range(c0, c1 + 1)]
        norm = [str(h).strip().lower() if h is not None else "" for h in headers]
        if "selection" not in norm or "pathway" not in norm:
            raise ValueError(f"{PATHWAY_TABLE} needs SELECTION and PATHWAY headers")
        sel_col = c0 + norm.index("selection")
        name_col = c0 + norm.index("pathway")

        # which named list (or inline list) validates each column
        col_source: Dict[int, str] = {}
        for dv in ws.data_validations.dataValidation:
            if dv.type != "list" or not dv.formula1:
                continue
            for rng in str(dv.sqref).split():
                try:
                    a, _, _, _ = range_boundaries(rng)
                except Exception:
                    continue
                col_source[a] = dv.formula1

        levers: List[Lever] = []
        used: Dict[str, int] = {}
        for col in range(name_col + 1, c1 + 1):
            code = str(ws.cell(r0, col).value or f"C{col}").strip()
            src = col_source.get(col, "")
            options: List[object] = []
            if src.startswith('"'):
                options = [_coerce(x) for x in src.strip('"').split(",") if x.strip()]
                key = code
            elif src:
                dn = wb.defined_names.get(src)
                if dn is not None:
                    for sheet, rng in dn.destinations:
                        options += _range_values(wb, sheet, rng)
                key = _lever_key(src, code)
            else:
                key = code
            if code.upper() == "S0" or (options and all(isinstance(o, int) for o in options)):
                key = "BaseYear" if key == code else key
            if key in used:  # keep keys unique
                key = f"{key}_{code}"
            used[key] = col
            levers.append(Lever(code=code, key=key, column=col, options=options, source=src))

        rows = []
        row_numbers: List[int] = []
        for r in range(r0 + 1, r1 + 1):
            name = ws.cell(r, name_col).value
            if name is None or str(name).strip() == "":
                continue
            row_numbers.append(r)
            rec = {"PATHWAY": str(name).strip()}
            for lv in levers:
                rec[lv.key] = ws.cell(r, lv.column).value
            rows.append(rec)
        # free-text levers: allowed options = what the workbook already uses
        df = pd.DataFrame(rows, columns=["PATHWAY", *[lv.key for lv in levers]])
        for lv in levers:
            if not lv.options:
                lv.options = [v for v in dict.fromkeys(df[lv.key].tolist()) if v is not None]
                lv.source = lv.source or "values used in the workbook"
        return PathwayTable(levers, name_col, sel_col, r0 + 1, r1, df, row_numbers)
    finally:
        if own:
            wb.close()


# --------------------------------------------------------------------------
# design files
# --------------------------------------------------------------------------
def load_design(path: Path, table: PathwayTable, base: Optional[str] = None) -> List[Tuple[str, Tuple]]:
    """Read and validate a design CSV -> [(pathway, lever values in column order)].

    Raises ``ValueError`` listing every problem, so nothing starts on a bad file.
    """
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    df.columns = [c.strip() for c in df.columns]
    if "PATHWAY" not in df.columns:
        raise ValueError(f"{path}: needs a PATHWAY column")
    known = {lv.key.lower(): lv for lv in table.levers} | {lv.code.lower(): lv for lv in table.levers}
    unknown = [c for c in df.columns if c != "PATHWAY" and c.lower() not in known]
    errors: List[str] = []
    if unknown:
        errors.append(f"unknown lever column(s): {', '.join(unknown)} "
                      f"(levers: {', '.join(table.keys)})")
    base_name = base or (table.pathways["PATHWAY"].iloc[0] if len(table.pathways) else None)
    base_row = table.pathways.set_index("PATHWAY").loc[base_name] if base_name in set(table.pathways["PATHWAY"]) else None
    if base_row is None and len(df.columns) - 1 < len(table.levers):
        errors.append(f"base pathway '{base_name}' not found; give every lever column")

    names = df["PATHWAY"].str.strip()
    dupes = names[names.duplicated()].unique().tolist()
    if dupes:
        errors.append(f"duplicate PATHWAY names: {', '.join(dupes[:10])}")
    if (names == "").any():
        errors.append("empty PATHWAY name(s)")

    out: List[Tuple[str, Tuple]] = []
    col_for = {c.lower(): c for c in df.columns}
    for i, rec in df.iterrows():
        values = []
        for lv in table.levers:
            col = col_for.get(lv.key.lower()) or col_for.get(lv.code.lower())
            raw = rec[col] if col is not None and rec[col] != "" else (
                base_row[lv.key] if base_row is not None else None)
            try:
                values.append(lv.match(raw))
            except ValueError as exc:
                errors.append(f"row {i + 2} ({rec['PATHWAY']}): {exc}")
        out.append((str(rec["PATHWAY"]).strip(), tuple(values)))
    if errors:
        head = errors[:25]
        more = f"\n  ... and {len(errors) - 25} more" if len(errors) > 25 else ""
        raise ValueError(f"{path}: design file has problems:\n  " + "\n  ".join(head) + more)
    return out


def template(table: PathwayTable) -> pd.DataFrame:
    return table.pathways.copy()


def _base_values(table: PathwayTable, base: Optional[str]) -> Dict[str, object]:
    if base is None:
        return table.pathways.iloc[0].to_dict()
    hit = table.pathways[table.pathways["PATHWAY"] == base]
    if hit.empty:
        raise ValueError(f"base pathway '{base}' not in the workbook "
                         f"({', '.join(table.pathways['PATHWAY'])})")
    return hit.iloc[0].to_dict()


def _resolve_vary(table: PathwayTable, vary: Optional[Sequence[str]]) -> List[Lever]:
    by = {lv.key.lower(): lv for lv in table.levers} | {lv.code.lower(): lv for lv in table.levers}
    if not vary:
        return [lv for lv in table.levers if len(lv.options) > 1 and lv.key not in SETTING_LEVERS]
    out = []
    for v in vary:
        lv = by.get(v.strip().lower())
        if lv is None:
            raise ValueError(f"unknown lever '{v}' (levers: {', '.join(table.keys)})")
        out.append(lv)
    return out


def factorial(table: PathwayTable, vary: Sequence[str], base: Optional[str] = None,
              limit: int = 100_000, prefix: str = "P") -> pd.DataFrame:
    """Every combination of the options of the ``vary`` levers; others from ``base``."""
    levers = _resolve_vary(table, vary)
    total = 1
    for lv in levers:
        total *= len(lv.options)
    if total > limit:
        raise ValueError(f"{total:,} combinations exceeds the limit of {limit:,}; "
                         "vary fewer levers or use 'sample'")
    b = _base_values(table, base)
    rows = []
    width = len(str(total))
    for i, combo in enumerate(itertools.product(*(lv.options for lv in levers)), 1):
        rec = {k: b[k] for k in table.keys}
        rec.update({lv.key: v for lv, v in zip(levers, combo)})
        rows.append({"PATHWAY": f"{prefix}{i:0{width}d}", **rec})
    return pd.DataFrame(rows, columns=["PATHWAY", *table.keys])


def sample(table: PathwayTable, n: int, vary: Optional[Sequence[str]] = None,
           base: Optional[str] = None, seed: int = 1, prefix: str = "P") -> pd.DataFrame:
    """``n`` distinct random combinations of the ``vary`` levers (all by default).

    Each option of each lever is drawn equally often (a balanced shuffle per
    lever), which spreads the sample more evenly than independent draws.
    """
    levers = _resolve_vary(table, vary)
    space = 1
    for lv in levers:
        space *= len(lv.options)
    if n > space:
        raise ValueError(f"only {space:,} distinct combinations exist; asked for {n:,} "
                         "(use 'factorial' for all of them)")
    rng = random.Random(seed)
    b = _base_values(table, base)
    seen = set()
    rows: List[dict] = []
    width = len(str(n))
    attempts = 0
    while len(rows) < n and attempts < 50:
        attempts += 1
        need = n - len(rows)
        cols = []
        for lv in levers:
            col = [lv.options[i % len(lv.options)] for i in range(need)]
            rng.shuffle(col)
            cols.append(col)
        for combo in zip(*cols):
            if combo in seen:
                continue
            seen.add(combo)
            rec = {k: b[k] for k in table.keys}
            rec.update({lv.key: v for lv, v in zip(levers, combo)})
            rows.append(rec)
    for i, rec in enumerate(rows, 1):
        rec["PATHWAY"] = f"{prefix}{i:0{width}d}"
    return pd.DataFrame(rows, columns=["PATHWAY", *table.keys])


def describe(table: PathwayTable) -> str:
    lines = [f"{len(table.levers)} levers in {PATHWAY_TABLE} "
             f"({len(table.pathways)} pathways defined in the workbook)\n"]
    w = max(len(lv.key) for lv in table.levers)
    for lv in table.levers:
        opts = ", ".join(map(str, lv.options)) or "(free text)"
        lines.append(f"  {lv.key:<{w}}  [{lv.code}]  {opts}")
    space = 1
    for lv in table.levers:
        if lv.key not in SETTING_LEVERS:
            space *= max(1, len(lv.options))
    lines.append(f"\nCombinations of all levers except {', '.join(sorted(SETTING_LEVERS))}: {space:,}")
    lines.append("Reporting settings (BaseYear, GWP, Price) stay at the base pathway's value unless "
                 "you list them in --vary.")
    return "\n".join(lines)


def write_levers(run_dir: Path, rows: List[Tuple[str, Tuple]], table: PathwayTable) -> Path:
    """Record each pathway's lever values in the run directory (used as IAMC meta)."""
    df = pd.DataFrame([{"PATHWAY": n, **dict(zip(table.keys, vals))} for n, vals in rows])
    out = Path(run_dir) / LEVERS_FILE
    df.to_csv(out, index=False)
    return out


def read_levers(run_dir: Path) -> Optional[pd.DataFrame]:
    p = Path(run_dir) / LEVERS_FILE
    if not p.exists():
        return None
    try:
        return pd.read_csv(p, dtype=str, keep_default_na=False)
    except Exception:
        return None
