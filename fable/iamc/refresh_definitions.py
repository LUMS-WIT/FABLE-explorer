"""Regenerate ``iamc_variables.csv`` from a clone of IAMC common-definitions.

    git clone --depth 1 https://github.com/IAMconsortium/common-definitions.git /tmp/cd
    python -m fable.iamc.refresh_definitions /tmp/cd

Expands ``{Tag}`` placeholders (e.g. ``{Crop Types}``) with the values from the
``tag_*.yaml`` files, including tag-supplied units (emission species), and writes
every (variable, unit) pair from the domains FABLE can report into. The export
checks its output against this snapshot, so no network access is needed at run
time.
"""

from __future__ import annotations

import csv
import itertools
import re
import subprocess
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).parent
OUT = HERE / "iamc_variables.csv"

# Domains of common-definitions that FABLE outputs can map to.
DOMAINS = {
    "afolu": None,  # all files
    "environment": None,
    "emissions": ["emissions.yaml"],
    "macro-economy": ["labor-force.yaml"],
}

TAG_RE = re.compile(r"\{([^{}]+)\}")


def _load_tags(var_root: Path) -> dict[str, list[tuple[str, dict]]]:
    tags: dict[str, list[tuple[str, dict]]] = {}
    for f in var_root.rglob("tag_*.yaml"):
        data = yaml.safe_load(f.read_text()) or []
        for block in data:
            for tag, values in block.items():
                items = []
                for v in values:
                    (name, attrs), = v.items()
                    items.append((str(name), attrs or {}))
                tags[tag] = items
    return tags


def _expand(name: str, unit, tags) -> list[tuple[str, str]]:
    found = [t for t in dict.fromkeys(TAG_RE.findall(name)) if t in tags]
    if not found:
        return [(name, "" if unit is None else str(unit))]
    out = []
    for combo in itertools.product(*(tags[t] for t in found)):
        n, u = name, "" if unit is None else str(unit)
        for tag, (val, attrs) in zip(found, combo):
            n = n.replace("{" + tag + "}", val)
            if u == "{" + tag + "}":
                u = str(attrs.get("unit", ""))
            else:
                u = u.replace("{" + tag + "}", val)
        out.append((n, u))
    return out


def main(clone: str) -> int:
    root = Path(clone)
    var_root = root / "definitions" / "variable"
    tags = _load_tags(var_root)
    rows: list[tuple[str, str, str]] = []
    for domain, files in DOMAINS.items():
        d = var_root / domain
        paths = sorted(d.glob("*.yaml")) if files is None else [d / f for f in files]
        for p in paths:
            if p.name.startswith("tag_"):
                continue
            for entry in yaml.safe_load(p.read_text()) or []:
                (name, attrs), = entry.items()
                attrs = attrs or {}
                for n, u in _expand(str(name), attrs.get("unit"), tags):
                    rows.append((n, u, f"{domain}/{p.name}"))
    try:
        rev = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"],
                             capture_output=True, text=True, check=True).stdout.strip()
    except Exception:
        rev = "unknown"
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        fh.write(f"# IAMconsortium/common-definitions @ {rev}\n")
        w = csv.writer(fh)
        w.writerow(["variable", "unit", "file"])
        w.writerows(sorted(set(rows)))
    print(f"wrote {OUT} ({len(set(rows))} variables, rev {rev[:10]})")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
