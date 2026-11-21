// Large runs: choose up to seven pathways to colour; the rest stay grey.

import { useState } from "react";
import { IamcIndex, extremes, isEnsemble } from "../lib/iamc";
import { defaultHighlight, useHighlight } from "../lib/highlight";
import { MAX_SLOTS } from "../lib/theme";

const QUICK: { label: string; variable: string; end: "low" | "high" }[] = [
  { label: "Lowest emissions", variable: "Emissions|Kyoto Gases|AFOLU", end: "low" },
  { label: "Highest emissions", variable: "Emissions|Kyoto Gases|AFOLU", end: "high" },
  { label: "Most food", variable: "Food Availability [per capita]", end: "high" },
  { label: "Least food", variable: "Food Availability [per capita]", end: "low" },
  { label: "Most forest", variable: "Land Cover|Forest", end: "high" },
];

function leverText(ix: IamcIndex, s: string): string | undefined {
  const l = ix.levers.get(s);
  if (!l) return undefined;
  return ix.leverKeys.map((k) => `${k}: ${l[k]}`).join("\n");
}

export default function HighlightPicker({ ix, year }: { ix: IamcIndex; year: number }) {
  const hl = useHighlight();
  const [query, setQuery] = useState("");
  if (!isEnsemble(ix)) return null;
  const full = hl.list.length >= MAX_SLOTS;

  const add = (s: string) => {
    if (!s || hl.has(s) || full || !ix.scenarios.includes(s)) return;
    hl.set([...hl.list, s]);
    setQuery("");
  };
  const remove = (s: string) => hl.set(hl.list.filter((x) => x !== s));

  return (
    <section className="picker-band" aria-label="Pathways to colour">
      <div className="picker-band-head">
        <p>
          <strong>{ix.scenarios.length.toLocaleString("en-GB")} pathways.</strong> Grey shows all of
          them; up to {MAX_SLOTS} chosen pathways get a colour.
        </p>
      </div>
      <div className="picked">
        {hl.list.map((s) => (
          <span key={s} className="picked-item" title={leverText(ix, s)}>
            <span className="swatch" style={{ background: hl.colorOf(s) }} />
            {s}
            {s === ix.baseline && <span className="key-note">baseline</span>}
            <button aria-label={`Remove ${s}`} onClick={() => remove(s)}>×</button>
          </span>
        ))}
        <span className="picked-add">
          <input
            list="pathway-names"
            value={query}
            placeholder={full ? `${MAX_SLOTS} chosen; remove one to add` : "Add a pathway by name"}
            disabled={full}
            onChange={(e) => {
              setQuery(e.target.value);
              if (ix.scenarios.includes(e.target.value)) add(e.target.value);
            }}
            onKeyDown={(e) => e.key === "Enter" && add(query.trim())}
            aria-label="Add a pathway by name"
          />
          <datalist id="pathway-names">
            {ix.scenarios
              .filter((s) => !hl.has(s) && (!query || s.toLowerCase().includes(query.toLowerCase())))
              .slice(0, 200)
              .map((s) => (
                <option key={s} value={s} />
              ))}
          </datalist>
        </span>
      </div>
      <div className="quick">
        <span className="muted">Add the pathway with</span>
        {QUICK.filter((q) => ix.unit.has(q.variable)).map((q) => {
          const pick = extremes(ix, q.variable, year)[q.end][0];
          return (
            <button key={q.label} className="btn-quiet" disabled={full || hl.has(pick)} onClick={() => add(pick)}>
              {q.label.toLowerCase()} in {year}
            </button>
          );
        })}
        <button className="btn-quiet" onClick={() => hl.set(defaultHighlight(ix))}>reset</button>
      </div>
    </section>
  );
}
