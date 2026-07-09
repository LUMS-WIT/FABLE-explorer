#!/usr/bin/env python
"""
FABLE Pakistan — Export ALL scenarios as one coloured PDF
=========================================================
Usage (Anaconda Prompt):
    cd C:\\Users\\wit\\Documents\\FABLE_Pakistan
    python export_all_pdf.py

Output:
    FABLE_All_Scenarios.pdf   (same folder)

Requirements (one-time install):
    pip install playwright reportlab
    playwright install chromium
"""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path

# ── 1. Locate the src/ folder so we can import dashboard helpers ──────────────
SCRIPT_DIR = Path(__file__).resolve().parent
SRC_DIR = SCRIPT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# ── 2. Imports from dashboard / comparison ────────────────────────────────────
try:
    from dashboard import (
        build_curated_figures,
        find_run_dirs,
        get_pathways_from_tables,
    )
    from comparison import safe_name
except ImportError as e:
    print(f"[ERROR] Cannot import dashboard helpers: {e}")
    print("Make sure you run this script from the FABLE_Pakistan root folder.")
    sys.exit(1)

import plotly.graph_objects as go

# ── 3. PDF helpers ────────────────────────────────────────────────────────────
try:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        Image as RLImage,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
    )
except ImportError:
    print("[ERROR] reportlab not installed.  Run:  pip install reportlab")
    sys.exit(1)

# ── 4. Playwright check ───────────────────────────────────────────────────────
try:
    from playwright.sync_api import sync_playwright  # type: ignore
    PLAYWRIGHT_OK = True
except ImportError:
    PLAYWRIGHT_OK = False
    print("[WARNING] playwright not installed — falling back to kaleido.")
    print("For full colours run:  pip install playwright  &&  playwright install chromium")


# ── 5. Figure → PNG (full colour) ─────────────────────────────────────────────
def fig_to_png(fig: go.Figure, width: int = 1400, height: int = 780) -> bytes:
    """Render a Plotly figure to a full-colour PNG via playwright (best) or kaleido."""

    # Force explicit colour theme so nothing renders black
    fig = go.Figure(fig)
    fig.update_layout(
        template="plotly",
        paper_bgcolor="white",
        plot_bgcolor="white",
    )

    # ── playwright (recommended) ──────────────────────────────────────────────
    if PLAYWRIGHT_OK:
        html_str = fig.to_html(
            full_html=True,
            include_plotlyjs="cdn",
            config={"staticPlot": True},
        )
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                page = browser.new_page(viewport={"width": width, "height": height})
                page.set_content(html_str)
                page.wait_for_timeout(1800)          # let Plotly finish rendering
                png = page.screenshot(full_page=False)
                browser.close()
            return png
        except Exception as exc:
            print(f"  [playwright error] {exc} — trying kaleido fallback")

    # ── kaleido fallback ─────────────────────────────────────────────────────
    import tempfile
    try:
        import kaleido  # type: ignore
        if hasattr(kaleido, "write_fig"):          # kaleido >= 1.0
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = tmp.name
            kaleido.write_fig(fig, tmp_path, width=width, height=height, scale=2)
        else:                                      # kaleido 0.2.x
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp_path = tmp.name
            fig.write_image(tmp_path, width=width, height=height, scale=2)
        with open(tmp_path, "rb") as fh:
            data = fh.read()
        os.unlink(tmp_path)
        return data
    except Exception as exc:
        raise RuntimeError(
            f"Cannot render figure to PNG.\n"
            f"Install playwright:  pip install playwright && playwright install chromium\n"
            f"Original error: {exc}"
        )


# ── 6. Build the PDF ──────────────────────────────────────────────────────────
def build_pdf(run_dir: Path, pathways: list[str], out_path: Path) -> None:
    page_size = landscape(A4)
    page_w, page_h = page_size
    img_w = page_w - 2 * cm
    img_h = img_w * 0.55

    styles = getSampleStyleSheet()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=page_size,
        leftMargin=1 * cm,
        rightMargin=1 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )

    story = []

    # ── Cover page ────────────────────────────────────────────────────────────
    story.append(Spacer(1, 4 * cm))
    story.append(Paragraph("FABLE Pakistan", styles["Title"]))
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph("All-Scenarios Graph Report", styles["Heading1"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(f"Scenarios: {', '.join(pathways)}", styles["Normal"]))
    story.append(PageBreak())

    total_pathways = len(pathways)
    for p_idx, pathway in enumerate(pathways, 1):
        print(f"\n[{p_idx}/{total_pathways}] Pathway: {pathway}")

        # Section heading page
        story.append(Spacer(1, 2 * cm))
        story.append(Paragraph(f"Scenario: {pathway}", styles["Title"]))
        story.append(PageBreak())

        figs = build_curated_figures(run_dir, pathway)
        total_figs = len(figs)
        print(f"  Found {total_figs} charts")

        for f_idx, (name, fig) in enumerate(figs, 1):
            chart_title = fig.layout.title.text or name.replace("_", " ").title()
            print(f"  Rendering {f_idx}/{total_figs}: {chart_title} ...", end=" ", flush=True)

            try:
                png_bytes = fig_to_png(fig)
                print("OK")
            except Exception as exc:
                print(f"FAILED ({exc})")
                story.append(Paragraph(f"[Chart could not be rendered: {chart_title}]", styles["Normal"]))
                story.append(PageBreak())
                continue

            story.append(Paragraph(chart_title, styles["Heading2"]))
            story.append(Spacer(1, 0.2 * cm))
            img_buf = io.BytesIO(png_bytes)
            story.append(RLImage(img_buf, width=img_w, height=img_h))
            story.append(PageBreak())

    print("\nBuilding PDF file ...", end=" ", flush=True)
    doc.build(story)
    out_path.write_bytes(buf.getvalue())
    print("Done!")


# ── 7. Main ───────────────────────────────────────────────────────────────────
def main() -> None:
    # Find the latest run folder
    search_root = SCRIPT_DIR
    run_dirs = find_run_dirs(search_root)
    if not run_dirs:
        print(f"[ERROR] No 'all_pathways_run_*' folder found under {search_root}")
        sys.exit(1)

    run_dir = run_dirs[0]
    print(f"Run folder: {run_dir}")

    pathways = get_pathways_from_tables(run_dir)
    if not pathways:
        print("[ERROR] No pathways found in combined tables.")
        sys.exit(1)

    print(f"Pathways found: {pathways}")

    out_path = SCRIPT_DIR / "FABLE_All_Scenarios.pdf"
    print(f"Output PDF: {out_path}\n")

    build_pdf(run_dir, pathways, out_path)

    size_mb = out_path.stat().st_size / 1_048_576
    print(f"\n✅ Done!  PDF saved to: {out_path}  ({size_mb:.1f} MB)")


if __name__ == "__main__":
    main()
