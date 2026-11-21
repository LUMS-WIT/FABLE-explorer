import { useCallback, useEffect, useMemo, useState } from "react";
import { Bundle } from "./bundle/types";
import {
  BundleError,
  defaultBundleUrl,
  loadBundleFromFile,
  loadBundleFromUrl,
} from "./bundle/load";
import { indexIamc } from "./lib/iamc";
import { HighlightContext, defaultHighlight, makeHighlight } from "./lib/highlight";
import QualityBanner from "./components/QualityBanner";
import Overview from "./components/Overview";
import TableExplorer from "./components/TableExplorer";
import DeviationAnalysis from "./components/DeviationAnalysis";
import IamcExport from "./components/IamcExport";
import Guide from "./components/Guide";
import Summary from "./components/Summary";
import Compare from "./components/Compare";

type Tab = "summary" | "compare" | "iamc" | "explore" | "deviation" | "overview" | "guide";
const TABS: { id: Tab; label: string; needsBundle: boolean }[] = [
  { id: "summary", label: "Summary", needsBundle: true },
  { id: "compare", label: "Compare pathways", needsBundle: true },
  { id: "iamc", label: "IAMC data", needsBundle: true },
  { id: "explore", label: "Workbook tables", needsBundle: true },
  { id: "deviation", label: "Deviation ranking", needsBundle: true },
  { id: "overview", label: "Run details", needsBundle: true },
  { id: "guide", label: "Guide", needsBundle: false },
];

function builtOn(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime())
    ? iso
    : d.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

export default function App() {
  const [bundle, setBundle] = useState<Bundle | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<Tab>("summary");
  const [dragging, setDragging] = useState(false);
  const ix = useMemo(() => (bundle ? indexIamc(bundle) : null), [bundle]);
  const [picked, setPicked] = useState<string[]>([]);
  useEffect(() => setPicked(ix ? defaultHighlight(ix) : []), [ix]);
  const highlight = useMemo(() => makeHighlight(picked, setPicked), [picked]);

  const show = useCallback((b: Bundle) => {
    setBundle(b);
    setError(null);
    setTab(b.iamc && b.iamc.data.rows.length ? "summary" : "overview");
  }, []);

  useEffect(() => {
    loadBundleFromUrl(defaultBundleUrl())
      .then(show)
      .catch((e) => setError(e instanceof BundleError ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, [show]);

  const openFile = useCallback(async (file: File) => {
    setLoading(true);
    try {
      show(await loadBundleFromFile(file));
    } catch (e) {
      setError(e instanceof BundleError ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [show]);

  const tabs = TABS.filter((t) => bundle || !t.needsBundle);

  return (
    <HighlightContext.Provider value={highlight}>
    <div
      className={`app ${dragging ? "dragging" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={(e) => {
        if (e.currentTarget === e.target) setDragging(false);
      }}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        const f = e.dataTransfer.files[0];
        if (f) void openFile(f);
      }}
    >
      <header className="topbar">
        <div className="brand">
          <span className="mark" aria-hidden>
            <span /><span /><span />
          </span>
          <span className="wordmark">FABLE Explorer</span>
          {bundle && (
            <span className="run-line">
              {bundle.source.country}, {bundle.pathways.length.toLocaleString("en-GB")} pathways, built {builtOn(bundle.source.generated_at)}
            </span>
          )}
        </div>
        <label className="file-btn">
          Open bundle
          <input
            type="file"
            accept="application/json,.json"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void openFile(f);
              e.target.value = "";
            }}
          />
        </label>
      </header>

      {(bundle || (!loading && error)) && (
        <nav className="tabs" aria-label="Views">
          {tabs.map((t) => (
            <button
              key={t.id}
              className={tab === t.id ? "tab-on" : ""}
              aria-current={tab === t.id ? "page" : undefined}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>
      )}

      <main className="content">
        {loading && <p className="muted">Loading results</p>}

        {!loading && error && tab !== "guide" && (
          <section className="panel empty error">
            <h2>No results loaded</h2>
            <p>{error}</p>
            <p className="muted">
              Drop a <code>bundle.json</code> anywhere on this page or use Open bundle. Build one with{" "}
              <code>python -m fable.compute bundle &lt;run_dir&gt;</code>.
            </p>
          </section>
        )}

        {!loading && tab === "guide" && <Guide bundle={bundle} />}

        {!loading && bundle && tab !== "guide" && (
          // keyed on the bundle so every view resets when another file is opened
          <div key={`${bundle.source.run_id}|${bundle.source.generated_at}`}>
            <QualityBanner q={bundle.run_quality} />
            {tab === "summary" && <Summary bundle={bundle} ix={ix} />}
            {tab === "compare" && <Compare ix={ix} />}
            {tab === "iamc" && <IamcExport bundle={bundle} />}
            {tab === "explore" && <TableExplorer bundle={bundle} />}
            {tab === "deviation" && <DeviationAnalysis bundle={bundle} />}
            {tab === "overview" && <Overview bundle={bundle} />}
          </div>
        )}
      </main>

      <footer className="foot">
        FABLE Explorer reads a <code>bundle.json</code> in your browser. Files you open stay on your computer.
      </footer>

      {dragging && <div className="drop-hint">Drop bundle.json to open it</div>}
    </div>
    </HighlightContext.Provider>
  );
}
