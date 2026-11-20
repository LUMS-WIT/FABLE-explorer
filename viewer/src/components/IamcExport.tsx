// IAMC-format view of the bundle: the same table that the compute layer writes
// to <run_dir>/iamc/, embedded in bundle.json (schema >= 1.1.0). Works for any
// FABLE country; a bundle without an `iamc` block gets instructions instead.

import { useMemo, useState } from "react";
import { Bundle, IamcSection, Scalar } from "../bundle/types";
import { BaselineMode, Row, num, toObjects } from "../lib/table";
import { downloadText, safeFilename, toCsv } from "../lib/download";
import Chart, { seriesColor } from "./Chart";
import DataGrid from "./DataGrid";
import PathwayPicker from "./PathwayPicker";

const ID_COLS = ["Model", "Scenario", "Region", "Variable", "Unit"];
const DEFINITIONS_URL = "https://github.com/IAMconsortium/common-definitions";

function family(variable: string): string {
  return variable.split("|")[0].replace(/ \[.*\]$/, "");
}

export default function IamcExport({ bundle }: { bundle: Bundle }) {
  const iamc = bundle.iamc;
  if (!iamc || iamc.data.rows.length === 0) return <NoIamc />;
  return <IamcView bundle={bundle} iamc={iamc} />;
}

function IamcView({ bundle, iamc }: { bundle: Bundle; iamc: IamcSection }) {
  const rows = useMemo(() => toObjects(iamc.data), [iamc]);
  const years = useMemo(
    () => iamc.data.columns.filter((c) => !ID_COLS.includes(c) && num(c) !== null),
    [iamc],
  );
  const scenarios = useMemo(() => {
    const seen: string[] = [];
    // keep the bundle's pathway order where possible
    const byPathway = new Map(iamc.scenarios.map((s) => [s.pathway, s.scenario]));
    for (const p of bundle.pathways) {
      const s = byPathway.get(p);
      if (s && !seen.includes(s)) seen.push(s);
    }
    for (const r of rows) {
      const s = String(r.Scenario);
      if (!seen.includes(s)) seen.push(s);
    }
    return seen;
  }, [iamc, rows, bundle.pathways]);

  const variables = useMemo(() => {
    const out = new Map<string, string>();
    for (const r of rows) out.set(String(r.Variable), String(r.Unit));
    return [...out.entries()].sort(([a], [b]) => a.localeCompare(b));
  }, [rows]);
  const families = useMemo(
    () => [...new Set(variables.map(([v]) => family(v)))],
    [variables],
  );

  const [fam, setFam] = useState(families.includes("Agricultural Production") ? "Agricultural Production" : families[0]);
  const famVars = variables.filter(([v]) => family(v) === fam);
  const [variable, setVariable] = useState(famVars[0]?.[0] ?? "");
  const effVar = famVars.some(([v]) => v === variable) ? variable : famVars[0]?.[0] ?? "";
  const unit = variables.find(([v]) => v === effVar)?.[1] ?? "";

  const baselineScenario =
    iamc.scenarios.find((s) => s.pathway === bundle.baseline_pathway)?.scenario ?? scenarios[0];
  const [selected, setSelected] = useState<Set<string>>(() => new Set(scenarios));
  const [baseline, setBaseline] = useState(baselineScenario);
  const [mode, setMode] = useState<BaselineMode>("raw");

  const chartData = useMemo(() => {
    const byScen = new Map<string, Row>();
    for (const r of rows) if (r.Variable === effVar) byScen.set(String(r.Scenario), r);
    const base = byScen.get(baseline);
    const x = years.map(Number);
    return scenarios
      .filter((s) => selected.has(s) && byScen.has(s))
      .map((s) => {
        const r = byScen.get(s)!;
        const y = years.map((yr) => {
          const v = num(r[yr]);
          if (mode === "raw" || v === null) return v;
          const b = base ? num(base[yr]) : null;
          if (b === null) return null;
          if (mode === "delta") return v - b;
          return b === 0 ? null : ((v - b) / Math.abs(b)) * 100;
        });
        return {
          type: "scatter" as const,
          mode: "lines+markers" as const,
          name: s,
          x,
          y,
          connectgaps: false,
          line: { color: seriesColor(scenarios.indexOf(s)), width: 2 },
          marker: { size: 5 },
        };
      });
  }, [rows, effVar, scenarios, selected, baseline, mode, years]);

  const yTitle =
    mode === "raw" ? unit : mode === "delta" ? `Δ vs ${baseline} (${unit})` : `% Δ vs ${baseline}`;

  const famRows = rows.filter(
    (r) => family(String(r.Variable)) === fam && selected.has(String(r.Scenario)),
  );
  const nVars = variables.length;
  const stem = `${safeFilename(iamc.model)}_iamc`;

  const downloadAll = () =>
    downloadText(`${stem}.csv`, toCsv(iamc.data.columns, iamc.data.rows));
  const downloadSelection = () => {
    const keep = iamc.data.rows.filter((r) => selected.has(String(r[1] as Scalar)));
    downloadText(`${stem}_selected_scenarios.csv`, toCsv(iamc.data.columns, keep));
  };
  const downloadMapping = () =>
    downloadText("iamc_mapping.csv", toCsv(iamc.mapping.columns, iamc.mapping.rows));

  return (
    <div className="stack">
      <section className="card">
        <h3>IAMC timeseries</h3>
        <p className="lead">
          The results of every pathway, mapped to the variable names and units of the{" "}
          <a href={DEFINITIONS_URL} target="_blank" rel="noreferrer">
            IAMC common-definitions
          </a>
          . The file uses the standard IAMC layout and loads directly in pyam, the IIASA
          Scenario Explorer, or a spreadsheet.
        </p>
        <dl className="kv">
          <dt>Model</dt><dd>{iamc.model}</dd>
          <dt>Region</dt><dd>{iamc.region}</dd>
          <dt>Scenarios</dt><dd>{scenarios.length} (one per FABLE pathway)</dd>
          <dt>Variables</dt><dd>{nVars}</dd>
          <dt>Years</dt><dd>{years[0]}–{years[years.length - 1]}</dd>
          <dt>Kyoto Gases</dt><dd>GWP-100 {iamc.kyoto_gwp}</dd>
          <dt>Checked against</dt><dd><code className="hash">{iamc.definitions}</code></dd>
        </dl>
        <div className="button-row">
          <button className="btn primary" onClick={downloadAll}>Download IAMC CSV (all scenarios)</button>
          <button className="btn" onClick={downloadSelection} disabled={selected.size === 0}>
            Download selected scenarios
          </button>
          <button className="btn" onClick={downloadMapping}>Download variable mapping</button>
        </div>
      </section>

      <div className="toolbar">
        <label>
          Group
          <select value={fam} onChange={(e) => setFam(e.target.value)}>
            {families.map((f) => (
              <option key={f} value={f}>{f}</option>
            ))}
          </select>
        </label>
        <label className="wide">
          Variable
          <select value={effVar} onChange={(e) => setVariable(e.target.value)}>
            {famVars.map(([v]) => (
              <option key={v} value={v}>{v}</option>
            ))}
          </select>
        </label>
        <span className="muted">unit: {unit}</span>
      </div>

      <PathwayPicker
        pathways={scenarios}
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
        <Chart data={chartData} title={effVar} xTitle="Year" yTitle={yTitle} />
      </div>

      <details className="card">
        <summary>
          {fam}: {famRows.length.toLocaleString()} rows in IAMC layout
        </summary>
        <DataGrid columns={iamc.data.columns} rows={famRows} prettyHeaders={false} />
      </details>

      <details className="card">
        <summary>How each variable is computed ({iamc.mapping.rows.length})</summary>
        <DataGrid columns={iamc.mapping.columns} rows={toObjects(iamc.mapping)} prettyHeaders={false} />
      </details>

      {iamc.notes.length > 0 && (
        <details className="card">
          <summary>Export notes ({iamc.notes.length})</summary>
          <ul className="notes">
            {iamc.notes.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

function NoIamc() {
  return (
    <section className="card">
      <h3>No IAMC table in this bundle</h3>
      <p>
        This bundle was built without the IAMC export, or with a version of the tool
        older than schema 1.1.0. Rebuild it from the run directory and load the new{" "}
        <code>bundle.json</code>:
      </p>
      <pre className="cmd">
        python -m fable.compute bundle exports/&lt;run_dir&gt; --model "FABLE-&lt;Country&gt; v1"
      </pre>
      <p className="muted">
        The same command also writes <code>&lt;run_dir&gt;/iamc/</code> with the IAMC CSV,
        an Excel copy and the variable mapping. See the Guide tab for details.
      </p>
    </section>
  );
}
