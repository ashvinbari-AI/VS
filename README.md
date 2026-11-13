# Competitor Analysis

**Instagram + Facebook Competitor Comparison Platform** — local-only.

Compares any two political people's Instagram/Facebook activity using your
existing `ig_scraper.py` / `fb_scraper.py` scrapers as the sole data source.
Everything runs on your Windows machine: React frontend, FastAPI backend,
JSON/Parquet storage. Nothing is deployed to the cloud, and the app itself
sends no data off the machine.

---

## 1. Architecture

```
React (Vite/TS/Tailwind)
        |  REST (/api/*)
        v
FastAPI backend
        |
        +-- scrapers/          subprocess wrappers around YOUR ig_scraper.py / fb_scraper.py
        +-- ingestion/         normalizes raw JSONL -> internal schema, dedupes
        +-- analytics/         deterministic Python metrics (no LLM)
        +-- nlp/                comment theme/issue classification
        |                        (local keyword-based)
        +-- storage/           JSON (configs/jobs) + Parquet (processed data)
        v
data/
  raw/<person_id>/<platform>/       untouched scraped evidence (JSONL+CSV)
  processed/*.parquet               normalized, deduped, analytics-ready
  analysis/                         nlp_cache.json, per-person/comparison output
  mock/                             synthetic DEMO MODE data only
```

Your scrapers (`ig_scraper.py`, `fb_scraper.py`, `schema_store.py`,
`selector_overrides.py`, `run_both.py`) are **untouched** — the platform
only shells out to their existing `scrape` CLI subcommand and reads the
JSONL/CSV they already write.

## 2. What's real vs. what's a known scraper limitation

Verified against your actual `output/` data (Devendra Fadnavis, 25 IG
posts, 6,855 comments):

- **Real, per-platform**: post/reel/video/photo type, caption, timestamp,
  likes, comment count, follower snapshot per scrape run.
- **Facebook only, real**: `share_count`, `view_count`, `media_urls`,
  per-type reaction breakdown, per-comment timestamp.
- **Instagram**: `ig_scraper.py`'s `build_post()` hardcodes
  `share_count=0`, `view_count=0`, `media_urls=[]`, and never exposes a
  per-comment timestamp — these are scraper placeholders, not real
  measurements, so the normalization layer (`backend/app/ingestion/normalize.py`)
  maps them to `None` → the UI shows **N/A**, never a fake `0`.
  If you extend `ig_scraper.py` to capture these for real, no platform
  change is needed — the adapter will just start passing real values through.
- **Not available from either scraper, at all**: `following` count, any
  geographic/location field. Hashtags/mentions are **parsed** deterministically
  out of the caption text (not scraped separately, not AI-generated).
- Followers are a **per-scrape-run snapshot**, not per-post — every post's
  `followers_at_collection` is joined from its scrape run.

## 3. Installation

### Python (backend)
Requires Python 3.11+ (tested with 3.12 — pyarrow/pandas wheels for very
new Python versions may lag, so 3.12 is recommended over bleeding-edge).

```powershell
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

### Node (frontend)
Requires Node 18+ (tested with Node 24).

```powershell
cd frontend
npm install
```

### Environment variables
Copy `.env.example` to `.env` in the project root:

```powershell
copy .env.example .env
```

| Variable | Purpose | Default |
|---|---|---|
| `DATA_DIR` | Where raw/processed/analysis/mock data lives | `./data` |
| `DEFAULT_PERIOD_DAYS` | Default comparison window | `30` |
| `DISPLAY_TIMEZONE` | Timezone for display dates | `Asia/Kolkata` |

**Never commit `.env`.**

## 4. Running it

### One command
```powershell
python start_all.py
```
Prints the backend (`http://127.0.0.1:3001`, docs at `/docs`) and frontend
(`http://127.0.0.1:5173`) URLs. The backend always uses fixed port 3001; if
something else is using it, the launcher stops and says so. The frontend
moves to the next free port if 5173 is taken.

### Manually (two terminals)
```powershell
# Terminal 1 -- backend
cd backend
.venv\Scripts\uvicorn app.main:app --reload --port 3001

# Terminal 2 -- frontend
cd frontend
npm run dev
```

## 5. First-time workflow

1. Open the app, go to **Data Sources**.
2. **Add Person** — name + Instagram/Facebook profile URLs. Repeat for
   everyone you want to compare. You can save any number of people and
   compare up to 6 at once (A vs B vs C vs D ...) — pick them in the header
   and use **+ Add person** for each extra one. Each person keeps their own
   color across every chart.
3. Get data into a person, either:
   - **Start Scraping** — runs your `ig_scraper.py` / `fb_scraper.py`
     `scrape` command as a background job (progress shown live). Requires
     you to have already run `python ig_scraper.py login` /
     `python fb_scraper.py login` once, in this project's root, so a saved
     session exists (`ig_session/cookies.pkl`, `fb_session/`). Facebook
     comment depth needs a **headed** (visible) browser — the platform
     defaults to headed for Facebook.
   - **Load Existing Data** — if you already scraped into a folder (e.g.
     this project's own `output/instagram`), type that folder's path and
     click Load Existing. It **copies** (never moves/deletes) the JSONL/CSV
     into `data/raw/<person_id>/<platform>/imported_<timestamp>/`.
4. Click **Run Analysis** (Data Sources page). This:
   - Normalizes every raw JSONL file into the internal schema.
   - Deduplicates by `(platform, content_id)`.
   - Writes `data/processed/{content,comments,profiles}.parquet`.
   - Classifies each comment's theme and the public issues it mentions
     (local keyword matching) and caches results in
     `data/analysis/nlp_cache.json` so nothing is re-analyzed twice.
5. Select two or more people in the header and explore Overview, Comparison,
   Activity, Engagement, Content Mix, Comments, Timeline, and
   Content Explorer.

## 6. Demo mode

To try the dashboard before scraping anything:

Settings page → **Load Demo Data**. Generates a small, clearly-synthetic
dataset for two placeholder people ("Demo Leader A/B") into `data/mock/`
and switches the whole app into **DEMO MODE** (shown in the sidebar and on
Data Sources). It never touches or mixes with real scraped data — disable
it from the same Settings page to go back to your real data.

Or from the command line:
```powershell
cd backend
.venv\Scripts\python -m app.demo.demo_data
```

## 7. Folder structure

```
ig_scraper.py, fb_scraper.py,       <- YOUR existing scrapers, untouched
schema_store.py, selector_overrides.py, run_both.py
output/                              <- your scrapers' default --out folder

backend/
  app/
    main.py                         FastAPI app
    config.py                       Settings (.env-backed)
    scrapers/                       ScraperAdapter subprocess wrappers
    ingestion/                      normalize.py, dedupe.py, ingest.py, import_existing.py
    storage/                        parquet_store.py, json_store.py, data_source.py
    analytics/                      engine.py (deterministic metrics), comparison.py
    nlp/                            comment_theme.py, issue_extraction.py, cache.py
    jobs/                           background job manager (scrape/analysis)
    routers/                        one file per API area
    demo/                           demo_data.py
  tests/                            pytest suite
  requirements.txt
  .venv/                            (created by you, gitignored)

frontend/
  src/
    components/                     Layout, KPI, Tables, ContentDrawer, states
    pages/                          one per sidebar item
    hooks/, services/, state/, types/, utils/

data/
  raw/<person_id>/<platform>/       untouched scraped evidence
  processed/                        content.parquet, comments.parquet, profiles.parquet
  analysis/                         nlp_cache.json, per-person/comparison outputs
  mock/                             DEMO MODE data only
  configs/                          people/*.json, settings.json

evaluation/                         independent evaluation/validation layer -- see evaluation/README.md
  ground_truth/, datasets/, evaluators/, metrics/, tests/, reports/,
  regression/, annotations/, config/, run.py

logs/                                backend.log, scraper.log, analysis.log
start_all.py
```

## 7a. Evaluation & validation

A separate `evaluation/` package (own README at `evaluation/README.md`)
tests this app's real analytics/NLP output against manually verified
ground truth — data completeness, field accuracy, engagement/activity
arithmetic, comparison-engine logic, and comment theme/issue
classification (precision/recall/F1, confusion matrices), plus regression
tracking against a saved baseline. It never modifies scraper logic,
analytics, or the dashboard — it only reads their output.

```powershell
backend\.venv\Scripts\python.exe -m evaluation.run
```
Ground truth starts empty (nothing here is auto-generated from scraped
data) — see `evaluation/ground_truth/README.md` for how to add manually
verified records. Full scope of what's built vs. still planned (a React
dashboard and FastAPI endpoints for it are not built yet) is in
`evaluation/README.md`.

## 8. Troubleshooting

- **"No saved session" when starting a scrape** — run
  `python ig_scraper.py login` or `python fb_scraper.py login` once from
  the project root first.
- **Facebook scrape returns 0 posts** — this is a scraper-layer issue
  (session/selectors/date window), not the platform; check
  `logs/scraper.log` and try `--headed` with a shorter `--days`.
- **Devanagari/emoji text garbled in a Windows terminal** — that's the
  terminal's code page, not the app; the browser UI and the stored
  JSON/Parquet files are correct UTF-8 throughout.
- **Port already in use** — the backend's port is fixed at 3001.
  `start_all.py` stops with a message if it's taken: run
  `netstat -ano | findstr :3001`, close that program, and retry, or use
  `python start_all.py --backend-port <port>` (the frontend follows it
  automatically).

## 9. Tests

```powershell
cd backend
.venv\Scripts\pytest -q
```

Covers: engagement math with null shares/followers/comments (must not
crash — spec requirement), median vs. average, activity/day-of-week/hour,
deterministic dedup, normalization against real
scraper field shapes (including the Instagram hardcoded-placeholder
handling), the NLP cache, and core API routes.
