// Compare pathways on any IAMC variable: one year side by side, the path over
// time, what a total is made of, which scenario settings move it (design runs)
// and two pathways head to head. Large runs show every pathway as a grey
// distribution with the chosen pathways in colour.

import { useMemo, useState } from "react";
import type { Data } from "plotly.js";
import {
  IamcIndex,
  children,
  family,
  fmtPct,
  fmtValue,
  isEnsemble,
  keyIndicators,
  leafName,
  leverEffects,
  pctChange,
  quantile,
  referenceYear,
  series,
  shortUnit,
  value,
} from "../lib/iamc";
import { useHighlight } from "../lib/highlight";
import { chartTheme, seriesColor } from "../lib/theme";
import Chart from "./Chart";
import HighlightPicker from "./HighlightPicker";
import NoIamc from "./NoIamc";

type Mode = "value" | "change";

export default function Compare({ ix }: { ix: IamcIndex | null }) {
  if (!ix) return <NoIamc what="pathway comparison" />;
  return <CompareView ix={ix} />;
}

function CompareView({ ix }: { ix: IamcIndex }) {
  const hl = useHighlight();
  const keys = keyIndicators(ix);
  const ensemble = isEnsemble(ix);
  const [variable, setVariable] = useState(keys[0]?.variable ?? ix.variables[0]);
  const [year, setYear] = useState(ix.years[ix.years.length - 1]);
  const [mode, setMode] = useState<Mode>("value");
  const [baseline, setBaseline] = useState(ix.baseline);
  const [a, setA] = useState(ix.baseline);
  const [b, setB] = useState(hl.list.find((s) => s !== ix.baseline) ?? ix.scenarios[1] ?? ix.baseline);

  const unit = ix.unit.get(variable) ?? "";
  const groups = useMemo(() => {
    const m = new Map<string, string[]>();
    for (const v of ix.variables) {
      const f = family(v);
      if (!m.has(f)) m.set(f, []);
      m.get(f)!.push(v);
    }
    return [...m.entries()];
  }, [ix]);
  const parts = children(ix, variable);
  const ref = referenceYear(ix);
  const shown = ensemble ? hl.list : ix.scenarios;

  return (
    <div className="compare">
      <div className="controls" role="group" aria-label="Comparison settings">
        <label className="ctl ctl-wide">
          <span>Indicator</span>
          <select value={variable} onChange={(e) => setVariable(e.target.value)}>
            <optgroup label="Headline">
              {keys.map((k) => (
                <option key={`k-${k.variable}`} value={k.variable}>{k.label}</option>
              ))}
            </optgroup>
            {groups.map(([f, vs]) => (
              <optgroup key={f} label={f}>
                {vs.map((v) => (
                  <option key={v} value={v}>{v}</option>
                ))}
              </optgroup>
            ))}
          </select>
        </label>
        <label className="ctl">
          <span>Year</span>
          <select value={year} onChange={(e) => setYear(Number(e.target.value))}>
            {ix.years.map((y) => (
              <option key={y} value={y}>{y}</option>
            ))}
          </select>
        </label>
        <div className="ctl">
          <span>Show</span>
          <div className="segmented">
            <button className={mode === "value" ? "seg-on" : ""} onClick={() => setMode("value")}>Values</button>
            <button className={mode === "change" ? "seg-on" : ""} onClick={() => setMode("change")}>Change vs baseline</button>
          </div>
        </div>
        <label className="ctl">
          <span>Baseline</span>
          <select value={baseline} onChange={(e) => setBaseline(e.target.value)}>
            {ix.scenarios.map((s) => (
              <option key={s} value={s}>{s}</option>
            ))}
          </select>
        </label>
      </div>

      <HighlightPicker ix={ix} year={year} />

      <h2 className="compare-title">
        {variable} <span className="unit">{shortUnit(unit)}</span>
      </h2>

      <div className="compare-grid">
        <section className="plate">
          <div className="section-head">
            <h3>{mode === "value" ? `In ${year}` : `Change against ${baseline}, ${year}`}</h3>
          </div>
          {ensemble && <Distribution ix={ix} variable={variable} year={year} mode={mode} baseline={baseline} />}
          <RankBars ix={ix} scenarios={shown} variable={variable} year={year} mode={mode} baseline={baseline} />
        </section>

        <section className="plate">
          <div className="section-head">
            <h3>Over time</h3>
          </div>
          <Trajectories ix={ix} variable={variable} mode={mode} baseline={baseline} year={year} ref_={ref} />
        </section>
      </div>

      {ix.leverKeys.length > 0 && ix.scenarios.length >= 12 && (
        <section className="plate">
          <div className="section-head">
            <h3>Which settings move it, {year}</h3>
            <p className="section-sub">
              Average change against {ix.baseline} across all pathways with each setting. Levers are
              sorted by how far apart their settings land.
            </p>
          </div>
          <LeverEffects ix={ix} variable={variable} year={year} />
        </section>
      )}

      {parts.length >= 2 && (
        <section className="plate">
          <div className="section-head">
            <h3>What the total is made of, {year}</h3>
            <p className="section-sub">{variable} split into its {parts.length} reported parts.</p>
          </div>
          <Composition ix={ix} scenarios={shown} variable={variable} parts={parts} year={year} />
        </section>
      )}

      <section className="plate">
        <div className="section-head head-row">
          <h3>Head to head, {year}</h3>
          <div className="h2h-pick">
            <PathwaySelect ix={ix} value={a} onChange={setA} label="First pathway" />
            <span className="muted">against</span>
            <PathwaySelect ix={ix} value={b} onChange={setB} label="Second pathway" />
          </div>
        </div>
        <HeadToHead ix={ix} a={a} b={b} year={year} extra={[variable, ...parts]} />
      </section>
    </div>
  );
}

function PathwaySelect({ ix, value: v, onChange, label }: {
  ix: IamcIndex; value: string; onChange: (s: string) => void; label: string;
}) {
  return (
    <select aria-label={label} value={v} onChange={(e) => onChange(e.target.value)}>
      {ix.scenarios.map((s) => <option key={s} value={s}>{s}</option>)}
    </select>
  );
}

// ------------------------------------------------------------------ distribution

function Distribution({ ix, variable, year, mode, baseline }: {
  ix: IamcIndex; variable: string; year: number; mode: Mode; baseline: string;
}) {
  const hl = useHighlight();
  const base = value(ix, baseline, variable, year);
  const vals = ix.scenarios
    .map((s) => {
      const v = value(ix, s, variable, year);
      return mode === "value" ? v : pctChange(v, base);
    })
    .filter((v): v is number => v !== null)
    .sort((p, q) => p - q);
  if (vals.length < 2) return null;
  const lo = quantile(vals, 0.005);
  const hi = quantile(vals, 0.995);
  const span = hi - lo || 1;
  const BINS = 48;
  const bins = new Array(BINS).fill(0);
  for (const v of vals) bins[Math.max(0, Math.min(BINS - 1, Math.floor(((v - lo) / span) * BINS)))] += 1;
  const peak = Math.max(...bins);
  const pos = (v: number) => Math.max(0, Math.min(100, ((v - lo) / span) * 100));
  return (
    <figure className="dist">
      <div className="dist-plot">
        <svg viewBox={`0 0 ${BINS} 20`} preserveAspectRatio="none" aria-hidden>
          {bins.map((c, i) =>
            c ? <rect key={i} x={i + 0.1} width={0.8} y={20 - (20 * c) / peak} height={(20 * c) / peak} /> : null,
          )}
        </svg>
        {hl.list.map((s) => {
          const v = value(ix, s, variable, year);
          const m = mode === "value" ? v : pctChange(v, base);
          if (m === null) return null;
          return (
            <span
              key={s}
              className="dist-mark"
              style={{ left: `${pos(m)}%`, background: hl.colorOf(s) }}
              title={`${s}: ${mode === "value" ? fmtValue(m, ix.unit.get(variable)) : fmtPct(m)}`}
            />
          );
        })}
      </div>
      <figcaption className="dist-axis">
        <span>{mode === "value" ? fmtValue(lo) : fmtPct(lo)}</span>
        <span className="muted">
          {vals.length.toLocaleString("en-GB")} pathways; coloured marks are the chosen ones
        </span>
        <span>{mode === "value" ? fmtValue(hi) : fmtPct(hi)}</span>
      </figcaption>
    </figure>
  );
}

// ------------------------------------------------------------------ ranked bars

function RankBars({ ix, scenarios, variable, year, mode, baseline }: {
  ix: IamcIndex; scenarios: string[]; variable: string; year: number; mode: Mode; baseline: string;
}) {
  const hl = useHighlight();
  const unit = ix.unit.get(variable) ?? "";
  const base = value(ix, baseline, variable, year);
  const rows = scenarios
    .map((s) => {
      const v = value(ix, s, variable, year);
      const m = mode === "value" ? v : pctChange(v, base);
      return { s, v, m };
    })
    .filter((r) => r.m !== null) as { s: string; v: number | null; m: number }[];
  rows.sort((p, q) => q.m - p.m);
  if (!rows.length) return <p className="muted">No values for {year}.</p>;

  const lo = Math.min(0, ...rows.map((r) => r.m));
  const hi = Math.max(0, ...rows.map((r) => r.m));
  const span = hi - lo || 1;
  const zero = ((0 - lo) / span) * 100;

  return (
    <div className="bars" role="table" aria-label={`${variable}, ${year}`}>
      {rows.map((r) => {
        const pos = ((r.m - lo) / span) * 100;
        const left = Math.min(zero, pos);
        const width = Math.abs(pos - zero);
        const neg = r.m < 0;
        const label = mode === "value" ? fmtValue(r.v) : r.s === baseline ? "baseline" : fmtPct(r.m);
        return (
          <div className="bar-row" role="row" key={r.s}>
            <span className="bar-name" role="rowheader">
              <span className="swatch" style={{ background: hl.colorOf(r.s) }} />
              {r.s}
            </span>
            <span className="bar-track" role="cell">
              {lo < 0 && hi > 0 && <span className="bar-zero" style={{ left: `${zero}%` }} />}
              <span
                className={`bar ${neg ? "bar-neg" : ""}`}
                style={{ left: `${left}%`, width: `${Math.max(width, 0.4)}%`, background: hl.colorOf(r.s) }}
                title={`${r.s}: ${fmtValue(r.v, unit)}${r.s !== baseline ? `, ${fmtPct(pctChange(r.v, base))} against ${baseline}` : ""}`}
              />
              <span
                className={`bar-label ${neg ? "bar-label-neg" : ""}`}
                style={neg ? { right: `${100 - left}%` } : { left: `${left + width}%` }}
              >
                {label}
              </span>
            </span>
          </div>
        );
      })}
      <p className="note">
        {mode === "value" ? shortUnit(unit) : `% change against ${baseline}`}, largest first.
      </p>
    </div>
  );
}

// ------------------------------------------------------------------ trajectories

function sig(v: number | null): number | null {
  // 6 significant figures: removes float noise that would draw a flat total as a zig-zag
  return v === null ? null : Number(v.toPrecision(6));
}

function Trajectories({ ix, variable, mode, baseline, year, ref_ }: {
  ix: IamcIndex; variable: string; mode: Mode; baseline: string; year: number; ref_: number;
}) {
  const hl = useHighlight();
  const unit = ix.unit.get(variable) ?? "";
  const baseSeries = series(ix, baseline, variable);
  const t = chartTheme();
  const toY = (s: string) =>
    series(ix, s, variable).map((v, k) => sig(mode === "value" ? v : pctChange(v, baseSeries[k])));
  const data: Data[] = [];

  if (isEnsemble(ix)) {
    // every pathway as a 10-90% band and a median line
    const all = ix.scenarios.map(toY);
    const q = (p: number) =>
      ix.years.map((_, k) => {
        const col = all.map((r) => r[k]).filter((v): v is number => v !== null).sort((x, y) => x - y);
        return col.length ? quantile(col, p) : null;
      });
    data.push(
      { type: "scatter", mode: "lines", x: ix.years, y: q(0.1), line: { width: 0, color: t.grid },
        hoverinfo: "skip", showlegend: false } as Data,
      { type: "scatter", mode: "lines", x: ix.years, y: q(0.9), line: { width: 0, color: t.grid },
        fill: "tonexty", fillcolor: "rgba(120,134,130,0.18)", name: "middle 80% of pathways",
        hoverinfo: "skip" } as Data,
      { type: "scatter", mode: "lines", x: ix.years, y: q(0.5), name: "median of all pathways",
        line: { color: t.muted, width: 1.5 },
        hovertemplate: `median<br>%{x}: %{y:,.3~r}<extra></extra>` } as Data,
    );
  }
  const shown = isEnsemble(ix) ? hl.list : ix.scenarios;
  for (const s of shown) {
    data.push({
      type: "scatter",
      mode: "lines+markers",
      name: s,
      x: ix.years,
      y: toY(s),
      line: { color: hl.colorOf(s), width: 2 },
      marker: { size: 6, color: hl.colorOf(s), line: { color: t.surface, width: 2 } },
      hovertemplate: `${s}<br>%{x}: %{y:,.3~r}${mode === "value" ? ` ${shortUnit(unit)}` : "%"}<extra></extra>`,
    } as Data);
  }
  return (
    <>
      <Chart
        data={data}
        yTitle={mode === "value" ? shortUnit(unit) : `% vs ${baseline}`}
        height={360}
        shapes={[{ type: "line", xref: "x", yref: "paper", x0: year, x1: year, y0: 0, y1: 1,
                   line: { color: t.muted, width: 1 } }]}
      />
      <p className="note">History to {ref_}; the vertical line marks {year}.</p>
    </>
  );
}

// ------------------------------------------------------------------ lever effects

function LeverEffects({ ix, variable, year }: { ix: IamcIndex; variable: string; year: number }) {
  const eff = useMemo(() => leverEffects(ix, variable, year), [ix, variable, year]);
  if (!eff.length) return <p className="muted">No lever settings vary in this run.</p>;
  // one shared scale; bars grow from zero so sign and size read at a glance
  const lo = Math.min(0, ...eff.flatMap((e) => e.options.map((o) => o.mean)));
  const hi = Math.max(0, ...eff.flatMap((e) => e.options.map((o) => o.mean)));
  const span = hi - lo || 1;
  const pos = (v: number) => ((v - lo) / span) * 100;
  const zero = pos(0);
  return (
    <>
      <div className="levers">
        {eff.map((e) => (
          <div className="lever" key={e.lever}>
            <h4>
              {e.lever}
              <span className="unit">settings {fmtPct(e.range, false)} apart</span>
            </h4>
            {[...e.options].reverse().map((o) => {
              const p = pos(o.mean);
              const neg = o.mean < 0;
              return (
                <div
                  className="lever-opt"
                  key={o.option}
                  title={`${e.lever} = ${o.option}: ${fmtPct(o.mean)} on average over ${o.n.toLocaleString("en-GB")} pathways`}
                >
                  <span className="lever-label">{o.option}</span>
                  <span className="lever-track">
                    <span className="bar-zero" style={{ left: `${zero}%` }} />
                    <span
                      className={`lever-bar ${neg ? "dv-neg" : "dv-pos"}`}
                      style={{ left: `${Math.min(p, zero)}%`, width: `${Math.max(Math.abs(p - zero), 0.5)}%` }}
                    />
                  </span>
                  <span className="lever-val">{fmtPct(o.mean)}</span>
                </div>
              );
            })}
          </div>
        ))}
      </div>
      <p className="note">
        Averages over pathways that differ in other settings too; read them as typical effects,
        not controlled comparisons. All bars share one scale.
      </p>
    </>
  );
}

// ------------------------------------------------------------------ composition

function Composition({ ix, scenarios, variable, parts, year }: {
  ix: IamcIndex; scenarios: string[]; variable: string; parts: string[]; year: number;
}) {
  const unit = shortUnit(ix.unit.get(variable) ?? "");
  // seven colour slots at most; fold the smallest parts into "Other"
  const totals = parts.map((p) => ({
    p,
    t: scenarios.reduce((acc, s) => acc + Math.abs(value(ix, s, p, year) ?? 0), 0),
  }));
  totals.sort((x, y) => y.t - x.t);
  const shown = totals.length > 7 ? totals.slice(0, 6).map((x) => x.p) : parts;
  const folded = totals.length > 7 ? totals.slice(6).map((x) => x.p) : [];
  const t = chartTheme();
  const scen = [...scenarios].reverse(); // first pathway on top
  const traces: Data[] = shown.map((p, i) => ({
    type: "bar",
    orientation: "h",
    name: leafName(p),
    y: scen,
    x: scen.map((s) => value(ix, s, p, year)),
    marker: { color: seriesColor(i), line: { color: t.surface, width: 2 } },
    hovertemplate: `%{y}<br>${leafName(p)}: %{x:,.3~r} ${unit}<extra></extra>`,
  }) as Data);
  if (folded.length) {
    traces.push({
      type: "bar",
      orientation: "h",
      name: "Other",
      y: scen,
      x: scen.map((s) => folded.reduce((acc, p) => acc + (value(ix, s, p, year) ?? 0), 0)),
      marker: { color: seriesColor(99), line: { color: t.surface, width: 2 } },
      hovertemplate: `%{y}<br>Other: %{x:,.3~r} ${unit}<extra></extra>`,
    } as Data);
  }
  return (
    <Chart
      data={traces}
      barmode="relative"
      horizontal
      xTitle={unit}
      height={Math.max(260, scenarios.length * 44 + 110)}
      margin={{ l: 150 }}
    />
  );
}

// ------------------------------------------------------------------ head to head

function HeadToHead({ ix, a, b, year, extra }: {
  ix: IamcIndex; a: string; b: string; year: number; extra: string[];
}) {
  const hl = useHighlight();
  const vars = [...new Set([...keyIndicators(ix).map((k) => k.variable), ...extra])];
  const rows = vars.map((v) => {
    const va = value(ix, a, v, year);
    const vb = value(ix, b, v, year);
    // a % change across a sign flip (e.g. a land sink vs a land source) means nothing
    const flips = va !== null && vb !== null && va * vb < 0;
    return { v, va, vb, p: flips ? null : pctChange(va, vb), abs: va !== null && vb !== null ? va - vb : null, flips };
  });
  const max = Math.max(5, ...rows.map((r) => Math.abs(r.p ?? 0)));
  const leverRows = ix.leverKeys.filter((k) => ix.levers.get(a)?.[k] !== ix.levers.get(b)?.[k]);
  return (
    <div className="scroll-x">
      <table className="h2h">
        <thead>
          <tr>
            <th scope="col">Indicator</th>
            <th scope="col" className="num">
              <span className="th-key"><span className="swatch" style={{ background: hl.colorOf(a) }} />{a}</span>
            </th>
            <th scope="col" className="num">
              <span className="th-key"><span className="swatch" style={{ background: hl.colorOf(b) }} />{b}</span>
            </th>
            <th scope="col" className="h2h-diff">Difference</th>
          </tr>
        </thead>
        <tbody>
          {leverRows.map((k) => (
            <tr key={`lever-${k}`} className="row-lever">
              <th scope="row">{k}<span className="unit">setting</span></th>
              <td className="num">{ix.levers.get(a)?.[k]}</td>
              <td className="num">{ix.levers.get(b)?.[k]}</td>
              <td className="h2h-diff" />
            </tr>
          ))}
          {rows.map((r) => {
            const w = r.p === null ? 0 : (Math.abs(r.p) / max) * 50;
            return (
              <tr key={r.v}>
                <th scope="row">
                  {keyIndicators(ix).find((k) => k.variable === r.v)?.label ?? r.v}
                  <span className="unit">{shortUnit(ix.unit.get(r.v) ?? "")}</span>
                </th>
                <td className="num">{fmtValue(r.va)}</td>
                <td className="num">{fmtValue(r.vb)}</td>
                <td className="h2h-diff">
                  <div className="dv">
                    <span className="dv-track">
                      <span className="dv-mid" />
                      {r.p !== null && (
                        <span
                          className={`dv-bar ${r.p < 0 ? "dv-neg" : "dv-pos"}`}
                          style={r.p < 0 ? { right: "50%", width: `${w}%` } : { left: "50%", width: `${w}%` }}
                        />
                      )}
                    </span>
                    <span className="dv-num" title={r.flips ? "Signs differ, so the absolute difference is shown" : undefined}>
                      {a === b ? "–" : r.flips ? `${r.abs! > 0 ? "+" : "−"}${fmtValue(Math.abs(r.abs!))}` : fmtPct(r.p)}
                    </span>
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="note">
        Difference is {a} relative to {b}, in %; bars share one scale. Where one value is negative
        and the other positive, the absolute difference is shown instead.
        {leverRows.length ? " The first rows list the settings that differ." : ""}
      </p>
    </div>
  );
}
