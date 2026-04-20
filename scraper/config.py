"""
config.py — Scraper + pipeline configuration.
"""

import json
import os
import re
from dotenv import load_dotenv

load_dotenv()

# ── Firebase ──────────────────────────────────────────────────────────────────
FIREBASE_CREDENTIALS_PATH = os.getenv("FIREBASE_CREDENTIALS_PATH", "serviceAccountKey.json")
FIREBASE_ALERT_COLLECTION = "jobs"

# ── Static website paths ──────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WEBSITE_DIR = BASE_DIR
DATA_DIR = os.path.join(BASE_DIR, "scraper", "data")

# Core data stores
RAWJOBS_JSON_PATH = os.path.join(DATA_DIR, "rawjobs.json")
TRANSLATED_RAW_JOBS_JSON_PATH = os.path.join(DATA_DIR, "translated_raw_jobs.json")
FORMATTED_JOBS_FLAT_JSON_PATH = os.path.join(DATA_DIR, "formatted_jobs_flat.json")
JOBS_JSON_PATH = os.path.join(DATA_DIR, "jobs.json")
PROCESSING_STATE_JSON_PATH = os.path.join(DATA_DIR, "processing_state.json")
SENT_ALERTS_PATH = os.path.join(DATA_DIR, "sent_alerts.json")

# Legacy compatibility alias
TRANSLATED_JOBS_JSON_PATH = TRANSLATED_RAW_JOBS_JSON_PATH

JOBS_OUTPUT_DIR = os.path.join(BASE_DIR, "jobs")
IMAGES_JOBS_DIR = os.path.join(WEBSITE_DIR, "images", "jobs")

# ── Categories ────────────────────────────────────────────────────────────────
_ALL_JOBS_CAT_JSON = os.path.join(os.path.dirname(__file__), "all_jobs_cat.json")

VALID_CATEGORIES = []
if os.path.exists(_ALL_JOBS_CAT_JSON):
    with open(_ALL_JOBS_CAT_JSON, "r", encoding="utf-8-sig") as _f:
        VALID_CATEGORIES = json.load(_f).get("categories", [])
else:
    VALID_CATEGORIES = ["other"]


def slugify_category(cat: str) -> str:
    """Standardized slugification for category folders and URLs."""
    f = str(cat).lower().strip()
    f = f.replace("&", "and")
    f = f.replace("/", " ")
    f = f.replace("_", "-")
    f = re.sub(r"[^a-z0-9\s-]", "", f)
    f = f.replace(" ", "-")
    f = re.sub(r"-+", "-", f)
    return f.strip("-")


def get_safe_category_slug(cat: str) -> str:
    """Returns slug if folder exists in images/jobs, else 'other'."""
    slug = slugify_category(cat)
    folder_path = os.path.join(IMAGES_JOBS_DIR, slug)
    if os.path.exists(folder_path):
        return slug
    return "other"


# ── GitHub Pages ──────────────────────────────────────────────────────────────
GITHUB_PAGES_BASE_URL = os.getenv(
    "GITHUB_PAGES_BASE_URL",
    "https://findjobsinfinland.fi"
)

# ── Job lifecycle ─────────────────────────────────────────────────────────────
EXPIRATION_DAYS = int(os.getenv("EXPIRATION_DAYS", "60"))

# ── Scraping target ───────────────────────────────────────────────────────────
BASE_URL = "https://duunitori.fi"
SEARCH_URL = "https://duunitori.fi/tyopaikat"

SEARCH_PARAMS = {
    # "haku": "cleaner",
    # "alue": "helsinki",
}

MAX_PAGES = int(os.getenv("MAX_PAGES", "10"))
AI_BATCH_SIZE = int(os.getenv("AI_BATCH_SIZE", "0"))  # 0 = unlimited (process all pending jobs)
PIPELINE_COMMIT_BATCH_SIZE = int(os.getenv("PIPELINE_COMMIT_BATCH_SIZE", "25"))  # commit+push every N AI-processed jobs
REQUEST_DELAY_SECONDS = float(os.getenv("REQUEST_DELAY_SECONDS", "2.0"))
DETAIL_DELAY_SECONDS = float(os.getenv("DETAIL_DELAY_SECONDS", "1.5"))

# ── Pipeline state / retry settings ───────────────────────────────────────────
AI_MAX_RETRIES = int(os.getenv("AI_MAX_RETRIES", "3"))
AI_CATEGORY_CANDIDATE_COUNT = int(os.getenv("AI_CATEGORY_CANDIDATE_COUNT", "5"))
PROCESSING_STATE_VERSION = 1

# ── HTTP headers ──────────────────────────────────────────────────────────────
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fi-FI,fi;q=0.9,en;q=0.8",
}

# ── CATEGORY KEYWORDS (loaded from job_categories.json) ──────────────────────
_JOB_CATEGORIES_JSON = os.path.join(os.path.dirname(__file__), "job_categories.json")
CATEGORY_KEYWORDS: dict[str, list[str]] = {}
if os.path.exists(_JOB_CATEGORIES_JSON):
    with open(_JOB_CATEGORIES_JSON, "r", encoding="utf-8-sig") as _f:
        _raw = json.load(_f)

    _valid_set = set(VALID_CATEGORIES) | {"other"}
    CATEGORY_KEYWORDS = {
        cat.lstrip("\ufeff"): kws for cat, kws in _raw.items()
        if cat.lstrip("\ufeff") in _valid_set
    }
else:
    CATEGORY_KEYWORDS = {
        "other": [],
    }