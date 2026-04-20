# Job Aggregator Architecture

This document outlines the complete architecture, data flow, and functional mechanisms of the Job Aggregator system. The system fetches jobs from multiple Finnish job boards, deduplicates them, translates them using Google Translate (via deep-translator), formats them using a local AI (Ollama), and generates static HTML pages for a fast frontend experience.

---

## 1. System Overview

The pipeline operates in a fully automated, scheduled loop, split into **four distinct phases**:

```
┌───────────────┐   ┌───────────────────┐   ┌───────────────────┐   ┌────────────────────┐
│  Phase 1      │──▶│  Phase 2          │──▶│  Phase 3          │──▶│  Phase 4           │
│  SCRAPING     │   │  TRANSLATION      │   │  AI FORMATTING    │   │  SITE GENERATION   │
│               │   │                   │   │                   │   │                    │
│  Duunitori    │   │  Argos FI→EN      │   │  Rule-based cat   │   │  HTML pages        │
│  Työmkturi    │   │  (offline)        │   │  + Ollama formats │   │  index/jobs.html   │
│  Jobly        │   │                   │   │  structured JSON  │   │  sitemap-jobs.xml  │
│               │   │  Translates:      │   │  Python locks     │   │  OG images         │
│  → rawjobs    │   │  title+jobcontent │   │  factual fields   │   │  Firebase alerts   │
│    .json      │   │  → translated_    │   │  → jobs.json      │   │                    │
│               │   │    content field  │   │                   │   │  ↓ (background)    │
│               │   │  → translated_    │   │                   │   │  Category post-    │
│               │   │    jobs.json      │   │                   │   │  check (Ollama)    │
└───────────────┘   └───────────────────┘   └───────────────────┘   └────────────────────┘
 run_scraper.py      job_translator.py        ai_processor.py          html_generator.py
                     translate_raw_jobs()     format_translated_       image_generator.py
                     run_phase2()             jobs()                   firebase_client.py
                                                                        category_post_check.py
```

Automated via **Windows Task Scheduler** at specific intervals, ensuring fresh data flows onto the live site at `findjobsinfinland.fi`.

---

## 2. Phase 1: Scraping (`run_scraper.py`)

Scraping is orchestrated by `scraper/run_scraper.py`, using a centralized `DeduplicationState` memory store to prevent duplicate job entries across runs and modules.

### Data Flow
1. **Load State**: Loads existing entries from `scraper/data/rawjobs.json` and builds dedup sets (tracking IDs, titles+companies, and apply URLs).
2. **Execute Modules**: Runs three independent scraper modules sequentially:
   - **`scraper_tyomarkkinatori.py`**: Fetches from Työmarkkinatori JSON API. Extracts structured fields including ESCO occupation codes, location data, salary, and employer contact info.
   - **`scraper_duunitori.py`**: Parses paginated HTML listings from duunitori.fi, then fetches each job's detail page for the full description and apply URL.
   - **`scraper_jobly.py`**: Parses XML sitemaps from Jobly, extracts JSON-LD structured data using `cloudscraper` to bypass Cloudflare.
3. **Normalize**: Each module calls `normalise_raw_job()` to standardize field names, generate hash IDs, and ensure consistent structure.
4. **Persist**: Newly gathered, verified unique jobs are appended to `scraper/data/rawjobs.json` with `ai_processed: false`.

### Deduplication
- **Hash ID**: 8-char hash from `title + location + jobLink`.
- **Title+Company pair**: Prevents same job from different sources.
- **Apply URL**: Catches exact duplicate listings.

### Output → `rawjobs.json`
```json
{
  "id": "8-char hash",
  "title": "Finnish title (raw)",
  "company": "Company name",
  "jobLocation": ["City1", "City2"],
  "jobcontent": "Full Finnish job description text",
  "jobapply_link": "URL or mailto:",
  "salary_range": "",
  "workTime": "Full-time",
  "language_requirements": ["Finnish"],
  "source": "tyomarkkinatori|duunitori|jobly",
  "ai_processed": false,
  "translated_content": null
}
```

---

## 3. Phase 2: Translation (`job_translator.py`)

**Purpose**: Translate all raw Finnish job text to English using Google Translate via deep-translator.

**File**: `scraper/job_translator.py`

### How It Works
1. `run_phase2()` is called by the pipeline.
2. Scans all raw jobs for those missing a `translated_content` field.
3. For each untranslated job, concatenates `title + jobcontent` into a single text block.
4. Passes the text through `translator.translate_fi_to_en()` (Google Translator logic).
5. Stores the result in the `translated_content` field on the raw job.
6. Saves the updated `rawjobs.json` (with translations cached).
7. **Saves `translated_jobs.json`** — a snapshot of the raw jobs with their translations, available for inspection before Phase 3.

### Key Functions
| Function | Purpose |
|----------|--------|
| `translate_raw_jobs(raw_jobs)` | Translates untranslated jobs, returns updated list |
| `run_phase2(raw_jobs)` | Full Phase 2: translate + save to rawjobs.json + translated_jobs.json |

### Key Design Decisions
- **Online**: Uses deep-translator to fetch translations via Google Translate API with built-in retries.
- **Cached**: Once translated, the `translated_content` field persists across pipeline runs. Only new/untranslated jobs are processed.
- **Decoupled**: Translation is completely separate from AI formatting. If the AI fails in Phase 3, the translation is still saved.
- **Inspectable**: `translated_jobs.json` is written at the end of Phase 2 so you can verify translations before AI formatting.
- **Reset**: `--reset-raw` clears both `ai_processed` and `translated_content`, forcing full retranslation.
- **Standalone**: Can be run independently: `python job_translator.py`

### Output
The `translated_content` field is added to each raw job in `rawjobs.json`:
```json
{
  "id": "201d6916",
  "title": "Myyntiedustaja / Mosvex Oy",
  "translated_content": "Sales Representative / Mosvex Oy\nWe are looking for sales representatives..."
}
```

---

## 4. Phase 3: AI Formatting (`ai_processor.py`)

**Purpose**: Take the pre-translated English text and format it into structured JSON fields using a local AI model (Ollama), combined with Python for factual fields.

**File**: `scraper/ai_processor.py`

### Key Functions
| Function | Purpose |
|----------|--------|
| `format_translated_jobs(raw_jobs, batch_size)` | Phase 3 entry point: format unprocessed jobs |
| `_call_ollama_for_content(text, raw_job, category)` | Send translated text to Ollama for structured extraction |
| `_build_formatted_job(raw, ai_data)` | Merge AI output with Python factual fields |
| `_build_fallback_ai_data(raw, category)` | Fallback when AI fails: Python extraction + translation |
| `apply_manual_fixes(job)` | Post-processing: salary normalization, Finnish sweep |
| `_sweep_finnish_from_job(job)` | Final safety net: catch remaining Finnish, retranslate |

### Pipeline Per Job

```
Pre-translated English text (from Phase 2)
      │
      ▼
┌─────────────────────────────────────┐
│  Step 1: CATEGORY DETECTION         │
│  detect_category_by_keywords()      │
│  Scores title + translated text     │
│  against job_categories.json.       │
│                                     │
│  Scoring rules:                     │
│  +50 ESCO label exact match         │
│  +35 ESCO substring containment     │
│  +15 ESCO word-level match          │
│  +12 Title exact keyword match      │
│  +8  Title contains keyword         │
│  +3x Text frequency (capped ×3)     │
│                                     │
│  Requires ≥ 2 distinct keyword      │
│  hits OR score ≥ 8 to classify.     │
│  No AI fallback — defaults to       │
│  "other" if score is 0.             │
└──────────────┬──────────────────────┘
               │ category determined
               ▼
┌─────────────────────────────────────┐
│  Step 2: AI FORMATTING              │
│  _call_ollama_for_content()         │
│  Ollama (qwen2.5:1.5b) reads the   │
│  ALREADY-TRANSLATED English text    │
│  and extracts structured fields:    │
│  - title (clean English)            │
│  - description (1 paragraph, ≤800c) │
│  - meta_description (SEO, ≤160c)    │
│  - job_responsibilities [3-6 items] │
│  - what_we_expect [3-6 items]       │
│  - what_we_offer [3-6 items]        │
│  - search_keywords (5-8 keywords)   │
│                                     │
│  AI does NOT translate — only       │
│  formats already-English text.      │
│                                     │
│  If AI fails → _build_fallback_     │
│  ai_data() uses Python extraction   │
│  + Google translation as fallback.  │
└──────────────┬──────────────────────┘
               │ structured ai_data
               ▼
┌─────────────────────────────────────┐
│  Step 3: PYTHON FACTUAL FIELDS      │
│  _build_formatted_job() locks:      │
│  - company (from raw, never AI)     │
│  - jobLocation (from raw or city    │
│    keyword detection)               │
│  - salary_range (regex extraction   │
│    or TES normalization)            │
│  - jobapply_link, jobLink           │
│  - job_employer_email/name/phone    │
│  - dates, open_positions            │
│  These are NEVER touched by AI.     │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Step 4: FINNISH SWEEP (SAFETY NET) │
│  _sweep_finnish_from_job()          │
│  Scans ALL text fields for Finnish  │
│  words using _looks_finnish().      │
│  If detected → retranslates with    │
│  Google Translate automatically.    │
│                                     │
│  Exempt fields (kept as-is):        │
│  - company                          │
│  - jobapply_link                    │
│  - job_employer_email               │
│  - job_employer_name                │
└──────────────┬──────────────────────┘
               │
               ▼
         Final formatted job
         → jobs.json (grouped by session)
         → formatted_jobs_flat.json (flat list)
```

### Who Does What

| Component | Responsibility |
|-----------|---------------|
| **Google Translate** (Phase 2) | **Translation**: Finnish → English. Uses deep-translator, cached in `translated_content`. |
| **Ollama** (Phase 3) | **Formatting**: Reads English text, extracts structured fields. Also picks category if string-match fails. |
| **Python** (Phase 3) | **Factual fields**: Company, location, salary, links, dates. Never delegated to AI. |
| **`_sweep_finnish_from_job()`** | **Safety net**: Catches any remaining Finnish after AI formatting and retranslates via Google Translate. |

### Salary Normalization
- Managed centrally by `patch_salary.py`:
  - Contains extensive regex mapping and rules.
  - Finnish collective agreement phrases (`TES`, `OVTES`, `työehtosopimus`, etc.) → normalized to: `"Competitive hourly wage based on Finnish collective agreements."`
  - Numeric salaries with `€` are kept as-is.
  - Integrated into Phase 3 processing.

### Category Classification Engine
- **Source of Truth**: 30 broad, predefined categories in `all_jobs_cat.json`.
- **Keyword Dictionary**: Populated from `job_categories.json`. Only keywords for categories present in `all_jobs_cat.json` are loaded (3 000+ keywords, Finnish + English).
- **Rule-Based Only**: `detect_category_by_keywords()` scores every category using ESCO occupation labels, title matching, and keyword frequency. Returns `(best_category, best_score)`. The highest-scoring category wins — **no AI involved in this step**.
- **Scoring thresholds**: requires either `≥ 2` distinct keyword hits OR a base score `≥ 8` (exact/partial title match). Jobs scoring 0 default to `"other"`.
- **AI tiebreaker removed**: Previously, Ollama was called as a fallback when the rule-based engine was ambiguous. This was removed to reduce latency and Ollama load during the main pipeline.

### Category Post-Check (`category_post_check.py`)
After each batch of 50 jobs is fully formatted and HTML/JSON is written, the pipeline runs a **synchronous, blocking** category verification pass before doing the git push:

```
Phase 3+4+5 complete for batch N
       │
       ▼  (BLOCKING — pipeline waits here)
┌──────────────────────────────────────────┐
│  category_post_check.run_check_sync()    │
│                                          │
│  For each newly formatted job:           │
│  1. Ask Ollama: "Is this category        │
│     correct? If not, return the slug."  │
│  2. If correction found:                 │
│     • Patch jobs.json + flat.json        │
│     • Move HTML file to new folder       │
│     • Patch jobs-table.html              │
│     • Write to category_changes_log.json │
│  3. Returns when all jobs are checked.  │
└──────────────────────────────────────────┘
       │
       ▼  (ONE git commit + push)
  All 50 jobs + any category corrections
  committed together in a single push.

  • Uses auto-detected Ollama model
    (llama3.x, gemma3, mistral, etc.)
  • Silently skips if Ollama offline
  • Thread-safe: file lock prevents
    concurrent corruption if called
    from multiple contexts
  • Source tagged "pipeline_post_check"
    in category_changes_log.json
```

This guarantees that by the time a batch is pushed to GitHub, every job is in its **correct category folder** — no stale misclassified pages ever reach the live site.

### Hallucination Detection
- `_is_irrelevant_ai_output()` checks if AI output has meaningful overlap with the original job title/content.
- Known hallucination words trigger rejection.
- Rejected AI output → fallback to Python extraction + Argos.

---

## 5. Phase 4: Site Generation

### 5.1 HTML Generation (`html_generator.py`)
- **Job Pages**: Compiles `job_template.html` into individual `/jobs/{category-slug}/{job-id}/index.html` pages.
- **Index Pages**: Updates `index.html` and `jobs.html` with job cards.
- **Sitemap**: Updates `sitemap-jobs.xml` with all active job URLs.
- **Dynamic Apply Links**: If `jobapply_link` is a `mailto:`, generates a pre-filled email template with subject and body.
- **Location Attributes**: Extracts and slugifies location data for `data-location` attributes, expanding with regional (e.g., `uusimaa`) and national (`finland`) contexts.
- **Recruiter Info**: Renders employer name, email, and phone on job pages with conditional display.

### 5.2 Image Generation (`image_generator.py`)
- Generates category-specific OG/meta images for social media sharing.
- Uses category-keyed image folders under `/images/jobs/{category-slug}/`.

### 5.3 Firebase Alerts (`firebase_client.py`)
- Sends push notifications for new job listings to subscribed users.
- Tracks sent alerts in `sent_alerts.json` to prevent duplicates.
- Uses Firebase Admin SDK with `serviceAccountKey.json`.

---

## 6. Data Stores

| File | Purpose | Written By |
|------|---------|------------|
| `rawjobs.json` | Raw Finnish jobs + `translated_content` | Phase 1 (scraper) + Phase 2 (`job_translator.py`) |
| `translated_jobs.json` | After Phase 2: raw jobs with translations. After Phase 3: formatted English jobs. | Phase 2 (`job_translator.py`), then Phase 3 (`ai_processor.py`) overwrites |
| `jobs.json` | Formatted English jobs, grouped by scrape session | Phase 3 (`ai_processor.py`) |
| `sent_alerts.json` | Job IDs that have had Firebase alerts sent | Phase 4 (`firebase_client.py`) |

---

## 7. Pipeline Orchestration (`run_pipeline.py`)

### Execution Flow
```
1. Load stores (rawjobs.json, jobs.json)
2. Reset if --reset-raw (clears ai_processed + translated_content)
3. Sync category directories (underscore → hyphen)
4. Expire old jobs (> EXPIRATION_DAYS)
───────────────────────────────────
5. PHASE 2: job_translator.run_phase2()
   → Translate untranslated raw jobs (Argos, offline)
   → Save rawjobs.json (with translated_content)
   → Save translated_raw_jobs.json (raw + translations)
───────────────────────────────────
6. Batched loop (PIPELINE_COMMIT_BATCH_SIZE jobs per iteration):

   a. PHASE 3: ai_processor.format_translated_jobs()
      → Rule-based category scoring (detect_category_by_keywords)
      → Ollama structures: title, description, meta, lists
      → Python locks factual fields (company, location, salary, links)
      → Finnish sweep safety net

   b. PHASE 4: Job_formatter.format_jobs()
      → Merges ai_data into final job schema
      → Generates job_id slug (title + location + hash)

   c. PHASE 5: Site generation
      → generate_images_for_jobs() — category stock images
      → generate_job_pages()       — /jobs/{cat}/{id}.html
      → update_main_pages()        — index.html, jobs.html
      → update_sitemap()           — sitemap-jobs.xml
      → save_formatted_jobs_flat() — formatted_jobs_flat.json
      → save_jobs()                — jobs.json
      → send_new_job_alerts()      — Firebase push notifications

   d. CATEGORY POST-CHECK (blocking — runs before git push)
      → category_post_check.run_check_sync(batch)
         Ollama verifies each job's category synchronously.
         If a correction is found → patches JSON + HTML files.
         Pipeline WAITS for this to complete.

   e. Git commit + push (one push covers batch + any corrections)
      → Commits all changes from this batch (new jobs + category fixes)
      → Pushes to GitHub Pages (live site update)
```

### CLI Commands
| Flag | Description |
|------|-------------|
| *(no flags)* | Full pipeline: Phase 2 + 3 + 4 |
| `--dry-run` | No disk writes, no AI/translation calls |
| `--reset-raw` | Reset all raw jobs (retranslate + reformat), then run |
| `--reset` | Nuclear: clear everything, reset raw + empty jobs.json |
| `--fix-dates` | Fix title casing + Finnish date formats, regenerate HTML |
| `--migrate` | One-time migration for category/date/salary/URL fixes |
| `--patch-titles` | Replace known Finnish titles with English equivalents |
| `--check-expires` | Print expiry stats for last 5 jobs |
| `--check-db` | Print Firebase document count + first 10 IDs |
| `--schedule` | Run pipeline now, then repeat every hour (blocking) |

---

## 8. Translation Layer (`translator.py`)

- Wraps `deep-translator` for Finnish → English translation over Google Translate.
- Handles chunking for strings larger than 4900 characters due to Google limits.
- Features retry logic and backoff. Falls back to original text if translation fails completely.
- Pre-processes text (removes excessive blank lines, unescapes HTML entities).

---

## 9. Finnish Detection (`_looks_finnish()`)

Comprehensive marker list for scanning output fields:
- **Job titles**: `työ`, `tekijä`, `myyjä`, `siivooja`, `kokki`, `hoitaja`, `kuljettaja`, etc.
- **Grammar**: `ja`, `sekä`, `osa-aik`, `vakituinen`, `määräaikainen`
- **Verbs**: `haemme`, `etsimme`, `tarjoamme`, `edellytämme`
- **Word endings**: `ämme`, `äinen`, `öinti`, `öissä`, `ässä`

Fields exempt from Finnish detection (kept as-is):
- `company`, `jobapply_link`, `job_employer_email`, `job_employer_name`

---

## 10. Configuration (`config.py`)

| Setting | Description |
|---------|-------------|
| `OLLAMA_MODEL` | `qwen2.5:1.5b` (in ai_processor.py) |
| `OLLAMA_URL` | `http://localhost:11434/api/generate` |
| `VALID_CATEGORIES` | Loaded from `all_jobs_cat.json` (30 broad functional categories) |
| `CATEGORY_KEYWORDS` | Keyword-to-category mapping loaded from `job_categories.json`. Over 3000 keywords in FI and EN. |
| `CITY_KEYWORDS` | All Finnish cities/districts for location detection |
| `UUSIMAA_CITIES` | Capital region cities for regional filtering |
| `MAX_PAGES` | Max scraping pages per site (default: 10) |
| `AI_BATCH_SIZE` | Jobs per AI batch (default: 0 = unlimited) |
| `EXPIRATION_DAYS` | Days before a job expires (default: 30) |
| `GITHUB_PAGES_BASE_URL` | `https://findjobsinfinland.fi` |

---

## 11. Directory Structure

```text
JobsInFinland/
├── ARCHITECTURE.md              # This document
├── index.html                   # Generated home page with job cards
├── jobs.html                    # Consolidated job feed page
├── 404.html                     # Custom error page
├── about-us.html                # Static page
├── contact-us.html              # Static page
├── sitemap-jobs.xml             # Auto-generated job sitemap
├── pipeline.log                 # Full pipeline execution log
│
├── jobs/                        # Generated HTML job pages
│   ├── {category-slug}/         # e.g., software-development/
│   │   └── {job-id}/
│   │       └── index.html       # Individual job page
│   └── ...
│
├── images/
│   └── jobs/
│       └── {category-slug}/     # 1.png through 30.png per category
│
├── css/                         # Stylesheets
├── js/                          # Frontend JavaScript
│
└── scraper/
    ├── run_scraper.py           # Phase 1: Scraper entrypoint
    ├── run_pipeline.py          # Phases 2–5: Pipeline CLI + batch loop
    ├── job_translator.py        # Phase 2: Argos FI→EN translation (offline)
    ├── ai_processor.py          # Phase 3: AI formatting + factual fields
    ├── patch_salary.py          # Phase 3: Centralized salary extraction logic
    ├── translator.py            # deep-translator FI→EN wrapper (Google)
    ├── html_generator.py        # Phase 5: Static site builder
    ├── image_generator.py       # Phase 5: OG image generator
    ├── config.py                # All configuration & category keywords
    ├── jobs_store.py            # jobs.json + formatted_jobs_flat.json I/O
    ├── rawjobs_store.py         # rawjobs.json I/O + AI status tracking
    ├── expiration.py            # Job expiration logic
    ├── firebase_client.py       # Phase 5: Firebase push notifications
    ├── scraper.py               # Shared scraping utilities
    ├── job_template.html        # HTML template for job pages
    ├── all_jobs_cat.json        # Valid category list (source of truth, 30 categories)
    ├── job_categories.json      # Keyword dictionaries for rule-based scoring
    ├── category_post_check.py   # Background AI category verifier (post-batch)
    ├── category_changer.py      # Manual category manager web UI + AI audit tool
    │
    ├── scraper_tyomarkkinatori.py   # Phase 1: Työmarkkinatori module
    ├── scraper_duunitori.py         # Phase 1: Duunitori module
    ├── scraper_jobly.py             # Phase 1: Jobly module
    │
    └── data/
        ├── rawjobs.json                # Phase 1+2: Raw jobs + translated_content
        ├── translated_raw_jobs.json    # Phase 2: Translations snapshot
        ├── formatted_jobs_flat.json    # Phase 3+4: Formatted jobs (flat list)
        ├── jobs.json                   # Phase 3+4: Formatted jobs (session-grouped)
        ├── processing_state.json       # Per-job AI processing state + retry count
        ├── category_changes_log.json   # Audit log: all category changes (manual + AI)
        └── sent_alerts.json            # Phase 5: Firebase alert tracking
```
