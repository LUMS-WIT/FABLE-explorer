// Which pathways get a colour. Small runs: every pathway, in workbook order.
// Large runs (ensembles): up to seven chosen pathways; the rest are drawn as a
// grey distribution. A pathway keeps its colour for as long as it stays chosen.

import { createContext, useContext } from "react";
import { IamcIndex, extremes, isEnsemble } from "./iamc";
import { MAX_SLOTS, seriesColor } from "./theme";

export interface Highlight {
  list: string[];
  set: (list: string[]) => void;
  colorOf: (scenario: string) => string;
  has: (scenario: string) => boolean;
}

export const HighlightContext = createContext<Highlight>({
  list: [],
  set: () => {},
  colorOf: () => seriesColor(99),
  has: () => false,
});

export function useHighlight(): Highlight {
  return useContext(HighlightContext);
}

export function makeHighlight(list: string[], set: (l: string[]) => void): Highlight {
  const pos = new Map(list.map((s, i) => [s, i]));
  return {
    list,
    set,
    colorOf: (s) => seriesColor(pos.has(s) ? pos.get(s)! : 99),
    has: (s) => pos.has(s),
  };
}

/** Default choice: the baseline plus the pathways at the ends of the headline indicators. */
export function defaultHighlight(ix: IamcIndex): string[] {
  if (!isEnsemble(ix)) return ix.scenarios.slice(0, MAX_SLOTS);
  const year = ix.years[ix.years.length - 1];
  const picks = [ix.baseline];
  const add = (s?: string) => {
    if (s && !picks.includes(s) && picks.length < MAX_SLOTS) picks.push(s);
  };
  const has = (v: string) => ix.unit.has(v);
  if (has("Emissions|Kyoto Gases|AFOLU")) {
    const e = extremes(ix, "Emissions|Kyoto Gases|AFOLU", year);
    add(e.low[0]);
    add(e.high[0]);
  }
  if (has("Food Availability [per capita]")) add(extremes(ix, "Food Availability [per capita]", year).high[0]);
  if (has("Land Cover|Forest")) add(extremes(ix, "Land Cover|Forest", year).high[0]);
  return picks;
}
