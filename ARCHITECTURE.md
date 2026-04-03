# Job Aggregator Architecture

This document outlines the complete architecture, data flow, and functional mechanisms of the Job Aggregator system. The system fetches jobs from multiple Finnish job boards, deduplicates them, translates them using an offline translation model (Argos), formats them using a local AI (Ollama), and generates static HTML pages for a fast frontend experience.

---

## 1. System Overview

The pipeline operates in a fully automated, scheduled loop, split into **four distinct phases**:

```
┌───────────────┐   ┌───────────────────┐   ┌───────────────────┐   ┌────────────────────┐
│  Phase 1      │──▶│  Phase 2          │──▶│  Phase 3          │──▶│  Phase 4           │
│  SCRAPING     │   │  TRANSLATION      │   │  AI FORMATTING    │   │  SITE GENERATION   │
│               │   │                   │   │                   │   │                    │
│  Duunitori    │   │  Argos FI→EN      │   │  Ollama formats   │   │  HTML pages        │
│  Työmkturi    │   │  (offline model)  │   │  structured JSON  │   │  index/jobs.html   │
│  Jobly        │   │                   │   │  Python locks     │   │  sitemap-jobs.xml  │
│               │   │  Translates:      │   │  factual fields   │   │  OG images         │
│  → rawjobs    │   │  title+jobcontent │   │  Finnish sweep    │   │  Firebase alerts   │
│    .json      │   │  → translated_    │   │  → jobs.json      │   │                    │
│               │   │    content field  │   │  → translated_    │   │                    │
│               │   │  → translated_    │   │    jobs.json      │   │                    │
│               │   │    jobs.json      │   │    (overwritten)  │   │                    │
└───────────────┘   └───────────────────┘   └───────────────────┘   └────────────────────┘
 run_scraper.py      job_translator.py        ai_processor.py         html_generator.py
                     translate_raw_jobs()     format_translated_      image_generator.py
                     run_phase2()             jobs()                  firebase_client.py
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

**Purpose**: Translate all raw Finnish job text to English using the offline Argos model. This phase runs completely offline with no network calls.

**File**: `scraper/job_translator.py`

### How It Works
1. `run_phase2()` is called by the pipeline.
2. Scans all raw jobs for those missing a `translated_content` field.
3. For each untranslated job, concatenates `title + jobcontent` into a single text block.
4. Passes the text through `translator.translate_fi_to_en()` (ArgosTranslate FI→EN model).
5. Stores the result in the `translated_content` field on the raw job.
6. Saves the updated `rawjobs.json` (with translations cached).
7. **Saves `translated_jobs.json`** — a snapshot of the raw jobs with their translations, available for inspection before Phase 3.

### Key Functions
| Function | Purpose |
|----------|--------|
| `translate_raw_jobs(raw_jobs)` | Translates untranslated jobs, returns updated list |
| `run_phase2(raw_jobs)` | Full Phase 2: translate + save to rawjobs.json + translated_jobs.json |

### Key Design Decisions
- **Offline**: No network required. ArgosTranslate runs locally.
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
| `_call_ollama_for_category(context)` | AI picks best category (fallback when string-match fails) |
| `_build_formatted_job(raw, ai_data)` | Merge AI output with Python factual fields |
| `_build_fallback_ai_data(raw, category)` | Fallback when AI fails: Python extraction + Argos |
| `apply_manual_fixes(job)` | Post-processing: salary normalization, Finnish sweep |
| `_sweep_finnish_from_job(job)` | Final safety net: catch remaining Finnish, retranslate |

### Pipeline Per Job

```
Pre-translated English text (from Phase 2)
      │
      ▼
┌─────────────────────────────────────┐
│  Step 1: CATEGORY DETECTION         │
│  a) Score translated text & title   │
│     using job_categories.json.      │
│     Requires >= 2 distinct keywords │
│     or score >= 8 (e.g., exact or   │
│     partial title match) to win.    │
│  b) If rule-based scoring yields    │
│     no clear winner ("other"),      │
│     AI picks a category from the    │
│     top matched candidates or the   │
│     all_jobs_cat.json allowed list. │
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
│  - description (1 paragraph, ≤500c) │
│  - meta_description (SEO, ≤160c)    │
│  - job_responsibilities [2-4 items] │
│  - what_we_expect [2-4 items]       │
│  - what_we_offer [2-4 items]        │
│  - who_is_this_for [2-4 items]      │
│  - search_keywords (5-8 keywords)   │
│                                     │
│  AI does NOT translate — only       │
│  formats already-English text.      │
│                                     │
│  If AI fails → _build_fallback_     │
│  ai_data() uses Python extraction   │
│  + Argos translation as fallback.   │
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
│  Argos automatically.               │
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
         → translated_jobs.json (flat list)
```

### Who Does What

| Component | Responsibility |
|-----------|---------------|
| **Argos** (Phase 2) | **Translation**: Finnish → English. Runs offline, cached in `translated_content`. |
| **Ollama** (Phase 3) | **Formatting**: Reads English text, extracts structured fields. Also picks category if string-match fails. |
| **Python** (Phase 3) | **Factual fields**: Company, location, salary, links, dates. Never delegated to AI. |
| **`_sweep_finnish_from_job()`** | **Safety net**: Catches any remaining Finnish after AI formatting and retranslates via Argos. |

### Salary Normalization
- Managed centrally by `patch_salary.py`:
  - Contains extensive regex mapping and rules.
  - Finnish collective agreement phrases (`TES`, `OVTES`, `työehtosopimus`, etc.) → normalized to: `"Competitive hourly wage based on Finnish collective agreements."`
  - Numeric salaries with `€` are kept as-is.
  - Integrated into Phase 3 processing.

### Category Classification Engine
- **Source of Truth**: 30 broad, predefined categories in `all_jobs_cat.json`.
- **Keyword Dictionary**: Populated dynamically from `job_categories.json`. Only keywords for categories present in `all_jobs_cat.json` are loaded.
- **Rule-Based Engine**: Jobs strictly require either `≥ 2` distinct keyword matches OR a base score `≥ 8` (achieved by an exact/partial job title match) to be confidently categorized.
- **AI Tie-Breaker Fallback**: If the rule-based engine scores 0 or fails to identify a clear winner, the local AI model selects the best fit from the 30 broad categories.
- Unrecognized or generic jobs default to `"other"`.

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
   → Argos translate untranslated raw jobs
   → Save rawjobs.json (with translated_content)
   → Save translated_jobs.json (raw + translations)
───────────────────────────────────
6. PHASE 3: ai_processor.format_translated_jobs()
   → AI formats using pre-translated text
   → Merge into jobs list
   → Apply manual fixes (salary, Finnish sweep)
───────────────────────────────────
7. PHASE 4: Site generation
   → Generate images, HTML pages, update indexes
   → Send Firebase alerts for new jobs
   → Save jobs.json + translated_jobs.json (final formatted)
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

- Wraps `argostranslate` for offline Finnish → English translation.
- Loads the FI→EN language model once, caches it for subsequent calls.
- Falls back silently to original text if model is missing or translation fails.
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
| `AI_BATCH_SIZE` | Jobs per AI batch (default: 10) |
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
    ├── run_pipeline.py          # Phases 2, 3 & 4: Pipeline CLI
    ├── job_translator.py        # Phase 2: Argos FI→EN translation
    ├── ai_processor.py          # Phase 3: AI formatting + factual fields
    ├── patch_salary.py          # Phase 3: Centralized salary extraction logic
    ├── translator.py            # ArgosTranslate FI→EN wrapper
    ├── html_generator.py        # Phase 4: Static site builder
    ├── image_generator.py       # Phase 4: OG image generator
    ├── config.py                # All configuration & category keywords
    ├── jobs_store.py            # jobs.json + translated_jobs.json I/O
    ├── rawjobs_store.py         # rawjobs.json I/O + AI status tracking
    ├── expiration.py            # Job expiration logic
    ├── firebase_client.py       # Phase 4: Firebase push notifications
    ├── scraper.py               # Shared scraping utilities
    ├── job_template.html        # HTML template for job pages
    ├── all_jobs_cat.json        # Valid category list data (source of truth)
    ├── job_categories.json      # Keyword dictionaries for scoring
    │
    ├── scraper_tyomarkkinatori.py   # Phase 1: Työmarkkinatori module
    ├── scraper_duunitori.py         # Phase 1: Duunitori module
    ├── scraper_jobly.py             # Phase 1: Jobly module
    │
    └── data/
        ├── rawjobs.json             # Phase 1+2: Raw jobs + translated_content
        ├── translated_jobs.json     # Phase 2: Translations → Phase 3: Formatted jobs
        ├── jobs.json                # Phase 3: Formatted jobs (session-grouped)
        └── sent_alerts.json         # Phase 4: Firebase alert tracking
```
