import { useMemo, useState } from "react";
import { Bundle } from "../bundle/types";
import { num, toObjects, uniqueStrings } from "../lib/table";
import { prettyLabel, prettyTableKey } from "../lib/labels";
import Chart from "./Chart";
import DataGrid from "./DataGrid";

export default function DeviationAnalysis({ bundle }: { bundle: Bundle }) {
  const rows = useMemo(
    () => toObjects(bundle.deviation_summary),
    [bundle.deviation_summary],
  );

  const tables = useMemo(() => uniqueStrings(rows, "Table"), [rows]);
  const [table, setTable] = useState<string>("");
  const [sigOnly, setSigOnly] = useState(true);
  const [topN, setTopN] = useState(20);

  if (bundle.deviation_summary.rows.length === 0) {
    return (
      <p className="muted">
        No deviation summary in this bundle (needs at least two pathways with
        overlapping metrics).
      </p>
    );
  }

  const filtered = rows
    .filter((r) => (table ? r.Table === table : true))
    .filter((r) => (sigOnly ? r.SignificantDeviation === true || r.SignificantDeviation === "True" : true))
    .sort(
      (a, b) =>
        (num(b.MaxPctDiffVsBaseline) ?? -Infinity) -
        (num(a.MaxPctDiffVsBaseline) ?? -Infinity),
    );

  const top = filtered.slice(0, topN);
  const chartData = [
    {
      type: "bar" as const,
      orientation: "h" as const,
      x: top.map((r) => num(r.MaxPctDiffVsBaseline) ?? 0).reverse(),
      y: top
        .map(
          (r) =>
            `${prettyLabel(String(r.Metric))}${
              r.Group && r.Group !== "(all rows)" ? ` · ${r.Group}` : ""
            }`,
        )
        .reverse(),
      marker: { color: "#2563eb" },
      hovertemplate:
        "%{y}<br>max %Δ vs baseline: %{x:.1f}%<extra></extra>",
    },
  ];

  return (
    <div className="stack">
      <div className="toolbar">
        <label>
          Table
          <select value={table} onChange={(e) => setTable(e.target.value)}>
            <option value="">(all)</option>
            {tables.map((t) => (
              <option key={t} value={t}>
                {prettyTableKey(t)}
              </option>
            ))}
          </select>
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={sigOnly}
            onChange={(e) => setSigOnly(e.target.checked)}
          />
          Significant only
        </label>
        <label>
          Top
          <input
            type="number"
            min={5}
            max={60}
            value={topN}
            onChange={(e) => setTopN(Math.max(5, Math.min(60, +e.target.value)))}
          />
        </label>
        <span className="muted">
          {filtered.length.toLocaleString()} metric/group rows match
        </span>
      </div>

      <div className="card">
        <Chart
          data={chartData}
          title={`Largest divergence from ${bundle.baseline_pathway}`}
          xTitle="max % Δ vs baseline"
          height={Math.max(360, top.length * 26 + 90)}
        />
      </div>

      <div className="card">
        <DataGrid columns={bundle.deviation_summary.columns} rows={filtered} />
      </div>
    </div>
  );
}
