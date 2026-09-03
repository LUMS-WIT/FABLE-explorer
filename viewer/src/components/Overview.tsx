import { Bundle } from "../bundle/types";
import { fmtDate } from "../lib/format";
import { prettyTableKey } from "../lib/labels";

export default function Overview({ bundle }: { bundle: Bundle }) {
  const s = bundle.source;
  return (
    <div className="stack">
      <section className="card">
        <h3>Source</h3>
        <dl className="kv">
          <dt>Country</dt><dd>{s.country}</dd>
          <dt>Workbook</dt><dd><code>{s.workbook_filename}</code></dd>
          <dt>Recalc engine</dt><dd>{s.recalc_engine}</dd>
          <dt>Run</dt><dd><code>{s.run_id}</code></dd>
          <dt>Generated</dt><dd>{fmtDate(s.generated_at)}</dd>
          <dt>Schema</dt><dd>v{bundle.schema_version} · {bundle.generator}</dd>
          {s.workbook_sha256 && (
            <>
              <dt>Workbook SHA-256</dt>
              <dd><code className="hash">{s.workbook_sha256}</code></dd>
            </>
          )}
        </dl>
      </section>

      <section className="card">
        <h3>Pathways ({bundle.pathways.length})</h3>
        <ul className="tag-list">
          {bundle.pathways.map((p) => (
            <li key={p} className={p === bundle.baseline_pathway ? "tag base" : "tag"}>
              {p}
              {p === bundle.baseline_pathway ? " · baseline" : ""}
            </li>
          ))}
        </ul>
      </section>

      <section className="card">
        <h3>Output tables ({bundle.tables.length})</h3>
        <table className="grid compact">
          <thead>
            <tr><th>Table</th><th>Sheet</th><th className="num">Rows</th><th className="num">Metrics</th></tr>
          </thead>
          <tbody>
            {bundle.tables.map((t) => (
              <tr key={t.key}>
                <td title={t.key}>{prettyTableKey(t.key)}</td>
                <td>{t.sheet}</td>
                <td className="num">{t.rows.length.toLocaleString()}</td>
                <td className="num">{t.numeric_cols.length}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
