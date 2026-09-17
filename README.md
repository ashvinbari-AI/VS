# Political Person Social Media Intelligence

**Instagram + Facebook Political Profile Comparison Platform** — local-only.

Compares any two political people's Instagram/Facebook activity using your
existing `ig_scraper.py` / `fb_scraper.py` scrapers as the sole data source.
Everything runs on your Windows machine: React frontend, FastAPI backend,
JSON/Parquet storage. Nothing is deployed to the cloud, and no data leaves
the machine unless you explicitly enable Gemini NLP.

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
        +-- nlp/                narrative/sentiment/theme/issue classification
        |                        (local rule-based, or Gemini if enabled)
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
| `GEMINI_API_KEY` | Optional. Enables Gemini for narrative/sentiment/theme/issue NLP only. | empty (Gemini disabled) |
| `GEMINI_MODEL` | Gemini model name | `gemini-2.0-flash` |
| `SENTIMENT_MODEL` | Optional. Local, offline HuggingFace sentiment model for non-Devanagari text — SENTIMENT only, needs `transformers`+`torch` installed. | empty (lexicon fallback) |
| `MARATHI_SENTIMENT_MODEL` | Optional. Same, for Devanagari-script (Marathi) text. | empty (lexicon fallback) |
| `DATA_DIR` | Where raw/processed/analysis/mock data lives | `./data` |
| `DEFAULT_PERIOD_DAYS` | Default comparison window | `30` |
| `DISPLAY_TIMEZONE` | Timezone for display dates | `Asia/Kolkata` |

**Never commit `.env`.** `GEMINI_API_KEY` is never logged or sent to the
frontend — `GET /api/settings` only reports whether one is configured.

## 4. Running it

### One command
```powershell
python start_all.py
```
Prints the backend (`http://127.0.0.1:8000`, docs at `/docs`) and frontend
(`http://127.0.0.1:5173`) URLs. Handles port conflicts by trying the next
free port.

### Manually (two terminals)
```powershell
# Terminal 1 -- backend
cd backend
.venv\Scripts\uvicorn app.main:app --reload --port 8000

# Terminal 2 -- frontend
cd frontend
npm run dev
```

## 5. First-time workflow

1. Open the app, go to **Data Sources**.
2. **Add Person** — name + Instagram/Facebook profile URLs. Repeat for a
   second person. You can save any number of people, not just two — pick
   which two to compare from the header dropdowns.
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
   - Runs NLP (narrative/sentiment/theme/issue) — local rule-based by
     default, a local transformer for sentiment if configured (section 7a),
     or Gemini if enabled in Settings — and caches results in
     `data/analysis/nlp_cache.json` so nothing is re-analyzed twice.
5. Select both people in the header and explore Overview, Comparison,
   Activity, Engagement, Narratives, Sentiment, Comments, Timeline, and
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

## 7. Enabling Gemini NLP

1. Put your key in `.env`: `GEMINI_API_KEY=...`
2. Restart the backend.
3. In Settings, toggle **Enable Gemini NLP** on.

Gemini is used **only** for narrative classification, sentiment, comment
theme, and issue extraction — every count/average/median/engagement-rate
number in the app is plain Python/pandas arithmetic and is computed the
same way whether Gemini is on or off. Results are cached by `content_id`
in `data/analysis/nlp_cache.json`, so re-running analysis doesn't re-spend
API calls on content already classified. If Gemini is unreachable (no key,
rate limit, network error), the app automatically falls back to the local
rule-based classifier — it never crashes on a missing/failed Gemini call.

## 7a. Local transformer sentiment (optional)

A step up from the keyword lexicon that still never sends data off this
machine — no API key needed:

```powershell
cd backend
.venv\Scripts\pip install transformers torch
```

Then in `.env`:
```
SENTIMENT_MODEL=cardiffnlp/twitter-xlm-roberta-base-sentiment
MARATHI_SENTIMENT_MODEL=l3cube-pune/marathi-sentiment-political-tweets
```
Restart the backend. Devanagari-script text (Marathi) is routed to
`MARATHI_SENTIMENT_MODEL`; everything else (English, transliterated text)
uses `SENTIMENT_MODEL`. **Sentiment only** — narrative, comment theme, and
issue extraction have no local-transformer tier and stay on the keyword
lexicon unless Gemini is enabled. Priority order is Gemini (if enabled) →
local transformer (if configured) → keyword lexicon, so this only takes
effect when Gemini NLP is off. Each model is downloaded from Hugging Face
on first use and cached locally by `transformers` — the first analysis run
after enabling this will be slower. Results are labeled `transformer:<model
name>`, distinct from `gemini:<model>` and `rule_based_v1`, everywhere the
app shows which classifier produced a value. If either package is missing,
a model fails to download, or a model's own output label can't be mapped
to Positive/Negative/Neutral with confidence, the app logs a warning and
falls back to the keyword lexicon — same never-crash, never-guess contract
as the Gemini path.

## 8. Folder structure

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
    nlp/                            narrative.py, sentiment.py, comment_theme.py,
                                     issue_extraction.py, gemini_client.py, cache.py
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

## 8a. Evaluation & validation

A separate `evaluation/` package (own README at `evaluation/README.md`)
tests this app's real analytics/NLP output against manually verified
ground truth — data completeness, field accuracy, engagement/activity
arithmetic, comparison-engine logic, and sentiment/narrative/theme/issue
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

## 9. Troubleshooting

- **"No saved session" when starting a scrape** — run
  `python ig_scraper.py login` or `python fb_scraper.py login` once from
  the project root first.
- **Facebook scrape returns 0 posts** — this is a scraper-layer issue
  (session/selectors/date window), not the platform; check
  `logs/scraper.log` and try `--headed` with a shorter `--days`.
- **Devanagari/emoji text garbled in a Windows terminal** — that's the
  terminal's code page, not the app; the browser UI and the stored
  JSON/Parquet files are correct UTF-8 throughout.
- **Port already in use** — `start_all.py` automatically tries the next
  free port for both backend and frontend; if you start them manually,
  pass `--port` explicitly.
- **Gemini errors** — check `logs/analysis.log`; the app always falls
  back to local rule-based NLP and keeps working.

## 10. Tests

```powershell
cd backend
.venv\Scripts\pytest -q
```

Covers: engagement math with null shares/followers/comments (must not
crash — spec requirement), median vs. average, activity/day-of-week/hour,
narrative diversity, deterministic dedup, normalization against real
scraper field shapes (including the Instagram hardcoded-placeholder
handling), the NLP cache, and core API routes.
