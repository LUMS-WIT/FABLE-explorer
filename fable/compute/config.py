"""Read ``config.yaml`` at the repo root.

Backwards compatible with the legacy one-line form::

    workbook: workbooks/FABLEPAKUP50.xlsx

Optional additions used by the bundle builder::

    country: Pakistan
    baseline_pathway: Current Trends
    output_dir: exports
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = REPO_ROOT / "config.yaml"


@dataclass
class Config:
    workbook: Optional[Path] = None
    country: str = "Unknown"
    baseline_pathway: Optional[str] = None
    output_dir: Path = REPO_ROOT / "exports"


def _load_yaml(path: Path) -> dict:
    try:
        import yaml  # type: ignore

        data = yaml.safe_load(path.read_text()) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        # Minimal fallback parser for "key: value" lines.
        out: dict = {}
        for line in path.read_text().splitlines():
            m = re.match(r"^\s*([A-Za-z_][\w-]*)\s*:\s*(.+?)\s*$", line)
            if m:
                out[m.group(1)] = m.group(2).strip().strip('"').strip("'")
        return out


def load_config(path: Path = CONFIG_PATH) -> Config:
    cfg = Config()
    if not path.exists():
        return cfg
    data = _load_yaml(path)

    wb = data.get("workbook") or data.get("workbook_path")
    if wb:
        p = Path(str(wb)).expanduser()
        cfg.workbook = p if p.is_absolute() else (path.parent / p)
    if data.get("country"):
        cfg.country = str(data["country"])
    if data.get("baseline_pathway"):
        cfg.baseline_pathway = str(data["baseline_pathway"])
    if data.get("output_dir"):
        p = Path(str(data["output_dir"])).expanduser()
        cfg.output_dir = p if p.is_absolute() else (path.parent / p)
    return cfg
