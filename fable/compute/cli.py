"""``python -m fable.compute`` — command-line entry point.

    engines                 show which recalc engines work here
    recalc  WORKBOOK        workbook -> CSV run directory (needs an engine)
    bundle  RUN_DIR         CSV run directory -> bundle.json + gate.json
    run     [WORKBOOK]      recalc + bundle in one go
    check   BUNDLE_JSON     re-run the publish gate on an existing bundle
    iamc    RUN_DIR         CSV run directory -> IAMC-format timeseries only
    view                    open the built viewer at http://127.0.0.1 with the current bundle
    pathways levers|template|sample|factorial WORKBOOK
                            list scenario levers, or write a pathway design CSV

Thousands of pathways: write a design with `pathways sample` or `pathways
factorial`, then `run WORKBOOK --design design.csv --workers N`.

``bundle`` and ``run`` also write IAMC files to <run_dir>/iamc/ unless
``--no-iamc`` is given or config.yaml sets ``iamc: {enabled: false}``.

Exit code is non-zero when the publish gate rejects the bundle.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

from ..iamc import IamcOptions, export_iamc, resolve_model_name
from .config import Config, load_config
from .engines import EngineUnavailable, _ORDER, get_engine
from .pipeline import bundle_from_run_dir, run_pipeline
from .validate import gate


def _add_common(p: argparse.ArgumentParser) -> None:
    p.add_argument("--out", type=Path, default=Path("viewer/public/data"),
                   help="directory for bundle.json + gate.json (default: viewer/public/data)")
    p.add_argument("--country", default=None, help="override country name")
    p.add_argument("--baseline", default=None, help="override baseline pathway")
    p.add_argument("--previous", type=Path, default=None,
                   help="previous bundle.json for the regression check")
    _add_iamc(p)
    p.add_argument("--no-iamc", action="store_true", help="skip the IAMC export")


def _add_iamc(p: argparse.ArgumentParser) -> None:
    g = p.add_argument_group("IAMC export")
    g.add_argument("--model", default=None,
                   help="IAMC model name, may include a version (default: config iamc.model, "
                        "else asked interactively, else FABLE-<country>)")
    g.add_argument("--region", default=None, help="IAMC region (default: country)")
    g.add_argument("--iamc-out", type=Path, default=None,
                   help="directory for IAMC files (default: <run_dir>/iamc)")
    g.add_argument("--no-input", action="store_true",
                   help="never prompt; use config or the suggested model name")


def _iamc_opts(args: argparse.Namespace, cfg: Config, country: str,
               *, force: bool = False) -> Optional[IamcOptions]:
    if not force and (getattr(args, "no_iamc", False) or not cfg.iamc_enabled):
        return None
    interactive = sys.stdin.isatty() and not args.no_input
    model = resolve_model_name(args.model, cfg.iamc_model, country, interactive=interactive)
    return IamcOptions(
        model=model,
        region=args.region or cfg.iamc_region or country,
        scenario_names=cfg.iamc_scenario_names,
        kyoto_gwp=cfg.iamc_kyoto_gwp,
        out_dir=args.iamc_out,
    )


def _print_gate(result) -> None:
    print("\n" + result.render(), file=sys.stderr)


def _parse_slice(spec: str | None) -> tuple[int, int] | None:
    if not spec:
        return None
    a, _, b = spec.partition(":")
    return (int(a or 0), int(b) if b else 10**9)


def cmd_engines(_: argparse.Namespace) -> int:
    for name in _ORDER:
        eng = get_engine(name)
        ok, why = eng.available()
        print(f"{'OK ' if ok else '-- '} {name:12} {why}")
    return 0


def cmd_recalc(args: argparse.Namespace) -> int:
    cfg = load_config()
    workbook = args.workbook or cfg.workbook
    if not workbook:
        print("no workbook given and config.yaml has none", file=sys.stderr)
        return 2
    eng = get_engine(args.engine)
    run_dir = eng.recalc_all(
        Path(workbook),
        args.output_root or cfg.output_dir,
        max_pathways=args.max_pathways,
        workers=args.workers,
        pathway_slice=_parse_slice(args.pathway_slice),
        run_dir=args.run_dir,
        design=args.design,
        base_pathway=args.base_pathway,
    )
    print(run_dir)
    return 0


def cmd_bundle(args: argparse.Namespace) -> int:
    cfg = load_config()
    country = args.country or cfg.country
    bundle, result = bundle_from_run_dir(
        args.run_dir,
        args.out,
        workbook_path=args.workbook or cfg.workbook,
        country=country,
        recalc_engine="precomputed-csv",
        baseline_pathway=args.baseline or cfg.baseline_pathway,
        previous_bundle=args.previous,
        iamc=_iamc_opts(args, cfg, country),
    )
    print(f"wrote {args.out / 'bundle.json'} "
          f"({len(bundle.tables)} tables, {len(bundle.pathways)} pathways, "
          f"status={bundle.run_quality.status})")
    _print_gate(result)
    return 0 if result.publishable else 1


def cmd_run(args: argparse.Namespace) -> int:
    cfg = load_config()
    workbook = args.workbook or cfg.workbook
    if not workbook:
        print("no workbook given and config.yaml has none", file=sys.stderr)
        return 2
    country = args.country or cfg.country
    if args.design:  # fail fast on a bad design, before Excel starts
        _check_design(Path(workbook), args.design, args.base_pathway)
    iamc = _iamc_opts(args, cfg, country)  # ask before the long recalc, not after
    bundle, result = run_pipeline(
        Path(workbook),
        args.out,
        engine=args.engine,
        output_root=args.output_root or cfg.output_dir,
        country=country,
        baseline_pathway=args.baseline or cfg.baseline_pathway,
        max_pathways=args.max_pathways,
        workers=args.workers,
        pathway_slice=_parse_slice(args.pathway_slice),
        previous_bundle=args.previous,
        iamc=iamc,
        design=args.design,
        base_pathway=args.base_pathway,
    )
    print(f"wrote {args.out / 'bundle.json'} (status={bundle.run_quality.status})")
    _print_gate(result)
    return 0 if result.publishable else 1


def cmd_check(args: argparse.Namespace) -> int:
    from .pipeline import _load_previous

    bundle = _load_previous(args.bundle_json)
    if bundle is None:
        print(f"could not parse {args.bundle_json}", file=sys.stderr)
        return 2
    result = gate(bundle, previous=_load_previous(args.previous))
    _print_gate(result)
    return 0 if result.publishable else 1


def cmd_iamc(args: argparse.Namespace) -> int:
    cfg = load_config()
    if not (args.run_dir / "combined_tables").is_dir():
        print(f"{args.run_dir} has no combined_tables/ directory", file=sys.stderr)
        return 2
    opts = _iamc_opts(args, cfg, args.country or cfg.country, force=True)
    assert opts is not None
    paths = export_iamc(args.run_dir, opts)
    for kind, path in paths.items():
        print(f"{kind:8} {path}")
    return 0


def _check_design(workbook: Path, design: Path, base: Optional[str]) -> int:
    from .design import load_design, read_pathway_table

    table = read_pathway_table(workbook)
    rows = load_design(design, table, base=base)
    print(f"design {design.name}: {len(rows)} pathways, {len(table.levers)} levers, all values valid",
          file=sys.stderr)
    return len(rows)


def cmd_pathways(args: argparse.Namespace) -> int:
    from . import design as dz

    cfg = load_config()
    workbook = Path(args.workbook or cfg.workbook or "")
    if not workbook.exists():
        print(f"workbook not found: {workbook}", file=sys.stderr)
        return 2
    print(f"reading levers from {workbook.name} ...", file=sys.stderr)
    table = dz.read_pathway_table(workbook)
    if args.action == "levers":
        print(dz.describe(table))
        return 0
    if args.action == "check":
        if not args.design:
            print("check needs --design FILE", file=sys.stderr)
            return 2
        _check_design(workbook, args.design, args.base_pathway)
        return 0
    vary = [v for v in (args.vary or "").split(",") if v.strip()]
    if args.action == "template":
        df = dz.template(table)
    elif args.action == "factorial":
        if not vary:
            print("factorial needs --vary LEVER,LEVER,...", file=sys.stderr)
            return 2
        df = dz.factorial(table, vary, base=args.base_pathway, prefix=args.prefix)
    else:
        df = dz.sample(table, args.n, vary=vary or None, base=args.base_pathway,
                       seed=args.seed, prefix=args.prefix)
    out = args.output or Path(f"pathways_{args.action}.csv")
    df.to_csv(out, index=False)
    print(f"wrote {out} ({len(df)} pathways x {len(table.levers)} levers)")
    return 0


def cmd_view(args: argparse.Namespace) -> int:
    from .serve import serve_forever

    serve_forever(data=args.data, port=args.port, open_browser=not args.no_browser)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m fable.compute", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("engines", help="show recalc engine availability").set_defaults(func=cmd_engines)

    pr = sub.add_parser("recalc", help="workbook -> CSV run directory")
    pr.add_argument("workbook", nargs="?", default=None)
    pr.add_argument("--engine", default="auto", help="auto | " + " | ".join(_ORDER))
    pr.add_argument("--output-root", type=Path, default=None)
    pr.add_argument("--max-pathways", type=int, default=None)
    pr.add_argument("--workers", type=int, default=1,
                    help="parallel spreadsheet processes (xlwings engine)")
    pr.add_argument("--pathway-slice", default=None, metavar="START:STOP",
                    help="index range of pathways for multi-machine sharding")
    pr.add_argument("--design", type=Path, default=None,
                    help="CSV of pathways (PATHWAY + lever columns) to run instead of the workbook's own")
    pr.add_argument("--base-pathway", default=None,
                    help="workbook pathway that fills levers missing from --design (default: first)")
    pr.add_argument("--run-dir", type=Path, default=None,
                    help="reuse/resume an existing run directory")
    pr.set_defaults(func=cmd_recalc)

    pb = sub.add_parser("bundle", help="CSV run directory -> bundle.json")
    pb.add_argument("run_dir", type=Path)
    pb.add_argument("--workbook", type=Path, default=None)
    _add_common(pb)
    pb.set_defaults(func=cmd_bundle)

    prun = sub.add_parser("run", help="recalc + bundle")
    prun.add_argument("workbook", nargs="?", default=None)
    prun.add_argument("--engine", default="auto", help="auto | " + " | ".join(_ORDER))
    prun.add_argument("--output-root", type=Path, default=None)
    prun.add_argument("--max-pathways", type=int, default=None)
    prun.add_argument("--workers", type=int, default=1,
                     help="parallel spreadsheet processes (xlwings engine)")
    prun.add_argument("--pathway-slice", default=None, metavar="START:STOP",
                     help="index range of pathways for multi-machine sharding")
    prun.add_argument("--design", type=Path, default=None,
                    help="CSV of pathways (PATHWAY + lever columns) to run instead of the workbook's own")
    prun.add_argument("--base-pathway", default=None,
                    help="workbook pathway that fills levers missing from --design (default: first)")
    _add_common(prun)
    prun.set_defaults(func=cmd_run)

    pc = sub.add_parser("check", help="re-run the publish gate on a bundle.json")
    pc.add_argument("bundle_json", type=Path)
    pc.add_argument("--previous", type=Path, default=None)
    pc.set_defaults(func=cmd_check)

    pi = sub.add_parser("iamc", help="CSV run directory -> IAMC-format timeseries")
    pi.add_argument("run_dir", type=Path)
    pi.add_argument("--country", default=None, help="override country name")
    _add_iamc(pi)
    pi.set_defaults(func=cmd_iamc)

    pp = sub.add_parser("pathways", help="list scenario levers or write a pathway design CSV",
                        description=(
                            "levers     list every lever and its allowed options\n"
                            "template   write the workbook's own pathways as a design CSV to edit\n"
                            "sample     N random distinct combinations (balanced per lever)\n"
                            "factorial  every combination of the --vary levers\n"
                            "check      validate a design CSV against the workbook"),
                        formatter_class=argparse.RawDescriptionHelpFormatter)
    pp.add_argument("action", choices=["levers", "template", "sample", "factorial", "check"])
    pp.add_argument("workbook", nargs="?", default=None)
    pp.add_argument("-o", "--output", type=Path, default=None, help="design CSV to write")
    pp.add_argument("-n", type=int, default=100, help="sample: number of pathways")
    pp.add_argument("--vary", default="", help="comma-separated lever keys (default for sample: all "
                                               "levers except BaseYear, GWP, Price)")
    pp.add_argument("--base-pathway", default=None,
                    help="workbook pathway that supplies levers not varied (default: first)")
    pp.add_argument("--seed", type=int, default=1)
    pp.add_argument("--prefix", default="P", help="pathway name prefix (P0001, P0002, ...)")
    pp.add_argument("--design", type=Path, default=None, help="check: design CSV to validate")
    pp.set_defaults(func=cmd_pathways)

    pv = sub.add_parser("view", help="serve the built viewer locally with the current bundle")
    pv.add_argument("--data", type=Path, default=None,
                    help="folder holding bundle.json (default: viewer/public/data)")
    pv.add_argument("--port", type=int, default=8765)
    pv.add_argument("--no-browser", action="store_true")
    pv.set_defaults(func=cmd_view)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except EngineUnavailable as exc:
        print(f"\nno recalc engine: {exc}", file=sys.stderr)
        return 3
    except FileNotFoundError as exc:
        print(f"\n{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
