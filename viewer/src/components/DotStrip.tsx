// "Where pathways land": one row per indicator, placed by % change against the
// baseline in the chosen year. All rows share one axis, so a long move on one
// indicator reads as long next to the others. Large runs add a grey density of
// every pathway, its middle-80% range and median; chosen pathways are dots.

import { useMemo, useState } from "react";
import {
  IamcIndex,
  KeyIndicator,
  fmtPct,
  fmtValue,
  isEnsemble,
  pctChange,
  quantile,
  value,
} from "../lib/iamc";
import { useHighlight } from "../lib/highlight";

const BINS = 64;

function niceMax(m: number): number {
  const steps = [5, 10, 20, 25, 50, 75, 100, 150, 200, 300, 500, 1000];
  return steps.find((s) => s >= m) ?? Math.ceil(m / 1000) * 1000;
}

/** Shared axis limit. One runaway row (e.g. +280%) would flatten every other
 *  row, so when the largest row is far beyond the rest, the axis follows the
 *  rest and the runaway values are pinned to the edge with their value shown. */
function axisLimit(rowMax: number[]): number {
  const s = [...rowMax].sort((a, b) => b - a);
  if (s.length >= 3 && s[0] > 1.8 * s[1]) return niceMax(Math.max(s[1] * 1.1, 1));
  return niceMax(Math.max(s[0] ?? 1, 1));
}

interface Dot {
  scenario: string;
  p: number;
  v: number | null;
  lane: number;
}

interface Row {
  k: KeyIndicator;
  b: number | null;
  dots: Dot[];
  all: number[]; // every pathway's % change, sorted
}

export default function DotStrip({
  ix,
  rows,
  year,
  focus,
  onFocus,
}: {
  ix: IamcIndex;
  rows: KeyIndicator[];
  year: number;
  focus: string | null;
  onFocus: (s: string | null) => void;
}) {
  const hl = useHighlight();
  const ensemble = isEnsemble(ix);
  const [tip, setTip] = useState<{ row: string; dot: Dot } | null>(null);

  const data = useMemo(() => {
    const out: Row[] = rows.map((k) => {
      const b = value(ix, ix.baseline, k.variable, year);
      const all: number[] = [];
      const dots: Dot[] = [];
      for (const s of ix.scenarios) {
        const v = value(ix, s, k.variable, year);
        const p = pctChange(v, b);
        if (p === null) continue;
        all.push(p);
        if (hl.has(s)) dots.push({ scenario: s, p, v, lane: 0 });
      }
      all.sort((x, y) => x - y);
      return { k, b, dots, all };
    });
    // in an ensemble, scale to the 1st-99th percentile so a few extreme runs don't set the axis
    const rowMax = out.map((r) =>
      ensemble && r.all.length > 20
        ? Math.max(Math.abs(quantile(r.all, 0.01)), Math.abs(quantile(r.all, 0.99)), ...r.dots.map((d) => Math.abs(d.p)))
        : Math.max(0, ...r.all.map(Math.abs)),
    );
    const max = axisLimit(rowMax);
    const clamp = (p: number) => Math.max(-max, Math.min(max, p));
    for (const r of out) {
      const sorted = [...r.dots].sort((a, b) => clamp(a.p) - clamp(b.p));
      const minGap = 2 * max * 0.022;
      let run: Dot[] = [];
      const flush = () => {
        run.forEach((d, i) => (d.lane = run.length === 1 ? 0 : i - (run.length - 1) / 2));
        run = [];
      };
      for (const d of sorted) {
        if (run.length && clamp(d.p) - clamp(run[run.length - 1].p) > minGap) flush();
        run.push(d);
      }
      flush();
    }
    return { rows: out, max };
  }, [ix, rows, year, hl, ensemble]);

  const x = (p: number) => 50 + (Math.max(-data.max, Math.min(data.max, p)) / data.max) * 50;
  const over = (p: number) => Math.abs(p) > data.max;
  const ticks = [-data.max, -data.max / 2, 0, data.max / 2, data.max];

  return (
    <div className="strip" onMouseLeave={() => setTip(null)}>
      <div className="strip-legend" role="group" aria-label="Highlight a pathway">
        {hl.list.map((s) => (
          <button
            key={s}
            className={`key ${focus === s ? "key-on" : ""} ${focus && focus !== s ? "key-dim" : ""}`}
            onMouseEnter={() => onFocus(s)}
            onMouseLeave={() => onFocus(null)}
            onFocus={() => onFocus(s)}
            onBlur={() => onFocus(null)}
          >
            <span className="swatch" style={{ background: hl.colorOf(s) }} />
            {s}
            {s === ix.baseline && <span className="key-note">baseline</span>}
          </button>
        ))}
        {ensemble && (
          <span className="key key-static">
            <span className="density-key" aria-hidden />
            all {ix.scenarios.length.toLocaleString("en-GB")} pathways
            <span className="range-key" aria-hidden />
            middle 80%
          </span>
        )}
      </div>

      <div className="strip-grid">
        <div className="strip-axis" aria-hidden>
          <span />
          <div className="strip-ticks">
            {ticks.map((t, i) => (
              <span key={t} className={i === 1 || i === 3 ? "tick-mid" : ""} style={{ left: `${x(t)}%` }}>
                {t === 0 ? "0%" : fmtPct(t)}
              </span>
            ))}
          </div>
        </div>

        {data.rows.map(({ k, b, dots, all }) => {
          const p10 = all.length ? quantile(all, 0.1) : null;
          const p90 = all.length ? quantile(all, 0.9) : null;
          const med = all.length ? quantile(all, 0.5) : null;
          let bins: number[] = [];
          if (ensemble) {
            bins = new Array(BINS).fill(0);
            for (const p of all) bins[Math.min(BINS - 1, Math.floor((x(p) / 100) * BINS))] += 1;
          }
          const peak = Math.max(1, ...bins);
          const outside = (ensemble ? all : dots.map((d) => d.p)).filter(over);
          return (
            <div className="strip-row" key={k.variable}>
              <div className="strip-label">
                <span className="strip-name">{k.label}</span>
                <span className="strip-base">
                  {ix.baseline}: {fmtValue(b, ix.unit.get(k.variable))}
                </span>
              </div>
              <div className="strip-track">
                {ensemble && (
                  <svg className="density" viewBox={`0 0 ${BINS} 10`} preserveAspectRatio="none" aria-hidden>
                    {bins.map((c, i) =>
                      c ? <rect key={i} x={i + 0.08} width={0.84} y={10 - (10 * c) / peak} height={(10 * c) / peak} /> : null,
                    )}
                  </svg>
                )}
                <span className="strip-zero" style={{ left: "50%" }} />
                {ensemble && p10 !== null && p90 !== null ? (
                  <>
                    <span className="strip-range" style={{ left: `${x(p10)}%`, width: `${x(p90) - x(p10)}%` }} />
                    {med !== null && <span className="strip-median" style={{ left: `${x(med)}%` }} title={`median ${fmtPct(med)}`} />}
                  </>
                ) : (
                  dots.length > 0 && (
                    <span
                      className="strip-range"
                      style={{
                        left: `${x(Math.min(...dots.map((d) => d.p)))}%`,
                        width: `${x(Math.max(...dots.map((d) => d.p))) - x(Math.min(...dots.map((d) => d.p)))}%`,
                      }}
                    />
                  )
                )}
                {dots.map((d) => {
                  const dim = focus !== null && focus !== d.scenario;
                  return (
                    <button
                      key={d.scenario}
                      className={`dot ${over(d.p) ? "dot-over" : ""} ${dim ? "dot-dim" : ""} ${focus === d.scenario ? "dot-on" : ""}`}
                      style={{ left: `${x(d.p)}%`, top: `calc(50% + ${d.lane * 9}px)`, background: hl.colorOf(d.scenario) }}
                      aria-label={`${d.scenario}: ${fmtValue(d.v, ix.unit.get(k.variable))}, ${fmtPct(d.p)} against ${ix.baseline}`}
                      onMouseEnter={() => {
                        setTip({ row: k.variable, dot: d });
                        onFocus(d.scenario);
                      }}
                      onMouseLeave={() => {
                        setTip(null);
                        onFocus(null);
                      }}
                      onFocus={() => setTip({ row: k.variable, dot: d })}
                      onBlur={() => setTip(null)}
                    />
                  );
                })}
                {outside.length > 0 && (() => {
                  const right = outside.some((p) => p > 0);
                  const lo = Math.min(...outside);
                  const hi = Math.max(...outside);
                  const label = ensemble
                    ? `${outside.length.toLocaleString("en-GB")} beyond, up to ${fmtPct(right ? hi : lo)}`
                    : outside.length > 1 ? `${fmtPct(lo)} to ${fmtPct(hi)}` : fmtPct(outside[0]);
                  return (
                    <span className={`strip-over ${right ? "over-right" : "over-left"}`}>
                      {right ? `${label} ▸` : `◂ ${label}`}
                    </span>
                  );
                })()}
                {tip && tip.row === k.variable && (
                  <div className="tip" style={{ left: `${x(tip.dot.p)}%` }} role="tooltip">
                    <span className="tip-head">
                      <span className="swatch" style={{ background: hl.colorOf(tip.dot.scenario) }} />
                      {tip.dot.scenario}
                    </span>
                    <span className="tip-val">{fmtValue(tip.dot.v, ix.unit.get(k.variable))}</span>
                    <span className="tip-sub">
                      {tip.dot.scenario === ix.baseline ? "baseline" : `${fmtPct(tip.dot.p)} against ${ix.baseline}`}
                    </span>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
