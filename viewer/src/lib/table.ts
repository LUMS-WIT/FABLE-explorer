// Row/column helpers over the columnar Table / Grid shape.

import { Grid, Scalar, Table } from "../bundle/types";

export type Row = Record<string, Scalar>;

export function toObjects(g: Grid | Table): Row[] {
  return g.rows.map((r) => {
    const o: Row = {};
    g.columns.forEach((c, i) => (o[c] = r[i] ?? null));
    return o;
  });
}

export function num(v: Scalar): number | null {
  if (v === null || v === "") return null;
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}

export function uniqueStrings(rows: Row[], col: string): string[] {
  const seen = new Set<string>();
  const out: string[] = [];
  for (const r of rows) {
    const v = r[col];
    if (typeof v === "string" && v && !seen.has(v)) {
      seen.add(v);
      out.push(v);
    }
  }
  return out;
}

export type BaselineMode = "raw" | "delta" | "pctDelta";

export const BASELINE_MODE_LABEL: Record<BaselineMode, string> = {
  raw: "Raw values",
  delta: "Δ vs baseline",
  pctDelta: "% Δ vs baseline",
};

// Series for one metric across pathways, aligned on the x column (usually Year).
export interface Series {
  pathway: string;
  x: (number | string)[];
  y: (number | null)[];
}

export function buildSeries(
  table: Table,
  metric: string,
  opts: {
    pathways: string[];
    xCol: string;
    baseline: string;
    mode: BaselineMode;
    /** extra dimension filters: {col: allowedValue} */
    filters?: Record<string, string>;
  },
): Series[] {
  const rows = toObjects(table);
  const pcol = table.pathway_col;

  const filtered = rows.filter((r) => {
    for (const [c, want] of Object.entries(opts.filters ?? {})) {
      if (String(r[c] ?? "") !== want) return false;
    }
    return true;
  });

  // index baseline by x for delta modes
  const baselineByX = new Map<string, number | null>();
  if (opts.mode !== "raw") {
    for (const r of filtered) {
      if (r[pcol] === opts.baseline) {
        baselineByX.set(String(r[opts.xCol]), num(r[metric]));
      }
    }
  }

  const out: Series[] = [];
  for (const p of opts.pathways) {
    const prows = filtered
      .filter((r) => r[pcol] === p)
      .sort((a, b) => {
        const av = num(a[opts.xCol]);
        const bv = num(b[opts.xCol]);
        if (av !== null && bv !== null) return av - bv;
        return String(a[opts.xCol]).localeCompare(String(b[opts.xCol]));
      });
    const x: (number | string)[] = [];
    const y: (number | null)[] = [];
    for (const r of prows) {
      const xvRaw = r[opts.xCol];
      const xv = num(xvRaw);
      x.push(xv !== null ? xv : String(xvRaw));
      let v = num(r[metric]);
      if (opts.mode !== "raw" && v !== null) {
        const bv = baselineByX.get(String(xvRaw));
        if (bv === null || bv === undefined) {
          v = null;
        } else if (opts.mode === "delta") {
          v = v - bv;
        } else {
          v = bv === 0 ? null : ((v - bv) / Math.abs(bv)) * 100;
        }
      }
      y.push(v);
    }
    out.push({ pathway: p, x, y });
  }
  return out;
}

export function filterGridRows(
  grid: Grid,
  predicate: (r: Row) => boolean,
): { columns: string[]; rows: Row[] } {
  return { columns: grid.columns, rows: toObjects(grid).filter(predicate) };
}
