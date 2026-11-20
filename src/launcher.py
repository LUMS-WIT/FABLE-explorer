#!/usr/bin/env python
"""Tkinter launcher for the FABLE pipeline.

Thin GUI over ``fable.compute``:

1. pick a workbook (defaults from ``config.yaml``)
2. choose engine + parallel worker count
3. Run -> recalc every pathway -> build ``viewer/public/data/bundle.json``
4. optionally open the static viewer / legacy Streamlit dashboard

The heavy lifting (single workbook parse, manual-calc Excel, scenario dedupe,
resumable run dir, N parallel Excel processes) lives in
``fable/compute/engines/xlwings_engine.py``. This window only drives it.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import webbrowser
from pathlib import Path
from typing import Optional

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from fable.compute.config import load_config  # noqa: E402
from fable.compute.engines import _ORDER, get_engine  # noqa: E402
from fable.compute.pipeline import bundle_from_run_dir, run_pipeline  # noqa: E402
from fable.compute.serve import start_server  # noqa: E402
from fable.iamc import IamcOptions, suggest_model_name  # noqa: E402

_VIEWER_DATA = _REPO_ROOT / "viewer" / "public" / "data"


class FableLauncher(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("FABLE Launcher")
        self.geometry("720x470")
        self.resizable(False, False)

        cfg = load_config()
        self.cfg = cfg
        self.workbook_path = tk.StringVar(value=str(cfg.workbook or ""))
        self.output_dir = tk.StringVar(value=str(cfg.output_dir))
        self.engine = tk.StringVar(value="auto")
        self.workers = tk.IntVar(value=max(1, (os.cpu_count() or 2) // 2))
        self.skip_recalc = tk.BooleanVar(value=False)
        self.run_dir = tk.StringVar()
        self.iamc_enabled = tk.BooleanVar(value=cfg.iamc_enabled)
        self.iamc_model = tk.StringVar(value=cfg.iamc_model or suggest_model_name(cfg.country))
        self.status_text = tk.StringVar(value="Idle.")
        self.progress_value = tk.DoubleVar(value=0.0)
        self._viewer_url: Optional[str] = None

        self._build_ui()

    # ---- UI --------------------------------------------------------------
    def _build_ui(self) -> None:
        pad = {"padx": 10, "pady": 5}

        tk.Label(self, text="Workbook:").grid(row=0, column=0, sticky="w", **pad)
        tk.Entry(self, textvariable=self.workbook_path, width=64).grid(row=0, column=1, **pad)
        tk.Button(self, text="Browse", command=self.select_workbook).grid(row=0, column=2, **pad)

        tk.Label(self, text="Export folder:").grid(row=1, column=0, sticky="w", **pad)
        tk.Entry(self, textvariable=self.output_dir, width=64).grid(row=1, column=1, **pad)
        tk.Button(self, text="Browse", command=self.select_output_dir).grid(row=1, column=2, **pad)

        opts = tk.Frame(self)
        opts.grid(row=2, column=0, columnspan=3, sticky="w", **pad)
        tk.Label(opts, text="Engine:").pack(side="left")
        ttk.Combobox(
            opts, textvariable=self.engine, width=12, state="readonly",
            values=["auto", *_ORDER],
        ).pack(side="left", padx=(4, 16))
        tk.Label(opts, text="Parallel Excel processes:").pack(side="left")
        tk.Spinbox(opts, from_=1, to=32, textvariable=self.workers, width=4).pack(side="left", padx=4)
        tk.Checkbutton(
            opts, text="Skip recalc (bundle from an existing run)",
            variable=self.skip_recalc, command=self._toggle_skip,
        ).pack(side="left", padx=16)

        self.run_dir_entry = tk.Entry(self, textvariable=self.run_dir, width=64, state="disabled")
        self.run_dir_entry.grid(row=3, column=1, **pad)
        self.run_dir_btn = tk.Button(self, text="Pick run dir", command=self.select_run_dir, state="disabled")
        self.run_dir_btn.grid(row=3, column=2, **pad)
        tk.Label(self, text="Existing run:").grid(row=3, column=0, sticky="w", **pad)

        tk.Label(self, text="IAMC model:").grid(row=4, column=0, sticky="w", **pad)
        iamc = tk.Frame(self)
        iamc.grid(row=4, column=1, columnspan=2, sticky="w", **pad)
        tk.Entry(iamc, textvariable=self.iamc_model, width=40).pack(side="left")
        tk.Checkbutton(
            iamc, text="Also write IAMC timeseries (<run dir>/iamc/)",
            variable=self.iamc_enabled,
        ).pack(side="left", padx=8)

        ttk.Progressbar(
            self, orient="horizontal", length=680, mode="determinate",
            variable=self.progress_value,
        ).grid(row=5, column=0, columnspan=3, **pad)
        tk.Label(self, textvariable=self.status_text, anchor="w").grid(
            row=6, column=0, columnspan=3, sticky="we", **pad
        )

        btns = tk.Frame(self)
        btns.grid(row=7, column=0, columnspan=3, pady=12)
        self.run_btn = tk.Button(btns, text="Run", width=16, command=self.run)
        self.run_btn.pack(side="left", padx=6)
        tk.Button(btns, text="Open viewer", width=16, command=self.open_viewer).pack(side="left", padx=6)
        tk.Button(btns, text="Legacy dashboard", width=16, command=self.launch_streamlit).pack(side="left", padx=6)

    def _toggle_skip(self) -> None:
        state = "normal" if self.skip_recalc.get() else "disabled"
        self.run_dir_entry.configure(state=state)
        self.run_dir_btn.configure(state=state)

    def select_workbook(self) -> None:
        path = filedialog.askopenfilename(
            title="Select FABLE workbook",
            filetypes=[("Excel files", "*.xlsx *.xlsm"), ("All files", "*.*")],
        )
        if path:
            self.workbook_path.set(path)

    def select_output_dir(self) -> None:
        path = filedialog.askdirectory(title="Select export folder")
        if path:
            self.output_dir.set(path)

    def select_run_dir(self) -> None:
        path = filedialog.askdirectory(title="Select an all_pathways_run_* directory")
        if path:
            self.run_dir.set(path)

    # ---- run -----------------------------------------------------------
    def _set_status(self, text: str) -> None:
        self.after(0, lambda: self.status_text.set(text))

    def _progress(self, idx: int, total: int, pathway: str, status: str) -> None:
        def _update() -> None:
            self.progress_value.set(100.0 * idx / max(total, 1))
            self.status_text.set("Done." if status == "done" else f"[{idx}/{total}] {pathway}")
        self.after(0, _update)

    def run(self) -> None:
        wb = self.workbook_path.get().strip()
        if not self.skip_recalc.get() and not Path(wb).exists():
            messagebox.showerror("Missing workbook", f"Not found: {wb}")
            return
        self.run_btn.configure(state="disabled")
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self) -> None:
        try:
            out = _VIEWER_DATA
            country = self.cfg.country
            baseline = self.cfg.baseline_pathway
            iamc = None
            if self.iamc_enabled.get():
                iamc = IamcOptions(
                    model=self.iamc_model.get().strip() or suggest_model_name(country),
                    region=self.cfg.iamc_region or country,
                    scenario_names=self.cfg.iamc_scenario_names,
                    kyoto_gwp=self.cfg.iamc_kyoto_gwp,
                )
            if self.skip_recalc.get():
                run_dir = Path(self.run_dir.get().strip())
                if not run_dir.exists():
                    raise FileNotFoundError(f"run dir not found: {run_dir}")
                self._set_status(f"Bundling {run_dir.name} ...")
                bundle, gate = bundle_from_run_dir(
                    run_dir, out, workbook_path=Path(self.workbook_path.get() or ""),
                    country=country, baseline_pathway=baseline, iamc=iamc,
                )
            else:
                self._set_status("Recalculating pathways ...")
                bundle, gate = run_pipeline(
                    Path(self.workbook_path.get()), out,
                    engine=self.engine.get(),
                    output_root=Path(self.output_dir.get()),
                    country=country, baseline_pathway=baseline,
                    workers=int(self.workers.get()), iamc=iamc,
                )
            msg = (
                f"{'OK' if gate.publishable else 'BLOCKED'} — "
                f"{len(bundle.pathways)} pathways, {len(bundle.tables)} tables, "
                f"status={bundle.run_quality.status}\nwrote {out / 'bundle.json'}"
            )
            if iamc is not None:
                run_dir_used = (
                    Path(self.run_dir.get().strip()) if self.skip_recalc.get()
                    else Path(self.output_dir.get()) / bundle.source.run_id
                )
                if bundle.iamc is not None:
                    msg += f"\nIAMC files ({iamc.model}): {run_dir_used / 'iamc'}"
                else:
                    msg += "\nIAMC export failed; see the terminal for the reason."
            self._set_status(msg.replace("\n", "  "))
            self.after(0, lambda: messagebox.showinfo("Done", msg))
        except Exception as exc:  # noqa: BLE001
            self._set_status(f"Failed: {exc}")
            self.after(0, lambda: messagebox.showerror("Run failed", str(exc)))
        finally:
            self.after(0, lambda: self.run_btn.configure(state="normal"))

    # ---- open results ------------------------------------------------
    def open_viewer(self) -> None:
        # The built site cannot run from file://, so serve it on 127.0.0.1.
        # Data requests are answered from viewer/public/data, so the bundle
        # written by the last run shows without rebuilding the site.
        if (_REPO_ROOT / "viewer" / "dist" / "index.html").exists():
            if self._viewer_url is None:
                _, self._viewer_url = start_server(data=_VIEWER_DATA)
            webbrowser.open(self._viewer_url)
            self._set_status(f"Viewer running at {self._viewer_url}")
            return
        try:
            subprocess.Popen(["npm", "run", "dev"], cwd=str(_REPO_ROOT / "viewer"))
            self._set_status("Started `npm run dev`. Open the localhost URL it prints.")
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror(
                "Viewer",
                f"Build the viewer first:\n    cd viewer && npm ci && npm run build\n\n{exc}",
            )

    def launch_streamlit(self) -> None:
        dash = Path(__file__).parent / "dashboard.py"
        if not dash.exists():
            messagebox.showerror("Missing", f"Not found: {dash}")
            return
        try:
            subprocess.Popen([sys.executable, "-m", "streamlit", "run", str(dash)], cwd=str(dash.parent))
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Streamlit error", str(exc))


if __name__ == "__main__":
    FableLauncher().mainloop()
