"""Build a large synthetic run directory from the 6-pathway golden run.

Used to test the bundle, the IAMC export and the dashboard at scale without
Excel. Each synthetic pathway copies one real pathway and scales its projected
values (years after 2015) by a smooth random factor, and gets random lever
settings, so the data looks like a design run but means nothing.

    python -m fable.tests.synthetic OUT_DIR -n 1000
"""

from __future__ import annotations

import argparse
import random
from pathlib import Path

import numpy as np
import pandas as pd

GOLDEN = Path(__file__).parent / "fixtures" / "golden_run"
LEVERS = {
    "Diet": ["NoChange", "EATLancetAverage", "FatDiet", "MyDiet"],
    "Land": ["NoExpansion", "NoDefor2030", "FreeExpansion"],
    "Afforestation": ["NoAffor", "BonnChallenge", "10billiontsunami", "Net-Zero"],
    "Livestock": ["NoGrowth", "BAUGrowth", "HighGrowth", "LowGrowth"],
    "Crop": ["NoGrowth", "LowGrowth", "MiddleGrowth", "HighGrowth"],
}
SKIP_COLS = {"Year", "YEAR", "CPIPriceShifter", "CH4", "N2O"}


def make(out_dir: Path, n: int, seed: int = 1, golden: Path = GOLDEN) -> Path:
    rng = random.Random(seed)
    nprng = np.random.default_rng(seed)
    out_dir = Path(out_dir)
    (out_dir / "combined_tables").mkdir(parents=True, exist_ok=True)
    manifest = pd.read_csv(golden / "run_manifest.csv")
    real = manifest["Pathway"].tolist()
    names = [real[0]] + [f"P{i:04d}" for i in range(1, n)]
    template = [real[0]] + [real[i % len(real)] for i in range(1, n)]
    # one smooth multiplier per pathway; 1 for the baseline copy
    gains = [1.0] + list(nprng.normal(1.0, 0.12, size=n - 1).clip(0.6, 1.5))

    for csv in sorted((golden / "combined_tables").glob("*__all_pathways.csv")):
        df = pd.read_csv(csv)
        pcol = "RunPathway"
        ycol = "Year" if "Year" in df.columns else "YEAR" if "YEAR" in df.columns else None
        num = [c for c in df.columns if c not in SKIP_COLS and c != pcol
               and pd.api.types.is_numeric_dtype(df[c])]
        frames = []
        for name, tmpl, g in zip(names, template, gains):
            part = df[df[pcol] == tmpl].copy()
            part[pcol] = name
            if ycol and g != 1.0 and num:
                ramp = ((part[ycol] - 2015).clip(lower=0) / 35.0).to_numpy()[:, None]
                part[num] = part[num].to_numpy() * (1 + (g - 1) * ramp)
            frames.append(part)
        pd.concat(frames, ignore_index=True).to_csv(out_dir / "combined_tables" / csv.name, index=False)

    pd.DataFrame({"Pathway": names, "Row": 20, "Status": "ok", "Error": "", "Seconds": 0.0}).to_csv(
        out_dir / "run_manifest.csv", index=False)
    lev = [{"PATHWAY": nm, **{k: rng.choice(v) for k, v in LEVERS.items()}} for nm in names]
    pd.DataFrame(lev).to_csv(out_dir / "pathway_levers.csv", index=False)
    return out_dir


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out_dir", type=Path)
    ap.add_argument("-n", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    print(make(a.out_dir, a.n, a.seed))
