// TypeScript mirror of fable/contract/bundle.schema.json.
// Keep in step with that file; SUPPORTED_MAJOR gates rendering.

export const SUPPORTED_MAJOR = 1;

export type Scalar = string | number | boolean | null;

export interface Source {
  workbook_filename: string;
  workbook_sha256: string;
  country: string;
  recalc_engine: "xlwings" | "libreoffice" | "precomputed-csv";
  run_id: string;
  generated_at: string;
}

export interface Table {
  key: string;
  sheet: string;
  table: string;
  columns: string[];
  rows: Scalar[][];
  pathway_col: string;
  year_col: string | null;
  dimension_cols: string[];
  numeric_cols: string[];
}

export interface Grid {
  columns: string[];
  rows: Scalar[][];
}

export interface QualityCheck {
  name: string;
  ok: boolean;
  detail: string;
}

export interface PathwayFailure {
  pathway: string;
  error: string;
}

export interface RunQuality {
  pathways_expected: number;
  pathways_ok: number;
  pathways_failed: number;
  status: "ok" | "degraded" | "failed";
  failures: PathwayFailure[];
  checks: QualityCheck[];
}

export interface Bundle {
  schema_version: string;
  generator: string;
  source: Source;
  pathways: string[];
  baseline_pathway: string;
  tables: Table[];
  deviation_summary: Grid;
  run_quality: RunQuality;
}

export function major(version: string): number {
  const n = Number.parseInt(version.split(".")[0] ?? "", 10);
  return Number.isFinite(n) ? n : NaN;
}
