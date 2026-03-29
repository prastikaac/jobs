# Job Aggregator Architecture

This document outlines the complete architecture, data flow, and functional mechanisms of the Job Aggregator system. The system fetches jobs from multiple Finnish job boards, deduplicates them, enriches and translates them using a local AI (Ollama), and generates static HTML pages for a fast frontend experience.

## 1. System Overview

The pipeline operates in a fully automated, scheduled loop, conceptually split into three main phases:
- **Phase 1 (Scraping):** Sequential fetching of raw job listings from independent modules into `scraper/data/rawjobs.json`.
- **Phase 2 (AI Processing):** Using a local LLM (`qwen2.5:3b`) to map, translate (Finnish to English), and structure job descriptions into discrete, high-quality JSON fields. 
- **Phase 3 (Site Generation & Notifications):** Building static HTML index pages and individual job listings, generating social media images, and triggering Firebase alerts for new jobs.

The entire process is automated via **Windows Task Scheduler**, running at specific intervals (10:00 AM, 1:30 PM, 5:00 PM), ensuring fresh data seamlessly flows onto the live site.

---

## 2. Scraping Phase (`run_scraper.py`)

Scraping is orchestrated by `scraper/run_scraper.py`, leveraging a centralized `DeduplicationState` memory store to prevent duplicate job entries across runs and modules.

### Data Flow
1. **Load State**: `run_scraper.py` loads existing entries from `scraper/data/rawjobs.json` and builds a `DeduplicationState` (tracking IDs, titles/companies/locations, and apply URLs) to filter out duplicates dynamically.
2. **Execute Modules**: Runs highly specialized, isolated scraper modules:
   - **`scraper_tyomarkkinatori.py`**: Fetches details directly via their JSON API.
   - **`scraper_duunitori.py`**: Parses list pagination and details via HTML.
   - **`scraper_jobly.py`**: Parses XML sitemaps and extracts JSON-LD structured data (using `cloudscraper` to bypass Cloudflare).
3. **Persist**: All newly gathered, verified unique jobs are appended to `scraper/data/rawjobs.json` with a flag `processed: false`.

---

## 3. Processing & AI Translation (`run_pipeline.py`)

The pipeline orchestrator (`scraper/run_pipeline.py`) unifies data transformation, HTML generation, and previous standalone utilities into one command structure.

### 3.1 Synchronizing & Categorizing
- **Data Sync**: Reads from `rawjobs.json`. Unprocessed jobs are queued for AI enrichment.
- **Hyphenated Slugs**: Job categories are mapped to web-safe hyphenated slugs (e.g., `sales-and-marketing`).
- **Fallback Logic**: Jobs with unrecognized categories are smoothly gracefully mapped to the `"other"` fallback category folder to maintain valid image linking and routing.

### 3.2 Ollama AI Formatting (`ai_processor.py`)
- Untranslated jobs are sent to a local Ollama instance running `qwen2.5:3b` in structural batches.
- **Translation & Structuring**: The AI breaks down raw job text into distinct, translated English fields: `experience` (formatted strictly as an array list), `description` (4-6 detailed sentences), `what_we_expect`, `job_responsibilities`, `what_we_offer`, and `who_is_this_for`.
- **Constraint Safety**: Important fields like `company` remain "sticky" and are safeguarded from being hallucinated by the LLM if they already exist in the raw data. 

---

## 4. Frontend & Site Generation

Once the data is normalized and AI-processed into `scraper/data/jobs.json`, Phase 3 builds the static assets.

### 4.1 HTML Generation (`html_generator.py`)
- **Indexes**: Generates `index.html`, dynamically segmented by category.
- **Job Templates**: Compiles the `job_template.html` into individual `/jobs/{category}/{id}/index.html` entries.
- **Dynamic Apply Linking**: Directly embeds Application URLs. If missing, automatically constructs a `mailto:` fallback based on parsed emails.
- **Frontend Filtering & SEO**: Extracts and slugifies location data from the JSON context to generate precise `data-location` attributes. Locations are automatically expanded with regional (e.g., `uusimaa`) and national (`finland`) contexts so frontend filtering tags remain robust. Prevents stale URL query params from persisting visually.

### 4.2 Supporting Assets
- **`image_generator.py`**: Composes category-specific meta/OG images so social sharing visually pops.
- **Firebase Alerts**: Triggers push notifications to subscribed users upon discovering new listings.

---

## 5. Centralized Utilities (`run_pipeline.py`)

`run_pipeline.py` serves as the swiss army knife for repository management, absorbing standalone commands:
- `--dry-run`: Tests parser updates without executing disk writes.
- `--reset-raw`: Resets status flags to rerun all jobs through the AI from scratch.
- `--fix-dates` & `--patch-titles`: Idempotently standardizes formats.
- `--migrate`: Handles one-time codebase shifts (slug logic updates, categorization patches).
- `--schedule`: Built-in application loop for headless background executions.

---

## 6. Full Directory Map

```text
JobsInFinland/
├── ARCHITECTURE.md
├── index.html                     # Generated Home Page
├── jobs.html                      # Consolidated Job Feed
├── to-do.txt
│
├── jobs/                          # Generated HTML Site content
│   ├── {hyphenated-category}/     # Category indexes & Job sub-folders
│   └── ...
│
└── scraper/
    ├── run_scraper.py             # Phase 1: Aggregator entrypoint
    ├── run_pipeline.py            # Phase 2 & 3: AI Processor & Site Gen CLI
    ├── ai_processor.py            # Local Ollama LLM integration
    ├── html_generator.py          # Static site parsing & compilation
    ├── image_generator.py         # Social image automation
    ├── config.py                  # Globals (Categories, Firebase, Regions)
    ├── firebase_client.py         # Push notifications integration
    │
    ├── scraper_tyomarkkinatori.py # Työmarkkinatori Module
    ├── scraper_duunitori.py       # Duunitori Module 
    ├── scraper_jobly.py           # Jobly Module
    │
    └── data/
        ├── rawjobs.json           # Raw JSON straight from the scrapers
        └── jobs.json              # AI-Processed clean output for the site
```
