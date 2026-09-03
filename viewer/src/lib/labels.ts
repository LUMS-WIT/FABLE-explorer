// FABLE workbooks name columns like "TotalCO2e", "LNPPMatureForest",
// "DeforRate", "kcal_feas". Those leak straight into chart titles and legends
// and read badly. prettyLabel() turns them into human text while keeping the
// raw token available for tooltips. It is heuristic and lossless-reversible is
// NOT a goal — readability is.

// Tokens that must render a specific way (checked before camelCase splitting).
const GLOSSARY: Record<string, string> = {
  co2e: "CO₂e",
  co2: "CO₂",
  n2o: "N₂O",
  ch4: "CH₄",
  ghg: "GHG",
  gwp: "GWP",
  soc: "SOC",
  npk: "NPK",
  pou: "Prevalence of Undernourishment",
  mder: "Minimum Dietary Energy Requirement",
  kcal: "kcal",
  lnpp: "Land-Not-Primarily-Productive",
  bii: "Biodiversity Intactness Index",
  ndc: "NDC",
  ssp: "SSP",
  fao: "FAO",
  gdp: "GDP",
  ha: "ha",
  defor: "Deforestation",
  affor: "Afforestation",
  agroeco: "Agro-ecological",
  ag: "Agricultural",
  live: "Livestock",
  hist: "Historical",
  calc: "Calculated",
  feas: "Feasible",
  targ: "Target",
  proj: "Projected",
  sh: "Share",
  dens: "Density",
  rum: "Ruminant",
  prod: "Production",
  emis: "Emissions",
  seq: "Sequestration",
  reg: "Regrowth",
  biofuel: "Biofuel",
  cropland: "Cropland",
  scen: "Scenario",
  conso: "Consumption",
  hum: "Human",
  biodiv: "Biodiversity",
  nutrient: "Nutrient",
  totalresults: "Total Results",
  results: "Results",
};

// Multi-word replacements applied to the already-spaced string.
const PHRASES: [RegExp, string][] = [
  [/\bMature Other L\b/gi, "Mature Other Land"],
  [/\bNew Forest\b/gi, "New Forest"],
  [/\bMax Pct Diff Vs Baseline\b/gi, "Max % Diff vs Baseline"],
  [/\bMax Abs Diff Vs Baseline\b/gi, "Max Abs Diff vs Baseline"],
  [/\bDiff Vs Baseline\b/gi, "Diff vs Baseline"],
  [/\bPct\b/gi, "%"],
  [/\bVs\b/gi, "vs"],
];

function splitToken(token: string): string[] {
  // camelCase / PascalCase / digit boundaries
  return token
    .replace(/([a-z0-9])([A-Z])/g, "$1 $2")
    .replace(/([A-Za-z])([0-9])/g, "$1 $2")
    .replace(/([0-9])([A-Za-z])/g, "$1 $2")
    .split(/\s+/)
    .filter(Boolean);
}

function humanizeWord(w: string): string {
  const key = w.toLowerCase();
  if (GLOSSARY[key]) return GLOSSARY[key];
  if (w.length <= 3 && w === w.toUpperCase()) return w; // keep acronyms
  return w.charAt(0).toUpperCase() + w.slice(1).toLowerCase();
}

const cache = new Map<string, string>();

export function prettyLabel(raw: string | null | undefined): string {
  if (raw == null || raw === "") return "";
  const hit = cache.get(raw);
  if (hit !== undefined) return hit;

  let out = raw
    .split(/[_\s]+/)
    .flatMap(splitToken)
    .map(humanizeWord)
    .join(" ")
    .replace(/\s+/g, " ")
    .trim();

  for (const [re, sub] of PHRASES) out = out.replace(re, sub);
  cache.set(raw, out);
  return out;
}

// "GHG__ResultsGHG" -> "GHG · Results"
export function prettyTableKey(key: string): string {
  const [sheet, table] = key.split("__");
  const left = prettyLabel(sheet ?? key);
  let right = prettyLabel((table ?? "").replace(/^Results?/i, "Results "));
  right = right.replace(/^Results\s+/i, "").trim();
  return right && right.toLowerCase() !== left.toLowerCase()
    ? `${left} · ${right}`
    : left;
}
