// Shown when a bundle has no IAMC block (built with the export off, or by a
// version of the tool older than schema 1.1.0).

export default function NoIamc({ what }: { what: string }) {
  return (
    <section className="panel empty">
      <h2>This bundle has no IAMC table</h2>
      <p>
        {what[0].toUpperCase() + what.slice(1)} is built from the IAMC table that newer bundles
        carry. Rebuild the bundle from its run directory, then open the new <code>bundle.json</code>:
      </p>
      <pre className="cmd">python -m fable.compute bundle exports/&lt;run_dir&gt; --model "FABLE-&lt;Country&gt; v1"</pre>
      <p className="muted">
        The workbook tables, deviation ranking and run details work with this bundle as it is.
      </p>
    </section>
  );
}
