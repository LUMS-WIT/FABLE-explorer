import { RunQuality } from "../bundle/types";

export default function QualityBanner({ q }: { q: RunQuality }) {
  if (q.status === "ok") return null;
  const failedChecks = q.checks.filter((c) => !c.ok);
  return (
    <div className={`banner banner-${q.status}`}>
      <strong>
        {q.status === "failed" ? "Run failed" : "Partial run"} —{" "}
        {q.pathways_ok}/{q.pathways_expected} pathways succeeded
      </strong>
      {q.failures.length > 0 && (
        <ul>
          {q.failures.map((f) => (
            <li key={f.pathway}>
              <code>{f.pathway}</code>: {f.error}
            </li>
          ))}
        </ul>
      )}
      {failedChecks.length > 0 && (
        <ul>
          {failedChecks.map((c) => (
            <li key={c.name}>
              {c.name}
              {c.detail ? ` — ${c.detail}` : ""}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
