# Job Aggregator Architecture

This document outlines the architecture and data flow of the Job Aggregator system. The system fetches jobs from multiple Finnish job boards, normalizes them, enriches them using AI, and generates static HTML pages.

## 1. System Overview

The pipeline is split into two main logical phases:
- **Phase 1 (Scraping):** Fetching raw job listings from external sources to `data/rawjobs.json`.
- **Phase 2 (Processing & Generation):** AI translation, categorization, and HTML site generation into `data/jobs.json` and the frontend display.

---

## 2. Scraping Phase (`run_scraper.py`)

The scraping phase is orchestrated by `scraper/run_scraper.py`. It uses a shared `DeduplicationState` to prevent duplicates from being saved across the three independent modules.

Each site has its own isolated scraper module that normalizes data to a common schema.

### Data Flow
1. **`run_scraper.py`** loads existing jobs from `rawjobs.json` to build the `DeduplicationState` (tracking seen IDs, hashes, and links).
2. It executes **`scraper_tyomarkkinatori.py`** (API JSON search & detail fetching).
3. It executes **`scraper_duunitori.py`** (HTML pagination & detail parsing).
4. It executes **`scraper_jobly.py`** (XML sitemap parsing + JSON-LD extraction via `cloudscraper`).
5. All new, deduplicated jobs are appended to `data/rawjobs.json`.

---

## 3. Processing & Generation Phase (`run_pipeline.py`)

The processing phase is orchestrated by `scraper/run_pipeline.py`. It picks up where the scraper left off by reading `rawjobs.json` and applying the AI steps.

### Data Flow
1. **Synchronization (`rawjobs_store.py`)**: `run_pipeline.py` compares `rawjobs.json` against the processed `jobs.json` to find jobs that require AI translation.
2. **AI Translation (`ai_processor.py`)**: Batches of untranslated jobs are sent to a local LLM (Ollama) to translate Finnish descriptions into structured English fields (e.g., `experience`, `job_responsibilities`, `what_we_offer`).
3. **Storage**: The fully enriched jobs are saved to `data/jobs.json`.
4. **Site Generation (`html_generator.py` / `generator_core.py`)**: 
   - Generates the `index.html` homepage.
   - Categorizes jobs and generates heavily structured category index pages.
   - Generates individual `job.html` templates for each listing, parsing out direct application URLs or mapping fallback `mailto:` links if only an email was provided.

---

## 4. Directory Structure

```text
Job Scraping/
├── scraper/
│   ├── run_scraper.py             # Entrypoint for Phase 1 (Scraping)
│   ├── run_pipeline.py            # Entrypoint for Phase 2 (Processing/Generating)
│   │
│   ├── scraper_tyomarkkinatori.py # Työmarkkinatori Module
│   ├── scraper_duunitori.py       # Duunitori Module 
│   ├── scraper_jobly.py           # Jobly Module
│   ├── scraper.py                 # Shared scraper utilities (e.g., fetch_with_retry)
│   │
│   ├── ai_processor.py            # Local LLM integration (Ollama)
│   ├── html_generator.py          # Static site parsing & HTML generation
│   ├── generator_core.py          # Category/index compilation routes
│   └── rawjobs_store.py           # JSON disk synchronization
│
├── data/
│   ├── rawjobs.json               # Raw JSON fetched directly from sites
│   └── jobs.json                  # AI structured JSON ready for the frontend
│
└── jobs/                          # Generated frontend HTML site
    ├── index.html                 # Main Homepage
    ├── {category}/                # Category subdirectories
    └── details/                   # Individual job HTML files
```

## 5. Fallback Mechanisms & Resiliency
- **Retries**: Network events are wrapped in `fetch_with_retry` (exponential backoff) to handle timeouts.
- **Bot Protection**: `cloudscraper` is utilized for Jobly to bypass Cloudflare gracefully.
- **Application URL Fallbacks**: If a job site provides no direct "Apply URL", the system regex-extracts an employer email and constructs a `mailto:` button with dynamically appended application instructions directly onto the generated job view.
