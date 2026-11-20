import { useMemo, useState } from "react";
import { Bundle } from "../bundle/types";
import { BaselineMode, Row, buildSeries, num, toObjects, uniqueStrings } from "../lib/table";

// First metric whose values actually vary, so the opening chart is not flat.
function defaultMetric(rows: Row[], cols: string[]): string {
  for (const c of cols) {
    let lo = Infinity;
    let hi = -Infinity;
    for (const r of rows) {
      const v = num(r[c]);
      if (v === null) continue;
      if (v < lo) lo = v;
      if (v > hi) hi = v;
      if (hi > lo) return c;
    }
  }
  return cols[0] ?? "";
}

// Dimension values ordered by size of the metric, largest first.
function byMagnitude(rows: Row[], dim: string, metric: string): string[] {
  const tot = new Map<string, number>();
  for (const r of rows) {
    const k = r[dim];
    if (typeof k !== "string" || !k) continue;
    tot.set(k, (tot.get(k) ?? 0) + Math.abs(num(r[metric]) ?? 0));
  }
  return [...tot.entries()].sort((a, b) => b[1] - a[1]).map(([k]) => k);
}
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
  const [metric, setMetric] = useState<string | null>(null);

  // secondary dimension filters (everything dimensional except the x axis)
  const extraDims = (table?.dimension_cols ?? []).filter((d) => d !== xCol);
  const rowsObj = useMemo(() => (table ? toObjects(table) : []), [table]);
  const [dimFilter, setDimFilter] = useState<Record<string, string>>({});

  const effMetric = useMemo(() => {
    const cols = table?.numeric_cols ?? [];
    if (metric && cols.includes(metric)) return metric;
    return defaultMetric(rowsObj, cols);
  }, [table, metric, rowsObj]);

  // One line per pathway needs exactly one row per x value, so every extra
  // dimension with several values gets a selector. Selectors cascade: each
  // lists only values present under the earlier choices, defaulting to the first.
  const dimChoices = useMemo(() => {
    const out: { dim: string; options: string[]; value: string }[] = [];
    let pool = rowsObj;
    for (const d of extraDims) {
      if (uniqueStrings(pool, d).length < 2) continue;
      const options = byMagnitude(pool, d, effMetric);
      const want = dimFilter[d];
      const value = want !== undefined && options.includes(want) ? want : options[0];
      out.push({ dim: d, options, value });
      pool = pool.filter((r) => String(r[d] ?? "") === value);
    }
    return out;
  }, [rowsObj, extraDims.join("\u0000"), dimFilter, effMetric]);
  const effFilter = useMemo(
    () => Object.fromEntries(dimChoices.map((c) => [c.dim, c.value])),
    [dimChoices],
  );


  const series = useMemo(() => {
    if (!table || !effMetric) return [];
    return buildSeries(table, effMetric, {
      pathways: bundle.pathways.filter((p) => selected.has(p)),
      xCol,
      baseline,
      mode,
      filters: effFilter,
    });
  }, [table, effMetric, bundle.pathways, selected, xCol, baseline, mode, effFilter]);

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
          <select value={tableKey} onChange={(e) => { setTableKey(e.target.value); setDimFilter({}); setMetric(null); }}>
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
        {dimChoices.map(({ dim: d, options: opts, value }) => {
          return (
            <label key={d}>
              {prettyLabel(d)}
              <select
                value={value}
                onChange={(e) => setDimFilter((f) => ({ ...f, [d]: e.target.value }))}
              >
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
          title={`${prettyTableKey(table.key)} — ${prettyLabel(effMetric)}${dimChoices.length ? ` (${dimChoices.map((c) => c.value).join(", ")})` : ""}`}
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
