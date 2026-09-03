# Deploying the FABLE web app

Two moving parts, joined by [`fable/contract/bundle.schema.json`](../fable/contract/bundle.schema.json):

| Part | Where it runs | Output |
| --- | --- | --- |
| **compute** — workbook → recalc pathways → `bundle.json` | your machine (Excel), or a self-hosted CI runner with Excel | `viewer/public/data/bundle.json` |
| **viewer** — static React app | GitHub Pages | the site |

The viewer only ever reads a committed `bundle.json`. Whatever breaks in
compute, the site keeps serving the last good bundle.

---

## One-time GitHub setup

1. **Settings → Pages → Build and deployment → Source: GitHub Actions.**
2. Nothing else. `contents` is the only token the deploy needs beyond Pages.

---

## Normal flow (GitHub-Pages-only, no CI compute)

You have Excel; CI does not. So recalc locally, commit the bundle, let CI deploy.

```bash
# once
python -m venv .venv && . .venv/bin/activate
pip install -e ".[excel,dev]"

# each refresh — recalc every pathway and write the bundle
python -m fable.compute run workbooks/FABLEPAKUP50.xlsx --workers 8 --out viewer/public/data

# review the gate, then commit
cat viewer/public/data/gate.json
git add viewer/public/data/bundle.json && git commit -m "data: refresh bundle" && git push
```

The push triggers **Deploy viewer to GitHub Pages**
([`deploy-pages.yml`](../.github/workflows/deploy-pages.yml)) → site updates.

`gate.json` is git-ignored on purpose; only `bundle.json` is committed.

### Just changed a chart, not the data?

Edit `viewer/`, push. Same deploy workflow, existing bundle.

---

## Refreshing the bundle without local Excel

### From an already-exported CSV run directory

Zip an `exports/all_pathways_run_*` directory, put it anywhere with a URL
(release asset, gist, S3), then run the **Rebuild bundle** workflow
([`bundle.yml`](../.github/workflows/bundle.yml)) with `source = zip-url`.
It builds `bundle.json`, runs the publish gate, and uploads it as an artifact.
Set `commit = true` to have it commit back (defaults off).

### Full recalc in CI

Needs a **self-hosted runner with Excel**
([`recalc-selfhosted.yml`](../.github/workflows/recalc-selfhosted.yml),
labels `self-hosted, windows, excel`). Then compute never touches your laptop:
dispatch the workflow with a `workbook_url`, it recalcs (`--workers`), bundles,
and uploads / optionally commits.

The licence-free alternative — a LibreOffice engine that runs on stock Ubuntu
runners — is scaffolded but not implemented; see
[`fable/contract/CONTRACT.md`](../fable/contract/CONTRACT.md).

---

## Scaling: hundreds / thousands of pathways

Shard the recalc; the bundle build stays trivial.

* **One box, many cores:** `--workers N` (N Excel processes).
* **Many boxes / CI matrix jobs:** each does
  `python -m fable.compute recalc WB.xlsx --pathway-slice A:B --run-dir shared/run`
  over a disjoint range, then one job runs
  `python -m fable.compute bundle shared/run` on the merged directory.
* Identical scenario tuples are recalculated once regardless of shard layout.
* A killed run resumes — pathways with CSVs already on disk are skipped.

See [`fable/README.md`](../fable/README.md#scaling-to-hundreds-of-pathways).

---

## Base path / custom domain

`viewer/vite.config.ts` defaults `base` to `/FABLE_Pakistan/` (project site at
`https://<user>.github.io/FABLE_Pakistan/`).

* **User/org site** (`<user>.github.io`) or **custom domain:** run
  **Deploy viewer** manually with `base_path = /`, or set `VITE_BASE=/` and
  commit a change to `vite.config.ts`.
* Add a `viewer/public/CNAME` file for a custom domain.

---

## Local preview of the production build

```bash
cd viewer
npm ci
npm run build && npm run preview   # http://localhost:4173/FABLE_Pakistan/
```

## Workflows at a glance

| File | Trigger | Does |
| --- | --- | --- |
| `ci.yml` | push / PR | pytest, golden-bundle gate, viewer typecheck + build |
| `deploy-pages.yml` | push to `main` touching `viewer/**`, or manual | build viewer, deploy Pages |
| `bundle.yml` | manual | CSV run dir → `bundle.json` (+ gate), artifact / opt-in commit |
| `recalc-selfhosted.yml` | manual | full recalc on a self-hosted Excel runner |
