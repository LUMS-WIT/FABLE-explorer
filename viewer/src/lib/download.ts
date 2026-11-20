// Client-side file downloads (no server involved).

import { Scalar } from "../bundle/types";

function csvCell(v: Scalar): string {
  if (v === null || v === undefined) return "";
  const s = String(v);
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export function toCsv(columns: string[], rows: Scalar[][]): string {
  const lines = [columns.map(csvCell).join(",")];
  for (const r of rows) lines.push(r.map(csvCell).join(","));
  return lines.join("\n") + "\n";
}

export function downloadText(filename: string, text: string, mime = "text/csv"): void {
  const blob = new Blob([text], { type: `${mime};charset=utf-8` });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function safeFilename(s: string): string {
  return s.replace(/[^A-Za-z0-9.]+/g, "_").replace(/^_+|_+$/g, "") || "export";
}
