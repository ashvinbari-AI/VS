# Evaluation & Validation System

An independent layer that tests the production Political Person Social
Media Intelligence app — it never modifies scraper logic, the analytics
engine, the NLP classifiers, or the React dashboard. Every evaluator here
either calls the real `backend/app/...` functions directly (engagement,
activity, comparison — see `evaluation/utils/backend_bridge.py`) or reads
the app's own stored output (`data/processed/*.parquet`,
`data/analysis/nlp_cache.json`) and checks it against manually verified
ground truth.

**If production output is wrong, this reports the error. Ground truth is
never adjusted to match a wrong production result.**

## Why ground truth is never auto-generated

Every `evaluation/ground_truth/*.json` file starts as `[]`. Nothing here
is derived from the scraper's own output — doing that would grade the
production system against a copy of itself, which proves nothing (this is
literally what the master prompt driving this system explicitly forbids).
A field only becomes "ground truth" once a person looks at the real post
on Instagram/Facebook and writes down what they actually see.

## Quick start

```powershell
# from the project root, using the backend's own virtualenv:
backend\.venv\Scripts\python.exe -m evaluation.run
backend\.venv\Scripts\python.exe -m evaluation.run --module scraper
backend\.venv\Scripts\python.exe -m evaluation.run --module metrics
backend\.venv\Scripts\python.exe -m evaluation.run --module nlp
backend\.venv\Scripts\python.exe -m evaluation.run --module comparison
backend\.venv\Scripts\python.exe -m evaluation.run --save-baseline   # promote this run to the regression baseline
```
Reports land in `evaluation/reports/<run_id>.json` (+ a `_scorecard.csv`).
Exit code is `1` if any scorecard entry is `FAIL` (spec §55 — wire this
into CI whenever you have one).

Unit tests (synthetic data only, deterministic, no ground truth needed):
```powershell
cd backend
.venv\Scripts\pytest ..\evaluation\tests -q
```

## How to read the output

- **PASS / WARNING / FAIL** — against this project's own thresholds in
  `evaluation/config/thresholds.yaml`, not an industry standard.
- **NOT_EVALUATED** — no ground truth exists yet for that metric. This is
  the expected state until you annotate real records; it is never
  silently treated as a pass.
- Categories (**data / analytics / nlp**) are reported **separately** —
  there is deliberately no single blended "overall accuracy" number (spec
  §30). A 100% engagement-arithmetic score and an 84% sentiment F1 measure
  two completely different things.
- **Precision / Recall / F1**: precision = of everything the model called
  X, how much really was X; recall = of everything that really was X, how
  much did the model catch; F1 = their harmonic mean. A confusion matrix
  breaks that down by exact predicted-vs-actual pairs.
- **Model-classified**, never "truth": sentiment/narrative/theme/issue
  labels the production system produced are compared against a *human's*
  label — the human label is ground truth, the model's is a prediction
  being graded, however good it is.

## How to add ground truth

1. Pick a handful of real, already-scraped posts/comments (see
   `data/processed/content.parquet` / `comments.parquet` for real ids).
2. Open each one on the actual platform, or read the caption/comment text
   directly out of the parquet/JSONL.
3. Add one JSON object per record to the relevant file under
   `evaluation/ground_truth/` — see `ground_truth/README.md` for the exact
   schema of each file, and `annotations/README.md` for the fuller
   per-field annotation guide.
4. Re-run `python -m evaluation.run` — that module's metrics move from
   `NOT_EVALUATED` to a real number.

## What's implemented (Phases 1–6 of the master prompt)

- Folder structure at the project root (this folder), independent of `backend/`/`frontend/`.
- Deterministic evaluators, all calling the real production functions:
  data completeness, field accuracy (+ content-type confusion matrix),
  data quality, duplicate detection, engagement + engagement-rate formula,
  average/median/P90, activity metrics, comparison-engine winner logic
  (including the missing/zero/null/equal edge cases).
- NLP evaluators (sentiment, narrative, comment theme, issue detection)
  reading the real `nlp_cache.json` against ground truth — micro/macro
  precision/recall/F1, confusion matrices, worst-category-first sorting,
  per-record error lists.
- Shared metric primitives: precision/recall/F1, confusion matrix,
  multi-label micro/macro, **Cohen's Kappa** (inter-annotator agreement),
  **bootstrap confidence intervals**.
- Configurable thresholds (`config/thresholds.yaml`) → PASS/WARNING/FAIL.
- Regression comparison against a saved baseline, with a
  `max_allowed_drop_pct_points` threshold and a non-zero exit code on FAIL.
- CLI (`python -m evaluation.run`), console report, JSON + CSV report
  files, a "limitations" section written automatically into every report.
- Ground-truth templates + annotation-format docs for every task, and a
  golden-vs-tuning dataset split to prevent data leakage.
- Full unit-test suite (`evaluation/tests/`) against synthetic, clearly
  marked test fixtures — no real ground truth required to run it.

## What's deliberately NOT built yet (Phases 7–10)

These are large, separate pieces of work this session stopped short of to
avoid producing 74 sections of untested code in one pass. Ask for any of
these specifically when you want them:

- **FastAPI evaluation endpoints** (spec §34) — the CLI/report JSON exists;
  nothing in `backend/app/routers/` exposes it over HTTP yet.
- **React Evaluation dashboard** (spec §35–44) — no sidebar section, no
  pages, no confusion-matrix charts yet.
- **HTML/PDF report rendering** (spec §45) — JSON + CSV are written; HTML/PDF are not.
- **Human review queue** (spec §66), **prompt-versioning files** (spec
  §49), **model-versioning metadata beyond what `nlp_cache.json` already
  stores** (spec §48).
- **`docs/EVALUATION_METHODOLOGY.md`** (spec §69) — this README covers the
  same ground informally; the dedicated methodology doc for a senior
  reviewer isn't written yet.
- A dedicated **two-annotator Cohen's Kappa CLI command** — the math
  (`cohens_kappa`) is implemented and tested; wiring it to read two
  annotator files end-to-end is not.

## Known, honest limitations (also written into every report)

- Duplicate-detection evaluation checks the *actual* production rule
  (content-id equality) — it structurally cannot detect two different-id
  records that are really the same post. That's a real system limitation,
  correctly surfaced as a false negative, not an evaluator bug.
- Geography evaluation (spec §23) is not implemented: the app's Geography
  feature was removed from this project earlier, so there is nothing left
  to evaluate. Re-add `evaluators/geography.py` +
  `ground_truth/geography_ground_truth.json` if Geography ever comes back.
- NLP evaluation reads whatever's cached in `data/analysis/nlp_cache.json`
  — it doesn't force a fresh Gemini/local-transformer call. Run **Run
  Analysis** in the app first so there's something to compare against.
