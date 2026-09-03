import { useMemo, useState } from "react";
import { Bundle } from "../bundle/types";
import { BaselineMode, buildSeries, toObjects, uniqueStrings } from "../lib/table";
import { prettyLabel, prettyTableKey } from "../lib/labels";
import Chart, { seriesColor } from "./Chart";
import DataGrid from "./DataGrid";
import PathwayPicker from "./PathwayPicker";

export default function TableExplorer({ bundle }: { bundle: Bundle }) {
  const [tableKey, setTableKey] = useState(bundle.tables[0]?.key ?? "");
  const table = bundle.tables.find((t) => t.key === tableKey) ?? bundle.tables[0];

  const [selected, setSelected] = useState<Set<string>>(
    () => new Set(bundle.pathways),
  );
  const [baseline, setBaseline] = useState(bundle.baseline_pathway);
  const [mode, setMode] = useState<BaselineMode>("raw");

  const xCol = table?.year_col ?? table?.dimension_cols[0] ?? table?.columns[1] ?? "";
  const [metric, setMetric] = useState(table?.numeric_cols[0] ?? "");

  // secondary dimension filters (everything dimensional except the x axis)
  const extraDims = (table?.dimension_cols ?? []).filter((d) => d !== xCol);
  const rowsObj = useMemo(() => (table ? toObjects(table) : []), [table]);
  const [dimFilter, setDimFilter] = useState<Record<string, string>>({});

  const effMetric = table?.numeric_cols.includes(metric)
    ? metric
    : table?.numeric_cols[0] ?? "";

  const series = useMemo(() => {
    if (!table || !effMetric) return [];
    return buildSeries(table, effMetric, {
      pathways: bundle.pathways.filter((p) => selected.has(p)),
      xCol,
      baseline,
      mode,
      filters: dimFilter,
    });
  }, [table, effMetric, bundle.pathways, selected, xCol, baseline, mode, dimFilter]);

  const chartData = series.map((s) => {
    const idx = bundle.pathways.indexOf(s.pathway);
    return {
      type: "scatter" as const,
      mode: "lines+markers" as const,
      name: s.pathway,
      x: s.x,
      y: s.y,
      line: { color: seriesColor(idx), width: 2 },
      marker: { size: 5 },
    };
  });

  const yTitle =
    mode === "raw"
      ? prettyLabel(effMetric)
      : mode === "delta"
        ? `${prettyLabel(effMetric)} — Δ vs ${baseline}`
        : `${prettyLabel(effMetric)} — % Δ vs ${baseline}`;

  if (!table) return <p>No tables in this bundle.</p>;

  return (
    <div className="stack">
      <div className="toolbar">
        <label>
          Table
          <select value={tableKey} onChange={(e) => { setTableKey(e.target.value); setDimFilter({}); }}>
            {bundle.tables.map((t) => (
              <option key={t.key} value={t.key}>
                {prettyTableKey(t.key)}
              </option>
            ))}
          </select>
        </label>
        <label>
          Metric
          <select value={effMetric} onChange={(e) => setMetric(e.target.value)}>
            {table.numeric_cols.map((c) => (
              <option key={c} value={c}>
                {prettyLabel(c)}
              </option>
            ))}
          </select>
        </label>
        <span className="muted">x-axis: {prettyLabel(xCol)}</span>
        {extraDims.map((d) => {
          const opts = uniqueStrings(rowsObj, d);
          if (opts.length < 2) return null;
          return (
            <label key={d}>
              {prettyLabel(d)}
              <select
                value={dimFilter[d] ?? ""}
                onChange={(e) =>
                  setDimFilter((f) => {
                    const n = { ...f };
                    if (e.target.value) n[d] = e.target.value;
                    else delete n[d];
                    return n;
                  })
                }
              >
                <option value="">(all)</option>
                {opts.map((o) => (
                  <option key={o} value={o}>
                    {o}
                  </option>
                ))}
              </select>
            </label>
          );
        })}
      </div>

      <PathwayPicker
        pathways={bundle.pathways}
        selected={selected}
        onToggle={(p) =>
          setSelected((s) => {
            const n = new Set(s);
            n.has(p) ? n.delete(p) : n.add(p);
            return n;
          })
        }
        baseline={baseline}
        onBaseline={setBaseline}
        mode={mode}
        onMode={setMode}
      />

      <div className="card">
        <Chart
          data={chartData}
          title={`${prettyTableKey(table.key)} — ${prettyLabel(effMetric)}`}
          xTitle={prettyLabel(xCol)}
          yTitle={yTitle}
        />
      </div>

      <details className="card">
        <summary>Raw table ({table.rows.length.toLocaleString()} rows)</summary>
        <DataGrid columns={table.columns} rows={rowsObj} />
      </details>
    </div>
  );
}
