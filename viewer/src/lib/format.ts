export function fmtNum(v: number | null | undefined, digits = 3): string {
  if (v === null || v === undefined || !Number.isFinite(v)) return "–";
  const a = Math.abs(v);
  if (a !== 0 && (a >= 1e6 || a < 1e-3)) return v.toExponential(2);
  return v.toLocaleString(undefined, { maximumFractionDigits: digits });
}

export function fmtCell(v: unknown, digits = 3): string {
  if (v === null || v === undefined || v === "") return "–";
  if (typeof v === "number") return fmtNum(v, digits);
  if (typeof v === "boolean") return v ? "yes" : "no";
  return String(v);
}

export function fmtDate(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toISOString().slice(0, 16).replace("T", " ") + " UTC";
}
