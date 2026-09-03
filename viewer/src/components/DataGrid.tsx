import { useMemo, useState } from "react";
import { Scalar } from "../bundle/types";
import { Row } from "../lib/table";
import { fmtCell } from "../lib/format";
import { prettyLabel } from "../lib/labels";

type Cmp = (a: Row, b: Row) => number;

export default function DataGrid({
  columns,
  rows,
  prettyHeaders = true,
  pageSize = 40,
  maxRows = 5000,
}: {
  columns: string[];
  rows: Row[];
  prettyHeaders?: boolean;
  pageSize?: number;
  maxRows?: number;
}) {
  const [sortCol, setSortCol] = useState<string | null>(null);
  const [asc, setAsc] = useState(true);
  const [page, setPage] = useState(0);

  const sorted = useMemo(() => {
    const capped = rows.slice(0, maxRows);
    if (!sortCol) return capped;
    const cmp: Cmp = (a, b) => {
      const av = a[sortCol] as Scalar;
      const bv = b[sortCol] as Scalar;
      if (av === null) return 1;
      if (bv === null) return -1;
      if (typeof av === "number" && typeof bv === "number") return av - bv;
      return String(av).localeCompare(String(bv));
    };
    const out = [...capped].sort(cmp);
    return asc ? out : out.reverse();
  }, [rows, sortCol, asc, maxRows]);

  const pages = Math.max(1, Math.ceil(sorted.length / pageSize));
  const view = sorted.slice(page * pageSize, page * pageSize + pageSize);

  function header(c: string) {
    setPage(0);
    if (sortCol === c) setAsc(!asc);
    else {
      setSortCol(c);
      setAsc(true);
    }
  }

  return (
    <div className="grid-wrap">
      <div className="grid-scroll">
        <table className="grid">
          <thead>
            <tr>
              {columns.map((c) => (
                <th key={c} onClick={() => header(c)} title={c}>
                  {prettyHeaders ? prettyLabel(c) : c}
                  {sortCol === c ? (asc ? " ▲" : " ▼") : ""}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {view.map((r, i) => (
              <tr key={i}>
                {columns.map((c) => (
                  <td key={c} className={typeof r[c] === "number" ? "num" : ""}>
                    {fmtCell(r[c])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="grid-foot">
        <span>
          {sorted.length.toLocaleString()} rows
          {rows.length > maxRows ? ` (capped from ${rows.length.toLocaleString()})` : ""}
        </span>
        {pages > 1 && (
          <span className="pager">
            <button disabled={page === 0} onClick={() => setPage(page - 1)}>
              ‹
            </button>
            {page + 1} / {pages}
            <button disabled={page + 1 >= pages} onClick={() => setPage(page + 1)}>
              ›
            </button>
          </span>
        )}
      </div>
    </div>
  );
}
