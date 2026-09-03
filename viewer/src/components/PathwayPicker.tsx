import { BASELINE_MODE_LABEL, BaselineMode } from "../lib/table";
import { seriesColor } from "./Chart";

export default function PathwayPicker({
  pathways,
  selected,
  onToggle,
  baseline,
  onBaseline,
  mode,
  onMode,
}: {
  pathways: string[];
  selected: Set<string>;
  onToggle: (p: string) => void;
  baseline: string;
  onBaseline: (p: string) => void;
  mode: BaselineMode;
  onMode: (m: BaselineMode) => void;
}) {
  return (
    <div className="picker">
      <div className="picker-row">
        <span className="picker-label">Pathways</span>
        <div className="chips">
          {pathways.map((p, i) => (
            <button
              key={p}
              className={`chip ${selected.has(p) ? "chip-on" : ""}`}
              style={
                selected.has(p)
                  ? { borderColor: seriesColor(i), color: seriesColor(i) }
                  : undefined
              }
              onClick={() => onToggle(p)}
            >
              {p}
            </button>
          ))}
        </div>
      </div>
      <div className="picker-row">
        <label className="picker-label" htmlFor="baseline">
          Baseline
        </label>
        <select
          id="baseline"
          value={baseline}
          onChange={(e) => onBaseline(e.target.value)}
        >
          {pathways.map((p) => (
            <option key={p} value={p}>
              {p}
            </option>
          ))}
        </select>
        <div className="segmented">
          {(Object.keys(BASELINE_MODE_LABEL) as BaselineMode[]).map((m) => (
            <button
              key={m}
              className={mode === m ? "seg-on" : ""}
              onClick={() => onMode(m)}
            >
              {BASELINE_MODE_LABEL[m]}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
