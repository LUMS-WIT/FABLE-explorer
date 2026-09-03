// Thin wrapper over react-plotly.js bound to the small "basic" Plotly build
// (scatter + bar + pie only — all this viewer needs) to keep the bundle light.

import { useMemo } from "react";
import createPlotlyComponent from "react-plotly.js/factory";
// @ts-expect-error - no types for the dist-min entry
import Plotly from "plotly.js-basic-dist-min";
import type { Data } from "plotly.js";

const Plot = createPlotlyComponent(Plotly);

const PALETTE = [
  "#2563eb", "#dc2626", "#059669", "#d97706", "#7c3aed",
  "#0891b2", "#db2777", "#65a30d", "#475569", "#c026d3",
];

export function seriesColor(i: number): string {
  return PALETTE[i % PALETTE.length];
}

function isDark(): boolean {
  return (
    typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-color-scheme: dark)").matches
  );
}

export default function Chart({
  data,
  title,
  xTitle,
  yTitle,
  height = 460,
  barmode,
}: {
  data: Data[];
  title?: string;
  xTitle?: string;
  yTitle?: string;
  height?: number;
  barmode?: "group" | "stack" | "overlay" | "relative";
}) {
  const layout = useMemo(() => {
    const dark = isDark();
    const fg = dark ? "#e5e7eb" : "#1f2937";
    const grid = dark ? "#374151" : "#e5e7eb";
    return {
      title: title ? { text: title, font: { size: 15 } } : undefined,
      autosize: true,
      height,
      margin: { l: 64, r: 24, t: title ? 48 : 16, b: 48 },
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      font: { color: fg, size: 12 },
      xaxis: { title: xTitle ? { text: xTitle } : undefined, gridcolor: grid, zerolinecolor: grid },
      yaxis: { title: yTitle ? { text: yTitle } : undefined, gridcolor: grid, zerolinecolor: grid },
      legend: { orientation: "h" as const, y: -0.2 },
      barmode,
      colorway: PALETTE,
    };
  }, [title, xTitle, yTitle, height, barmode]);

  return (
    <Plot
      data={data}
      layout={layout as never}
      config={{ displayModeBar: false, responsive: true } as never}
      useResizeHandler
      style={{ width: "100%", height }}
    />
  );
}
