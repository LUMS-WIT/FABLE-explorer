import { useCallback, useEffect, useState } from "react";
import { Bundle } from "./bundle/types";
import {
  BundleError,
  defaultBundleUrl,
  loadBundleFromFile,
  loadBundleFromUrl,
} from "./bundle/load";
import { fmtDate } from "./lib/format";
import QualityBanner from "./components/QualityBanner";
import Overview from "./components/Overview";
import TableExplorer from "./components/TableExplorer";
import DeviationAnalysis from "./components/DeviationAnalysis";

type Tab = "overview" | "explore" | "deviation";
const TABS: { id: Tab; label: string }[] = [
  { id: "overview", label: "Overview" },
  { id: "explore", label: "Table explorer" },
  { id: "deviation", label: "Deviation analysis" },
];

export default function App() {
  const [bundle, setBundle] = useState<Bundle | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<Tab>("overview");
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    loadBundleFromUrl(defaultBundleUrl())
      .then((b) => {
        setBundle(b);
        setError(null);
      })
      .catch((e) => setError(e instanceof BundleError ? e.message : String(e)))
      .finally(() => setLoading(false));
  }, []);

  const openFile = useCallback(async (file: File) => {
    setLoading(true);
    try {
      const b = await loadBundleFromFile(file);
      setBundle(b);
      setError(null);
      setTab("overview");
    } catch (e) {
      setError(e instanceof BundleError ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  return (
    <div
      className={`app ${dragging ? "dragging" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        const f = e.dataTransfer.files[0];
        if (f) void openFile(f);
      }}
    >
      <header className="topbar">
        <div className="brand">
          <span className="logo">▚</span> FABLE Explorer
          {bundle && (
            <span className="sub">
              {bundle.source.country} · {bundle.pathways.length} pathways ·{" "}
              {fmtDate(bundle.source.generated_at)}
            </span>
          )}
        </div>
        <label className="file-btn">
          Open bundle…
          <input
            type="file"
            accept="application/json,.json"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) void openFile(f);
            }}
          />
        </label>
      </header>

      {bundle && (
        <nav className="tabs">
          {TABS.map((t) => (
            <button
              key={t.id}
              className={tab === t.id ? "tab-on" : ""}
              onClick={() => setTab(t.id)}
            >
              {t.label}
            </button>
          ))}
        </nav>
      )}

      <main className="content">
        {loading && <p className="muted">Loading bundle…</p>}

        {!loading && error && (
          <div className="card error">
            <h3>Could not load a bundle</h3>
            <p>{error}</p>
            <p className="muted">
              Drop a <code>bundle.json</code> anywhere on this page, or use
              “Open bundle…”. Generate one with{" "}
              <code>python -m fable.compute bundle &lt;run_dir&gt;</code>.
            </p>
          </div>
        )}

        {!loading && bundle && (
          <>
            <QualityBanner q={bundle.run_quality} />
            {tab === "overview" && <Overview bundle={bundle} />}
            {tab === "explore" && <TableExplorer bundle={bundle} />}
            {tab === "deviation" && <DeviationAnalysis bundle={bundle} />}
          </>
        )}
      </main>

      {dragging && <div className="drop-hint">Drop bundle.json to load</div>}
    </div>
  );
}
