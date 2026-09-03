// Load + structurally validate a bundle, from the bundled data file or from a
// file the user drops in. Validation is deliberately shallow: enough to refuse
// garbage and an unsupported schema major, not a full JSON-schema check.

import { Bundle, SUPPORTED_MAJOR, major } from "./types";

export class BundleError extends Error {}

const REQUIRED_KEYS: (keyof Bundle)[] = [
  "schema_version",
  "generator",
  "source",
  "pathways",
  "baseline_pathway",
  "tables",
  "deviation_summary",
  "run_quality",
];

export function validateBundle(raw: unknown): Bundle {
  if (typeof raw !== "object" || raw === null) {
    throw new BundleError("bundle is not a JSON object");
  }
  const b = raw as Record<string, unknown>;
  for (const k of REQUIRED_KEYS) {
    if (!(k in b)) throw new BundleError(`bundle is missing "${k}"`);
  }
  if (typeof b.schema_version !== "string") {
    throw new BundleError("schema_version must be a string");
  }
  const m = major(b.schema_version);
  if (Number.isNaN(m)) {
    throw new BundleError(`unparseable schema_version "${b.schema_version}"`);
  }
  if (m !== SUPPORTED_MAJOR) {
    throw new BundleError(
      `bundle schema v${b.schema_version} is not supported by this viewer ` +
        `(needs major v${SUPPORTED_MAJOR}). Rebuild the viewer or regenerate the bundle.`,
    );
  }
  if (!Array.isArray(b.pathways) || b.pathways.length === 0) {
    throw new BundleError("bundle has no pathways");
  }
  if (!Array.isArray(b.tables)) {
    throw new BundleError("bundle.tables is not an array");
  }
  return b as unknown as Bundle;
}

export async function loadBundleFromUrl(url: string): Promise<Bundle> {
  let res: Response;
  try {
    res = await fetch(url, { cache: "no-cache" });
  } catch (e) {
    throw new BundleError(`could not fetch ${url}: ${(e as Error).message}`);
  }
  if (!res.ok) {
    throw new BundleError(`fetch ${url} returned HTTP ${res.status}`);
  }
  let json: unknown;
  try {
    json = await res.json();
  } catch (e) {
    throw new BundleError(`${url} is not valid JSON: ${(e as Error).message}`);
  }
  return validateBundle(json);
}

export async function loadBundleFromFile(file: File): Promise<Bundle> {
  const text = await file.text();
  let json: unknown;
  try {
    json = JSON.parse(text);
  } catch (e) {
    throw new BundleError(`${file.name} is not valid JSON: ${(e as Error).message}`);
  }
  return validateBundle(json);
}

export function defaultBundleUrl(): string {
  // import.meta.env.BASE_URL already ends with "/"
  return `${import.meta.env.BASE_URL}data/bundle.json`;
}
