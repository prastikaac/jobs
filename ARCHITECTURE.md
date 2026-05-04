# Job Aggregator Architecture

This document outlines the complete architecture, data flow, and functional mechanisms of the Job Aggregator system. The system fetches jobs from multiple Finnish job boards, deduplicates them, translates them using **Google Translate** (via deep-translator, online), formats them using a local AI (**LM Studio / qwen2.5**), and generates static HTML pages for a fast frontend experience.

---

## 1. System Overview

The pipeline operates in a fully automated, scheduled loop, split into **five distinct phases**:

```
┌──────────────┐  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  Phase 1     │─▶│  Phase 2        │─▶│  Phase 3        │─▶│  Phase 4         │─▶│  Phase 5         │
│  SCRAPING    │  │  TRANSLATION    │  │  AI FORMATTING  │  │  JOB FORMATTER   │  │  SITE GENERATION │
│              │  │                 │  │                 │  │                  │  │                  │
│  Duunitori   │  │  Google Trans.  │  │  AI title fix   │  │  Locks factual   │  │  HTML pages      │
│  Työmkturi   │  │  (online, via   │  │  Rule-based cat │  │  fields (Python) │  │  index/jobs.html │
│  Jobly       │  │  deep-trans.)   │  │  LM Studio fmt  │  │  Builds job_id   │  │  sitemap.xml     │
│              │  │                 │  │  structured JSON │  │  slug + URL      │  │  OG images       │
│  →rawjobs    │  │  →translated_   │  │  →translated_   │  │  meta_desc       │  │  Firebase alerts │
│   .json      │  │   raw_jobs.json │  │   raw_jobs.json │  │  →formatted_     │  │  Git commit+push │
└──────────────┘  └─────────────────┘  └─────────────────┘  │   jobs_flat.json │  └──────────────────┘
 run_scraper.py    job_translator.py    ai_processor.py       │  →jobs.json      │  html_generator.py
                                       category_checker.py   └──────────────────┘  image_generator.py
                                                             Job_formatter.py      firebase_client.py
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

**Purpose**: Translate all raw Finnish job text to English using **Google Translate via deep-translator** (online).

**File**: `scraper/job_translator.py`

### How It Works
1. `run_phase2()` is called by the pipeline.
2. Scans all raw jobs for those missing a `translated_content` field.
3. For each untranslated job, concatenates `title + jobcontent` into a single text block.
4. Passes text through `translator.translate_fi_to_en()` — chunked for Google's 4900-char limit.
5. Stores result in `translated_content` field on the raw job.
6. Saves updated `rawjobs.json` and **`translated_raw_jobs.json`** snapshot.

### Key Functions
| Function | Purpose |
|----------|--------|
| `translate_raw_jobs(raw_jobs)` | Translates untranslated jobs, returns updated list |
| `run_phase2(raw_jobs)` | Full Phase 2: translate + save to rawjobs.json + translated_raw_jobs.json |

### Key Design Decisions
- **Online**: Google Translate via deep-translator with chunking (≤4900 chars) and retry/backoff.
- **Cached**: `translated_content` persists across runs — only new/untranslated jobs are processed.
- **Decoupled**: Translation saved independently of AI. AI failure in Phase 3 does not lose translations.
- **Reset**: `--reset-raw` clears both `ai_processed` and `translated_content`, forcing full retranslation.

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

## 4. Phase 3: AI Formatting (`ai_processor.py` + `category_checker.py`)

**Purpose**: Take the pre-translated English text and format it into structured JSON fields using **LM Studio (qwen2.5-3b-instruct)**, combined with Python for factual fields. Factual field locking and final job assembly happens in Phase 4 (`Job_formatter.py`).

**File**: `scraper/ai_processor.py`

### Key Functions
| Function | Purpose |
|----------|--------|
| `format_translated_jobs(raw_jobs, batch_size)` | Phase 3 entry point: format unprocessed jobs |
| `_call_lm_studio_for_content(text, raw_job, category)` | Send translated text to LM Studio for structured extraction |
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
│  _call_lm_studio_for_content()      │
│  LM Studio (qwen2.5-coder-1.5b)     │
│  reads the ALREADY-TRANSLATED       │
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
| **LM Studio** (Phase 3) | **Formatting**: Reads English text, extracts structured fields. Also picks category if string-match fails. |
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
- **AI override via LM Studio**: The background `BatchChecker` thread evaluates the category concurrently with formatting using `determine_category()`. It checks the point-wise score first, then asks LM Studio to suggest the best category. If LM Studio finds a better fit, it overrides the point-wise category in-place.

### Category Post-Check (`category_checker.py`)

The category verifier now runs **concurrently with AI Formatting** using a batch-level `ThreadPoolExecutor`.

```
  Phase 3 starts
  
  ┌────────────────────────────────────────────────────────┐
  │ 1. category_checker.determine_category() is         │
  │    submitted to a ThreadPoolExecutor for ALL jobs in   │
  │    the batch upfront.                                  │
  │                                                        │
  │ 2. Main thread proceeds to format jobs sequentially    │
  │    using _call_lm_studio_for_content().                │
  │                                                        │
  │ 3. Before finalizing a job, the main thread waits for  │
  │    that specific job's category future to complete.    │
  │                                                        │
  │ 4. Merges final category into formatted data.          │
  └────────────────────────────────────────────────────────┘
         │
         ▼
    Returns fully formatted job batch
```

**Key properties:**
- Category checks run in the background for the entire batch simultaneously while the AI processor works.
- By the time the main thread finishes the heavy AI extraction for a job, its category check is usually already completed and waiting.
- Logs to `scraper/category_checker.log` (dedicated file, INFO level)
- Silently skips if LM Studio is offline — pipeline unaffected
- Thread-safe: `_file_lock` prevents concurrent JSON/HTML corruption
- Source tagged `"pipeline_post_check"` in `category_changes_log.json`

### Hallucination Detection
- `_is_irrelevant_ai_output()` checks if AI output has meaningful overlap with the original job title/content.
- Known hallucination words trigger rejection.
- Rejected AI output → fallback to Python extraction + Argos.

---

## 5. Phase 4: Job Formatter (`Job_formatter.py`)

**Purpose**: Take AI-formatted job data and produce the final clean job object with locked factual fields, slugged URLs, and sanitized lists.

- **`format_jobs(jobs)`**: Main entry point. Calls `_build_formatted_job()` per job.
- **`_build_formatted_job(raw, ai_data)`**: Builds the full job schema — locks company, location (via municipality code lookup), salary, links, dates. Generates `job_id` slug (`title-slug + loc-slug + hash`).
- **`apply_manual_fixes(job)`**: Post-processing — title/company casing, image URL correction, meta description truncation.
- **`sanitize_ai_output()`**: Validates AI list fields, fills gaps from raw content, enforces minimum 3 items per list.
- **Municipality Code Resolver**: Converts numeric codes (e.g. `"091"`) to city names using `municipalities_codes.json`.
- **Region Resolver**: Maps codes to `MAAKUNTANIMIFI` region names for `jobRegions` field.

---

## 6. Phase 5: Site Generation

### 6.1 HTML Generation (`html_generator.py`)
- **Job Pages**: Compiles `job_template.html` into individual `/jobs/{category-slug}/{job-id}/index.html` pages.
- **Index Pages**: Updates `index.html` and `jobs.html` with job cards.
- **Sitemap**: Updates `sitemap-jobs.xml` with all active job URLs.
- **Dynamic Apply Links**: If `jobapply_link` is a `mailto:`, generates a pre-filled email template with subject and body.
- **Location Attributes**: Extracts and slugifies location data for `data-location` attributes, with regional and national context.
- **Recruiter Info**: Renders employer name, email, and phone on job pages with conditional display.

### 6.2 Image Generation (`image_generator.py`)
- Generates category-specific OG/meta images for social media sharing.
- Uses category-keyed image folders under `/images/jobs/{category-slug}/`.

### 6.3 Firebase Alerts (`firebase_client.py`)
- Sends push notifications for new job listings to subscribed users.
- Tracks sent alerts in `sent_alerts.json` to prevent duplicates.
- Uses Firebase Admin SDK with `serviceAccountKey.json`.

---

## 7. Data Stores

| File | Purpose | Written By |
|------|---------|------------|
| `rawjobs.json` | Raw Finnish jobs + `translated_content` | Phase 1 + Phase 2 |
| `translated_raw_jobs.json` | Raw jobs with translations + AI-formatted fields | Phase 2 (translations), Phase 3 (AI fields) |
| `processing_state.json` | Per-job state: translated, ai_processed, retry_count | Phase 2 + Phase 3 |
| `formatted_jobs_flat.json` | Final formatted jobs — flat list | Phase 4 (`Job_formatter.py`) |
| `jobs.json` | Final formatted jobs — session-grouped | Phase 4 (`Job_formatter.py`) |
| `sent_alerts.json` | Job IDs that have had Firebase alerts sent | Phase 5 (`firebase_client.py`) |

---

## 8. Pipeline Orchestration (`run_pipeline.py`)

### Execution Flow
```
1. Load stores (rawjobs.json, processing_state.json, formatted_jobs_flat.json)
2. Reset if --reset-raw (clears ai_processed + translated_content)
3. Sync category directories (underscore → hyphen)
4. Expire old jobs (> EXPIRATION_DAYS = 60 days)
───────────────────────────────────
5. PHASE 2: job_translator.run_phase2()  [skipped with --ai-only or --format-only]
   → Google Translate untranslated raw jobs
   → Save rawjobs.json + translated_raw_jobs.json
───────────────────────────────────
6. Batched loop (25 jobs/batch — PIPELINE_COMMIT_BATCH_SIZE) [skipped with --format-only]

   a. PHASE 3: ai_processor.format_translated_jobs(chunk)
      → category_checker.determine_category() runs in background ThreadPool:
          Step 0: format_job_title_with_ai() — LM Studio generates clean English title
          Step 1: detect_category_by_keywords() — rule-based scoring
          Step 2: LM Studio confirms or overrides the category
      → Main thread calls _call_lm_studio_for_content() per job (structures description + lists)
      → Waits for category future before finalizing each job

   b. PHASE 4: Job_formatter.format_jobs()
      → sanitize_ai_output() validates and fills AI list fields
      → _build_formatted_job() assembles final job schema
      → Locks: company, location (municipality codes), salary, links, dates
      → Generates job_id slug + jobUrl + image_url
      → apply_manual_fixes() — casing, URL, meta_description

   c. PHASE 5: Site generation
      → generate_images_for_jobs() — category stock images
      → generate_job_pages()       — /jobs/{cat-slug}/{job-id}/index.html
      → update_main_pages()        — index.html, jobs.html
      → update_sitemap()           — sitemap-jobs.xml
      → save_formatted_jobs_flat() — formatted_jobs_flat.json
      → save_jobs()                — jobs.json
      → send_new_job_alerts()      — Firebase push notifications
      → Git commit + push          — live site updated on GitHub Pages
```

### CLI Resume Commands (run from project root)
| Command | Resumes From | Runs |
|---------|-------------|------|
| `python scraper/run_pipeline.py` | After Phase 1 (Scraping) | Phase 2+3+4+5 |
| `python scraper/run_pipeline.py --ai-only` | After Phase 2 (Translation) | Phase 3+4+5 |
| `python scraper/run_pipeline.py --format-only` | After Phase 3 (AI Formatting) | Phase 4+5 |
| `python scraper/run_pipeline.py --html-only` | Force Phase 5 only | Phase 5 only |

### All CLI Flags
| Flag | Description |
|------|-------------|
| *(no flags)* | Full pipeline: Phase 2→3→4→5 |
| `--ai-only` | Skip Phase 2, resume from Phase 3 (AI already translated) |
| `--format-only` | Skip Phase 2+3, run Phase 4+5 on AI-processed jobs |
| `--html-only` | Phase 5 only: regenerate HTML from formatted_jobs_flat.json |
| `--dry-run` | No disk writes, no AI/translation calls |
| `--reset-raw` | Reset all raw jobs to untranslated/unprocessed, then run |
| `--reset` | Clear everything — reset raw + empty output stores |
| `--fix-dates` | Fix title casing + Finnish date formats, regenerate HTML |
| `--migrate` | One-time migration for category/date/salary/URL fixes |
| `--patch-titles` | Replace known Finnish titles with English equivalents |
| `--check-expires` | Print expiry stats for last 5 jobs |
| `--check-db` | Print Firebase document count + first 10 IDs |
| `--schedule` | Run pipeline now, then repeat every 1 hour (blocking) |

---

## 9. Translation Layer (`translator.py`)

- Wraps `deep-translator` for Finnish → English translation over **Google Translate** (online).
- Handles chunking for strings larger than **4900 characters** due to Google limits.
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

| Setting | Value / Description |
|---------|--------------------|
| `LM_STUDIO_MODEL` (category_checker) | `qwen2.5-3b-instruct` |
| `LM_STUDIO_URL` | `http://localhost:1234/v1/chat/completions` |
| `VALID_CATEGORIES` | Loaded from `all_jobs_cat.json` (30 broad functional categories) |
| `CATEGORY_KEYWORDS` | Loaded from `job_categories.json` — 3000+ keywords (FI + EN) |
| `MAX_PAGES` | Max scraping pages per site (default: 10) |
| `AI_BATCH_SIZE` | Jobs per AI batch (default: 0 = unlimited) |
| `PIPELINE_COMMIT_BATCH_SIZE` | Git commit+push every N processed jobs (default: 25) |
| `EXPIRATION_DAYS` | Days before a job expires (default: **60**) |
| `AI_MAX_RETRIES` | Max AI retries per job (default: 3) |
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
    ├── run_pipeline.py          # Phases 2–5: Pipeline CLI + batch loop (--ai-only, --format-only, --html-only)
    ├── job_translator.py        # Phase 2: Google Translate FI→EN (online, deep-translator)
    ├── ai_processor.py          # Phase 3: LM Studio AI content formatting
    ├── Job_formatter.py         # Phase 4: Final job assembly, factual field locking, slug generation
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
    ├── category_checker.py      # Phase 3: AI title formatter + rule-based + LM Studio category check
    ├── offline_manual_category_changer.py  # Manual category manager (offline UI)
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
