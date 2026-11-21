// Read-side helpers over the IAMC block of a bundle: lookups, variable
// hierarchy, key indicators and rule-based summary sentences. Everything here
// is computed from the numbers in the bundle; nothing is country-specific.

import { Bundle, IamcSection } from "../bundle/types";
import { num } from "./table";

const ID_COLS = ["Model", "Scenario", "Region", "Variable", "Unit"];

export interface KeyIndicator {
  variable: string;
  label: string;
  /** used only for wording ("cuts" / "raises"); never for colour */
  short: string;
}

// Headline indicators, in display order. Any that a bundle lacks are skipped.
export const KEY_INDICATORS: KeyIndicator[] = [
  { variable: "Emissions|Kyoto Gases|AFOLU", label: "AFOLU emissions", short: "emissions" },
  { variable: "Land Cover|Forest", label: "Forest area", short: "forest area" },
  { variable: "Land Cover|Cropland", label: "Cropland", short: "cropland" },
  { variable: "Land Cover|Pasture", label: "Pasture", short: "pasture" },
  { variable: "Agricultural Production", label: "Agricultural production", short: "production" },
  { variable: "Food Availability [per capita]", label: "Food availability", short: "food availability" },
  { variable: "Water Consumption|Irrigation", label: "Irrigation water", short: "irrigation water" },
  { variable: "Fertilizer Use|Nitrogen", label: "Nitrogen fertiliser", short: "nitrogen use" },
  { variable: "Labor Force|Employed|Agriculture", label: "Farm employment", short: "farm employment" },
];

export interface IamcIndex {
  section: IamcSection;
  scenarios: string[];
  years: number[];
  variables: string[];
  unit: Map<string, string>;
  /** value lookup: scenario -> variable -> year-index -> value */
  values: Map<string, Map<string, (number | null)[]>>;
  baseline: string;
  /** scenario -> lever settings, when the run came from a pathway design */
  levers: Map<string, Record<string, string>>;
  leverKeys: string[];
}

/** Runs with more pathways than colour slots are shown as an ensemble. */
export const ENSEMBLE_THRESHOLD = 7;
export function isEnsemble(ix: IamcIndex): boolean {
  return ix.scenarios.length > ENSEMBLE_THRESHOLD;
}

export function indexIamc(bundle: Bundle): IamcIndex | null {
  const s = bundle.iamc;
  if (!s || s.data.rows.length === 0) return null;
  const cols = s.data.columns;
  const ci = (c: string) => cols.indexOf(c);
  const yearCols = cols.filter((c) => !ID_COLS.includes(c) && num(c) !== null);
  const years = yearCols.map(Number);
  const yIdx = yearCols.map(ci);
  const [iS, iV, iU] = [ci("Scenario"), ci("Variable"), ci("Unit")];

  const values = new Map<string, Map<string, (number | null)[]>>();
  const unit = new Map<string, string>();
  const seenScen: string[] = [];
  const vars = new Set<string>();
  for (const r of s.data.rows) {
    const sc = String(r[iS]);
    const v = String(r[iV]);
    if (!values.has(sc)) {
      values.set(sc, new Map());
      seenScen.push(sc);
    }
    values.get(sc)!.set(v, yIdx.map((i) => num(r[i])));
    unit.set(v, String(r[iU]));
    vars.add(v);
  }
  // keep the workbook's pathway order
  const byPathway = new Map(s.scenarios.map((x) => [x.pathway, x.scenario]));
  const ordered: string[] = [];
  for (const p of bundle.pathways) {
    const sc = byPathway.get(p);
    if (sc && values.has(sc) && !ordered.includes(sc)) ordered.push(sc);
  }
  for (const sc of seenScen) if (!ordered.includes(sc)) ordered.push(sc);

  const baseline = byPathway.get(bundle.baseline_pathway) ?? ordered[0];
  const levers = new Map<string, Record<string, string>>();
  for (const x of s.scenarios) if (x.levers) levers.set(x.scenario, x.levers);
  // levers that actually vary across the run
  const leverKeys = [...new Set([...levers.values()].flatMap((l) => Object.keys(l)))].filter(
    (k) => new Set([...levers.values()].map((l) => l[k])).size > 1,
  );
  return {
    levers,
    leverKeys,
    section: s,
    scenarios: ordered,
    years,
    variables: [...vars].sort((a, b) => a.localeCompare(b)),
    unit,
    values,
    baseline,
  };
}

export function value(ix: IamcIndex, scenario: string, variable: string, year: number): number | null {
  const yi = ix.years.indexOf(year);
  if (yi < 0) return null;
  return ix.values.get(scenario)?.get(variable)?.[yi] ?? null;
}

export function series(ix: IamcIndex, scenario: string, variable: string): (number | null)[] {
  return ix.values.get(scenario)?.get(variable) ?? ix.years.map(() => null);
}

export function pctChange(v: number | null, base: number | null): number | null {
  if (v === null || base === null || base === 0) return null;
  return ((v - base) / Math.abs(base)) * 100;
}

/** Direct children of a variable present in the data, e.g. Land Cover -> Land Cover|Forest. */
export function children(ix: IamcIndex, variable: string): string[] {
  const stem = variable.replace(/ \[[^\]]*\]$/, "");
  const suffix = variable.match(/ \[[^\]]*\]$/)?.[0] ?? "";
  const depth = stem.split("|").length + 1;
  return ix.variables.filter((v) => {
    const vs = v.replace(/ \[[^\]]*\]$/, "");
    const vsuf = v.match(/ \[[^\]]*\]$/)?.[0] ?? "";
    return vsuf === suffix && vs.startsWith(stem + "|") && vs.split("|").length === depth;
  });
}

export function leafName(variable: string): string {
  const stem = variable.replace(/ \[[^\]]*\]$/, "");
  return stem.split("|").pop() ?? stem;
}

export function family(variable: string): string {
  return variable.split("|")[0].replace(/ \[.*\]$/, "");
}

export function keyIndicators(ix: IamcIndex): KeyIndicator[] {
  return KEY_INDICATORS.filter((k) => ix.unit.has(k.variable));
}

export function labelFor(variable: string): string {
  return KEY_INDICATORS.find((k) => k.variable === variable)?.label ?? variable;
}

/**
 * First year in which any pathway departs from the baseline on a key
 * indicator: the start of the projection. Earlier years are shared history.
 */
export function divergenceYear(ix: IamcIndex): number {
  const keys = keyIndicators(ix);
  for (const y of ix.years) {
    for (const k of keys) {
      const b = value(ix, ix.baseline, k.variable, y);
      for (const sc of ix.scenarios) {
        const p = pctChange(value(ix, sc, k.variable, y), b);
        if (p !== null && Math.abs(p) > 0.5) return y;
      }
    }
  }
  return ix.years[ix.years.length - 1];
}

/** Last shared year before pathways diverge (the reference point for trends). */
export function referenceYear(ix: IamcIndex): number {
  const d = divergenceYear(ix);
  const prior = ix.years.filter((y) => y < d);
  return prior.length ? prior[prior.length - 1] : ix.years[0];
}

// ---------------------------------------------------------------- formatting

export function fmtValue(v: number | null, unit = ""): string {
  if (v === null || !Number.isFinite(v)) return "–";
  const a = Math.abs(v);
  const digits = a >= 1000 ? 0 : a >= 100 ? 0 : a >= 10 ? 1 : a >= 1 ? 2 : 3;
  const s = v.toLocaleString("en-GB", { maximumFractionDigits: digits, minimumFractionDigits: 0 });
  return unit ? `${s} ${shortUnit(unit)}` : s;
}

export function fmtPct(p: number | null, signed = true): string {
  if (p === null || !Number.isFinite(p)) return "–";
  const r = Math.abs(p) >= 10 ? Math.round(p) : Math.round(p * 10) / 10;
  const s = `${Math.abs(r).toLocaleString("en-GB")}%`;
  if (!signed || r === 0) return r === 0 ? "0%" : s;
  return r > 0 ? `+${s}` : `−${s}`;
}

/** Units as people say them: drop the "/yr" clutter on stocks only where IAMC has none. */
export function shortUnit(u: string): string {
  return u
    .replace("million t DM/yr", "Mt DM/yr")
    .replace("Mt CO2-equiv/yr", "Mt CO₂e/yr")
    .replace("Mt CO2/yr", "Mt CO₂/yr")
    .replace("Mt CH4/yr", "Mt CH₄/yr")
    .replace("kt N2O/yr", "kt N₂O/yr")
    .replace("million full-time equivalent workers", "million FTE")
    .replace("million ha", "Mha");
}

// ------------------------------------------------------------------ ensemble

export function quantile(sorted: number[], q: number): number {
  if (!sorted.length) return NaN;
  const pos = (sorted.length - 1) * q;
  const lo = Math.floor(pos);
  const hi = Math.ceil(pos);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (pos - lo);
}

export interface Spread {
  n: number;
  min: number;
  p10: number;
  median: number;
  p90: number;
  max: number;
}

export function spread(values: (number | null)[]): Spread | null {
  const v = values.filter((x): x is number => x !== null && Number.isFinite(x)).sort((a, b) => a - b);
  if (!v.length) return null;
  return {
    n: v.length,
    min: v[0],
    p10: quantile(v, 0.1),
    median: quantile(v, 0.5),
    p90: quantile(v, 0.9),
    max: v[v.length - 1],
  };
}

/** % change against the baseline for every scenario. */
export function changes(ix: IamcIndex, variable: string, year: number, base = ix.baseline): Map<string, number | null> {
  const b = value(ix, base, variable, year);
  return new Map(ix.scenarios.map((s) => [s, pctChange(value(ix, s, variable, year), b)]));
}

export interface LeverEffect {
  lever: string;
  options: { option: string; mean: number; n: number }[];
  range: number;
}

/**
 * Main effect of each lever: the average % change against the baseline over
 * all pathways with each setting. With a balanced sample this isolates the
 * lever's typical effect; it is an average, not a controlled experiment.
 */
export function leverEffects(ix: IamcIndex, variable: string, year: number): LeverEffect[] {
  const ch = changes(ix, variable, year);
  const out: LeverEffect[] = [];
  for (const k of ix.leverKeys) {
    const acc = new Map<string, { sum: number; n: number }>();
    for (const [s, p] of ch) {
      const opt = ix.levers.get(s)?.[k];
      if (opt === undefined || p === null) continue;
      const a = acc.get(opt) ?? { sum: 0, n: 0 };
      a.sum += p;
      a.n += 1;
      acc.set(opt, a);
    }
    const options = [...acc.entries()]
      .filter(([, a]) => a.n > 0)
      .map(([option, a]) => ({ option, mean: a.sum / a.n, n: a.n }))
      .sort((x, y) => x.mean - y.mean);
    if (options.length < 2) continue;
    out.push({ lever: k, options, range: options[options.length - 1].mean - options[0].mean });
  }
  return out.sort((a, b) => b.range - a.range);
}

/** Pathways with the lowest / highest value of a variable. */
export function extremes(ix: IamcIndex, variable: string, year: number, k = 1): { low: string[]; high: string[] } {
  const r = ix.scenarios
    .map((s) => ({ s, v: value(ix, s, variable, year) }))
    .filter((x) => x.v !== null)
    .sort((a, b) => a.v! - b.v!);
  return { low: r.slice(0, k).map((x) => x.s), high: r.slice(-k).reverse().map((x) => x.s) };
}

// ------------------------------------------------------------------ findings

export interface Insight {
  text: string;
  /** scenario the sentence is about, for a colour key beside it */
  scenario?: string;
}

function phrase(p: number | null): string {
  if (p === null) return "";
  const r = Math.abs(p) >= 10 ? Math.round(p) : Math.round(p * 10) / 10;
  if (r === 0) return "about the same as";
  return `${Math.abs(r).toLocaleString("en-GB")}% ${r > 0 ? "higher than" : "lower than"}`;
}

/**
 * A handful of plain sentences describing the spread of pathways at `year`
 * against the baseline. Rule-based: every number is read from the table.
 */
export function insights(ix: IamcIndex, year: number): Insight[] {
  const out: Insight[] = [];
  if (isEnsemble(ix)) out.push(...ensembleFindings(ix, year));
  const base = ix.baseline;
  const others = ix.scenarios.filter((s) => s !== base);
  const ref = referenceYear(ix);
  const keys = keyIndicators(ix);
  const has = (v: string) => ix.unit.has(v);
  const E = "Emissions|Kyoto Gases|AFOLU";
  const F = "Food Availability [per capita]";
  const FO = "Land Cover|Forest";

  // 1. Where the baseline is heading.
  const trend = keys.filter((k) => [E, FO, F].includes(k.variable));
  const parts = trend
    .map((k) => {
      const a = value(ix, base, k.variable, ref);
      const b = value(ix, base, k.variable, year);
      const p = pctChange(b, a);
      if (p === null) return null;
      const dir = Math.abs(p) < 0.5 ? "flat" : p > 0 ? `up ${fmtPct(p, false)}` : `down ${fmtPct(p, false)}`;
      return `${k.label.toLowerCase().replace("afolu", "AFOLU")} ${dir} (${fmtValue(a)} to ${fmtValue(b, ix.unit.get(k.variable))})`;
    })
    .filter(Boolean);
  if (parts.length && year > ref) {
    out.push({
      scenario: base,
      text: `Under ${base}, from ${ref} to ${year}: ${listJoin(parts as string[])}.`,
    });
  }

  // 2. Lowest-emission pathway and what comes with it.
  if (has(E) && others.length) {
    const ranked = [...ix.scenarios]
      .map((s) => ({ s, v: value(ix, s, E, year) }))
      .filter((x) => x.v !== null)
      .sort((a, b) => a.v! - b.v!);
    const low = ranked[0];
    if (low && low.s !== base) {
      const bE = value(ix, base, E, year);
      const side = [F, FO, "Agricultural Production"]
        .filter(has)
        .map((v) => {
          const p = pctChange(value(ix, low.s, v, year), value(ix, base, v, year));
          return p === null || Math.abs(p) < 1 ? null : `${labelFor(v).toLowerCase()} ${fmtPct(p)}`;
        })
        .filter(Boolean) as string[];
      out.push({
        scenario: low.s,
        text:
          `${low.s} has the lowest AFOLU emissions in ${year}: ${fmtValue(low.v, ix.unit.get(E))}, ` +
          `${phrase(pctChange(low.v, bE))} ${base}.` +
          (side.length ? ` Against ${base}, it also has ${listJoin(side)}.` : ""),
      });
    }
  }

  // 3. Food availability extremes.
  if (has(F) && others.length) {
    const vals = ix.scenarios.map((s) => ({ s, v: value(ix, s, F, year) })).filter((x) => x.v !== null);
    const lo = vals.reduce((m, x) => (x.v! < m.v! ? x : m), vals[0]);
    const hi = vals.reduce((m, x) => (x.v! > m.v! ? x : m), vals[0]);
    if (lo && hi && hi.v! - lo.v! > 1) {
      out.push({
        scenario: lo.s,
        text:
          `Food availability in ${year} ranges from ${fmtValue(lo.v, "")} kcal per person per day ` +
          `(${lo.s}) to ${fmtValue(hi.v, "")} (${hi.s}).`,
      });
    }
  }

  // 4. Forest: which pathways keep it, which lose it.
  if (has(FO) && others.length) {
    const r = ix.scenarios
      .map((s) => ({ s, p: pctChange(value(ix, s, FO, year), value(ix, s, FO, ref)) }))
      .filter((x) => x.p !== null);
    const kept = r.filter((x) => Math.abs(x.p!) < 2).map((x) => x.s);
    const lost = r.filter((x) => x.p! <= -2).sort((a, b) => a.p! - b.p!);
    if (lost.length) {
      out.push({
        scenario: lost[0].s,
        text:
          `Forest area shrinks most under ${lost[0].s} (${fmtPct(lost[0].p)} from ${ref})` +
          (kept.length ? `; it holds steady under ${namesOrCount(kept)}.` : "."),
      });
    }
  }

  // 5. Where pathways disagree most.
  const spreads = keys
    .map((k) => {
      const b = value(ix, base, k.variable, year);
      const ps = ix.scenarios.map((s) => pctChange(value(ix, s, k.variable, year), b)).filter((p): p is number => p !== null);
      if (!ps.length) return null;
      return { k, lo: Math.min(...ps), hi: Math.max(...ps) };
    })
    .filter((x): x is { k: KeyIndicator; lo: number; hi: number } => x !== null)
    .sort((a, b) => b.hi - b.lo - (a.hi - a.lo));
  if (spreads.length && spreads[0].hi - spreads[0].lo > 5) {
    const s = spreads[0];
    out.push({
      text:
        `Pathways differ most on ${s.k.short}: from ${fmtPct(s.lo)} to ${fmtPct(s.hi)} ` +
        `against ${base} in ${year}.`,
    });
  }
  return out;
}

function ensembleFindings(ix: IamcIndex, year: number): Insight[] {
  const out: Insight[] = [];
  const base = ix.baseline;
  const n = ix.scenarios.length - 1;
  const E = "Emissions|Kyoto Gases|AFOLU";
  const F = "Food Availability [per capita]";
  if (ix.unit.has(E)) {
    const ch = [...changes(ix, E, year).entries()].filter(([s, p]) => s !== base && p !== null).map(([, p]) => p!);
    const below = ch.filter((p) => p < -0.5).length;
    const sp = spread(ch);
    if (sp) {
      out.push({
        text:
          `${below.toLocaleString("en-GB")} of ${n.toLocaleString("en-GB")} pathways ` +
          `(${Math.round((100 * below) / Math.max(n, 1))}%) have lower AFOLU emissions than ${base} in ${year}. ` +
          `The middle 80% range from ${fmtPct(sp.p10)} to ${fmtPct(sp.p90)}.`,
      });
    }
    if (ix.unit.has(F)) {
      const both = ix.scenarios.filter((s) => {
        const pe = pctChange(value(ix, s, E, year), value(ix, base, E, year));
        const pf = pctChange(value(ix, s, F, year), value(ix, base, F, year));
        return s !== base && pe !== null && pf !== null && pe <= -20 && pf >= -1;
      }).length;
      out.push({
        text:
          `${both.toLocaleString("en-GB")} pathways cut AFOLU emissions by at least 20% ` +
          `while keeping food availability within 1% of ${base} or higher.`,
      });
    }
    const eff = leverEffects(ix, E, year);
    if (eff.length) {
      const top = eff[0];
      const lo = top.options[0];
      const hi = top.options[top.options.length - 1];
      out.push({
        text:
          `${top.lever} is the setting that moves AFOLU emissions most: pathways with ${lo.option} ` +
          `average ${fmtPct(lo.mean)} against ${base}, those with ${hi.option} ${fmtPct(hi.mean)}.`,
      });
    }
  }
  return out;
}

function namesOrCount(names: string[]): string {
  return names.length <= 4 ? listJoin(names) : `${names.length.toLocaleString("en-GB")} pathways`;
}

function listJoin(items: string[]): string {
  if (items.length <= 1) return items.join("");
  return `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;
}
