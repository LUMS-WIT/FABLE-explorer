// Landing view: where pathways end up on the headline indicators, the main
// findings, and the numbers behind them. Built from the bundle's IAMC block.

import { useMemo, useState } from "react";
import { Bundle } from "../bundle/types";
import {
  IamcIndex,
  fmtPct,
  fmtValue,
  insights,
  isEnsemble,
  keyIndicators,
  pctChange,
  referenceYear,
  shortUnit,
  spread,
  value,
} from "../lib/iamc";
import { useHighlight } from "../lib/highlight";
import DotStrip from "./DotStrip";
import HighlightPicker from "./HighlightPicker";
import NoIamc from "./NoIamc";

export default function Summary({ bundle, ix }: { bundle: Bundle; ix: IamcIndex | null }) {
  if (!ix) return <NoIamc what="the summary" />;
  return <SummaryView bundle={bundle} ix={ix} />;
}

function SummaryView({ bundle, ix }: { bundle: Bundle; ix: IamcIndex }) {
  const hl = useHighlight();
  const ref = referenceYear(ix);
  const future = ix.years.filter((y) => y > ref);
  const yearChoices = future.filter((y) => y % 10 === 0).slice(-3);
  const last = ix.years[ix.years.length - 1];
  const [year, setYear] = useState(last);
  const [focus, setFocus] = useState<string | null>(null);
  const rows = keyIndicators(ix);
  const notes = useMemo(() => insights(ix, year), [ix, year]);
  const ensemble = isEnsemble(ix);
  const n = ix.scenarios.length;
  const cols = hl.list;

  return (
    <div className="summary">
      <header className="hero">
        <div className="hero-text">
          <h1>{bundle.source.country}</h1>
          <p className="hero-lede">
            {n.toLocaleString("en-GB")} FABLE pathways for land, food and emissions, compared with{" "}
            <strong>{ix.baseline}</strong>. They share history up to {ref} and separate after it.
          </p>
        </div>
        <div className="hero-year" role="group" aria-label="Year shown">
          <span className="hero-year-label">Year</span>
          <div className="segmented">
            {(yearChoices.length ? yearChoices : [last]).map((y) => (
              <button key={y} className={y === year ? "seg-on" : ""} onClick={() => setYear(y)}>
                {y}
              </button>
            ))}
          </div>
        </div>
      </header>

      <HighlightPicker ix={ix} year={year} />

      <section className="plate">
        <div className="section-head">
          <h2>Change against {ix.baseline} in {year}</h2>
          <p className="section-sub">
            One row per headline indicator, on a shared scale.
            {ensemble ? " Grey bars count pathways; dots are the coloured ones." : ""}
          </p>
        </div>
        <DotStrip ix={ix} rows={rows} year={year} focus={focus} onFocus={setFocus} />
      </section>

      <section className="findings">
        <div className="section-head">
          <h2>Findings for {year}</h2>
        </div>
        <ul className="insights">
          {notes.map((note, i) => (
            <li key={i}>
              <span
                className="insight-mark"
                style={{ background: note.scenario ? hl.colorOf(note.scenario) : "var(--rule-strong)" }}
                aria-hidden
              />
              <span>{note.text}</span>
            </li>
          ))}
        </ul>
      </section>

      <section className="plate plate-table">
        <div className="section-head">
          <h2>Scorecard, {year}</h2>
          <p className="section-sub">
            Each value with its change against {ix.baseline} beneath it.
            {ensemble ? ` The last column summarises all ${n.toLocaleString("en-GB")} pathways.` : ""}
          </p>
        </div>
        <div className="scroll-x">
          <table className="scorecard">
            <thead>
              <tr>
                <th scope="col">Indicator</th>
                {cols.map((s) => (
                  <th
                    key={s}
                    scope="col"
                    className={`num ${focus && focus !== s ? "col-dim" : ""}`}
                    onMouseEnter={() => setFocus(s)}
                    onMouseLeave={() => setFocus(null)}
                  >
                    <span className="th-key">
                      <span className="swatch" style={{ background: hl.colorOf(s) }} />
                      {s}
                    </span>
                  </th>
                ))}
                {ensemble && (
                  <th scope="col" className="num th-ensemble">
                    All pathways
                    <span className="unit">median, middle 80%</span>
                  </th>
                )}
              </tr>
            </thead>
            <tbody>
              {rows.map((k) => {
                const b = value(ix, ix.baseline, k.variable, year);
                const all = ensemble ? spread(ix.scenarios.map((s) => value(ix, s, k.variable, year))) : null;
                return (
                  <tr key={k.variable}>
                    <th scope="row">
                      {k.label}
                      <span className="unit">{shortUnit(ix.unit.get(k.variable) ?? "")}</span>
                    </th>
                    {cols.map((s) => {
                      const v = value(ix, s, k.variable, year);
                      const p = s === ix.baseline ? null : pctChange(v, b);
                      return (
                        <td key={s} className={`num ${focus && focus !== s ? "col-dim" : ""}`}>
                          <span className="sc-val">{fmtValue(v)}</span>
                          <span className="sc-delta">{s === ix.baseline ? "baseline" : fmtPct(p)}</span>
                        </td>
                      );
                    })}
                    {all && (
                      <td className="num td-ensemble">
                        <span className="sc-val">{fmtValue(all.median)}</span>
                        <span className="sc-delta">
                          {fmtValue(all.p10)} to {fmtValue(all.p90)}
                        </span>
                      </td>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
