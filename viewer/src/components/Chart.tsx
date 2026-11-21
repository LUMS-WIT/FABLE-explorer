// Thin wrapper over react-plotly.js bound to the small "basic" Plotly build
// (scatter + bar + pie only) to keep the bundle light. Styling follows the
// site's tokens: hairline solid grid, recessive axes, text in ink colours.

import { useMemo } from "react";
import createPlotlyComponent from "react-plotly.js/factory";
// @ts-expect-error - no types for the dist-min entry
import Plotly from "plotly.js-basic-dist-min";
import type { Data } from "plotly.js";
import { chartTheme, seriesColor, useColorScheme } from "../lib/theme";

const Plot = createPlotlyComponent(Plotly);

export { seriesColor };

export default function Chart({
  data,
  title,
  xTitle,
  yTitle,
  height = 420,
  barmode,
  showLegend = true,
  horizontal = false,
  margin,
  shapes,
}: {
  data: Data[];
  title?: string;
  xTitle?: string;
  yTitle?: string;
  height?: number;
  barmode?: "group" | "stack" | "overlay" | "relative";
  showLegend?: boolean;
  horizontal?: boolean;
  margin?: Partial<{ l: number; r: number; t: number; b: number }>;
  shapes?: object[];
}) {
  const dark = useColorScheme();
  const layout = useMemo(() => {
    const t = chartTheme();
    const axis = (titleText?: string) => ({
      title: titleText ? { text: titleText, font: { size: 12, color: t.muted } } : undefined,
      gridcolor: t.grid,
      linecolor: t.grid,
      zerolinecolor: t.muted,
      zerolinewidth: 1,
      tickfont: { size: 11, color: t.muted },
      automargin: true,
    });
    return {
      title: title
        ? { text: title, font: { size: 14, color: t.ink }, x: 0, xanchor: "left" as const, y: 0.98 }
        : undefined,
      autosize: true,
      height,
      margin: { l: 56, r: 24, t: title ? 44 : 12, b: 48, ...margin },
      paper_bgcolor: "rgba(0,0,0,0)",
      plot_bgcolor: "rgba(0,0,0,0)",
      font: { color: t.ink, size: 12, family: t.font },
      xaxis: { ...axis(xTitle), showgrid: horizontal },
      yaxis: { ...axis(yTitle), showgrid: !horizontal },
      showlegend: showLegend,
      legend: { orientation: "h" as const, y: -0.18, font: { size: 12, color: t.ink } },
      hoverlabel: { bgcolor: t.surface, bordercolor: t.grid, font: { color: t.ink, family: t.font } },
      hovermode: "closest" as const,
      barmode,
      bargap: 0.35,
      shapes,
    };
    // dark is a dependency so tokens are re-read after an OS theme switch
  }, [title, xTitle, yTitle, height, barmode, showLegend, horizontal, margin, shapes, dark]);

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
