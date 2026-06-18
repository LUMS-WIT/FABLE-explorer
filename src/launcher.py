#!/usr/bin/env python
"""
Tkinter launcher for FABLE Pakistan all-pathways runner + Streamlit dashboard.

Buttons:
1) Select workbook
2) Select export folder
3) Run dashboard (runs exports first)
"""

from __future__ import annotations

import subprocess
import threading
import sys
from pathlib import Path
from typing import Optional

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from runner import run_all_pathways


class FableLauncher(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("FABLE Pakistan Launcher")
        self.geometry("640x360")
        self.resizable(False, False)

        self.workbook_path = tk.StringVar()
        self.output_dir = tk.StringVar()
        self.status_text = tk.StringVar(value="Idle.")

        self.progress = ttk.Progressbar(self, orient="horizontal", length=560, mode="determinate")
        self.progress_value = tk.DoubleVar(value=0.0)
        self.progress.configure(variable=self.progress_value)

        self._build_ui()

    def _build_ui(self) -> None:
        pad = {"padx": 10, "pady": 6}

        tk.Label(self, text="Workbook:").grid(row=0, column=0, sticky="w", **pad)
        tk.Entry(self, textvariable=self.workbook_path, width=70).grid(
            row=0, column=1, sticky="w", **pad
        )
        tk.Button(self, text="Select Workbook", command=self.select_workbook).grid(
            row=0, column=2, sticky="w", **pad
        )

        tk.Label(self, text="Export folder:").grid(row=1, column=0, sticky="w", **pad)
        tk.Entry(self, textvariable=self.output_dir, width=70).grid(
            row=1, column=1, sticky="w", **pad
        )
        tk.Button(self, text="Select Export Folder", command=self.select_output_dir).grid(
            row=1, column=2, sticky="w", **pad
        )

        self.progress.grid(row=3, column=0, columnspan=3, **pad)
        tk.Label(self, textvariable=self.status_text).grid(
            row=4, column=0, columnspan=3, sticky="w", **pad
        )

        tk.Button(self, text="Run Dashboard", command=self.run_dashboard).grid(
            row=5, column=1, sticky="w", **pad
        )

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

    def _set_status(self, text: str) -> None:
        self.status_text.set(text)

    def _progress_callback(self, idx: int, total: int, pathway: str, status: str) -> None:
        def _update() -> None:
            self.progress.configure(maximum=total)
            self.progress_value.set(idx)
            if status == "done":
                self._set_status("Done.")
            else:
                self._set_status(f"[{idx}/{total}] {pathway}")

        self.after(0, _update)

    def _run_exports(self, workbook: Path, output_root: Path) -> Optional[Path]:
        try:
            self._set_status("Starting exports...")
            run_dir = run_all_pathways(
                workbook_path=workbook,
                output_root=output_root,
                excel_visible=False,
                progress_callback=self._progress_callback,
            )
            self._set_status(f"Exports complete: {run_dir}")
            return run_dir
        except Exception as exc:
            self.after(0, lambda: messagebox.showerror("Run failed", str(exc)))
            self._set_status("Run failed.")
            return None

    def _launch_streamlit(self) -> None:
        dash_path = Path(__file__).parent / "dashboard.py"
        if not dash_path.exists():
            messagebox.showerror("Missing dashboard", f"Not found: {dash_path}")
            return
        try:
            subprocess.Popen(
                [sys.executable, "-m", "streamlit", "run", str(dash_path)],
                cwd=str(dash_path.parent),
            )
        except Exception as exc:
            messagebox.showerror("Streamlit error", str(exc))

    def run_dashboard(self) -> None:
        workbook = self.workbook_path.get().strip()
        output_dir = self.output_dir.get().strip()
        if not workbook:
            messagebox.showerror("Missing workbook", "Please select a workbook first.")
            return
        wb_path = Path(workbook)
        if not wb_path.exists():
            messagebox.showerror("Missing workbook", f"Not found: {wb_path}")
            return
        out_root = Path(output_dir) if output_dir else wb_path.parent / "exports"
        self.output_dir.set(str(out_root))

        def worker() -> None:
            run_dir = self._run_exports(wb_path, out_root)
            if run_dir is not None:
                self._launch_streamlit()

        threading.Thread(target=worker, daemon=True).start()


if __name__ == "__main__":
    app = FableLauncher()
    app.mainloop()
