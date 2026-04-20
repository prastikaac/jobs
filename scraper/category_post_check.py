"""
category_post_check.py — Background category verifier for the scraping pipeline.

Triggered after each AI-processed batch in run_pipeline.py.
Runs in a daemon thread so it NEVER blocks the main pipeline.

What it does (per job in the batch):
  1. Asks Ollama: "Is this category correct? If not, return the right one."
  2. If a better category is found → patches jobs.json, formatted_jobs_flat.json,
     the HTML file, and jobs-table.html (same logic as category_changer.py).
  3. After processing all jobs in the batch, does a single batched git commit + push.

If Ollama is offline the whole checker silently exits — pipeline is unaffected.
"""

import datetime
import json
import logging
import random
import re
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

logger = logging.getLogger("cat_post_check")

# ── Paths (mirror category_changer.py) ────────────────────────────────────────
_SCRAPER_DIR = Path(__file__).parent
_ROOT_DIR    = _SCRAPER_DIR.parent
_DATA_DIR    = _SCRAPER_DIR / "data"

JOBS_JSON       = _DATA_DIR / "jobs.json"
FLAT_JSON       = _DATA_DIR / "formatted_jobs_flat.json"
CAT_JSON        = _SCRAPER_DIR / "all_jobs_cat.json"
JOBS_DIR        = _ROOT_DIR / "jobs"
JOBS_TABLE      = _ROOT_DIR / "jobs-table.html"
CHANGES_LOG     = _DATA_DIR / "category_changes_log.json"

SITE_BASE       = "https://findjobsinfinland.fi"
OLLAMA_BASE_URL = "http://localhost:11434"

PREFERRED_MODELS = [
    "llama3.1", "llama3.2", "llama3", "llama3:8b",
    "gemma3", "gemma2", "mistral", "phi3", "phi",
]

# One global lock so parallel batches never corrupt files simultaneously
_file_lock = threading.Lock()

# ── Ollama helpers ─────────────────────────────────────────────────────────────

def _ollama_get(path: str):
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE_URL}{path}")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def _detect_best_model() -> str | None:
    resp = _ollama_get("/api/tags")
    if resp is None:
        return None
    models = resp.get("models", [])
    if not models:
        return None
    available = [m["name"].split(":")[0] for m in models]
    for pref in PREFERRED_MODELS:
        for avail in available:
            if avail.lower().startswith(pref.lower()):
                return next(
                    m["name"] for m in models
                    if m["name"].split(":")[0].lower() == avail.lower()
                )
    return models[0]["name"]


_PROMPT_TMPL = """\
You are a precise job classification engine. Output ONE word only.

TASK:
Decide the best category for this job from the VALID CATEGORIES list.
If the CURRENT CATEGORY is already the best match, output exactly: CORRECT
Otherwise output ONLY the correct slug (e.g. healthcare).

Do NOT explain. Do NOT add punctuation. Output one word or CORRECT.

---
Job Title       : {title}
Company         : {company}
Job Description : {description}
Current Category: {current_cat}

VALID CATEGORIES:
{cat_list}
---
Your answer:"""


def _ask_ollama(model: str, title: str, company: str, description: str,
                current_cat: str, valid_cats: list[str]) -> str | None:
    """
    Returns the corrected category slug, or None if the current is correct/unknown.
    """
    cat_list = "\n".join(f"  - {c}" for c in valid_cats)
    prompt   = _PROMPT_TMPL.format(
        title=title,
        company=company,
        description=(description or "")[:500],
        current_cat=current_cat,
        cat_list=cat_list,
    )
    payload = json.dumps({
        "model":   model,
        "prompt":  prompt,
        "stream":  False,
        "options": {"temperature": 0.0, "num_predict": 64},
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/generate",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read())
        raw = data.get("response", "").strip().lower().split()[0] if data.get("response", "").strip() else ""
        raw = re.sub(r"[^a-z0-9\-]", "", raw)
    except Exception as exc:
        logger.warning("[cat_check] Ollama error for '%s': %s", title, exc)
        return None

    if raw == "correct" or not raw:
        return None
    if raw in valid_cats:
        return raw
    # fuzzy fallback
    for vc in valid_cats:
        if raw in vc or vc in raw:
            return vc
    logger.debug("[cat_check] Unknown category '%s' for '%s' — ignoring.", raw, title)
    return None


# ── File helpers ───────────────────────────────────────────────────────────────

def _load_json(path: Path):
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: Path, data) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _save_jobs_json(path: Path, jobs_raw: list) -> None:
    json_str = json.dumps(jobs_raw, ensure_ascii=False, indent=2)
    json_str = json_str.replace("  },\n  {", "  },\n\n  {")
    with open(path, "w", encoding="utf-8") as f:
        f.write(json_str)


def _flat_jobs(data: list) -> list:
    flat = []
    for item in data:
        if isinstance(item, dict) and "jobs" in item:
            flat.extend(item["jobs"])
        elif isinstance(item, dict):
            flat.append(item)
    return flat


def _fmt_cat(slug: str) -> str:
    return slug.replace("-", " ").title()


def _pick_image(new_category: str, old_image_url: str) -> str:
    img_dir = _ROOT_DIR / "images" / "jobs" / new_category
    if img_dir.exists():
        pngs = [p.name for p in img_dir.iterdir() if p.suffix.lower() == ".png"]
        if pngs:
            return f"{SITE_BASE}/images/jobs/{new_category}/{random.choice(pngs)}"
    return old_image_url


def _append_change_log(entry: dict) -> None:
    log = []
    if CHANGES_LOG.exists():
        try:
            with open(CHANGES_LOG, "r", encoding="utf-8") as f:
                log = json.load(f)
        except Exception:
            log = []
    entry.setdefault("timestamp", datetime.datetime.now().isoformat(timespec="seconds"))
    log.append(entry)
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    _save_json(CHANGES_LOG, log)


# ── Core category-change logic (mirrors category_changer._apply_category_change_to_files) ──

def _apply_change(jobs_raw: list, flat_raw: list, job: dict, new_category: str) -> tuple[bool, str]:
    """
    Mutates jobs_raw + flat_raw in-place, patches + moves the HTML file,
    updates jobs-table.html, and appends to the audit log.
    Returns (success, error_message).
    """
    old_category = job.get("job_category", "other")
    slug         = job.get("job_id", "")
    old_image    = job.get("image_url", "")

    old_html = JOBS_DIR / old_category / f"{slug}.html"
    new_html = JOBS_DIR / new_category / f"{slug}.html"

    if not old_html.exists():
        return False, f"HTML not found: {old_html}"

    new_image_url = _pick_image(new_category, old_image)
    old_job_url   = f"{SITE_BASE}/jobs/{old_category}/{slug}"
    new_job_url   = f"{SITE_BASE}/jobs/{new_category}/{slug}"
    old_img_pfx   = f"{SITE_BASE}/images/jobs/{old_category}/"

    # 1. Patch jobs_raw
    for item in jobs_raw:
        bucket = item.get("jobs", [item]) if "jobs" in item else [item]
        for j in bucket:
            if j.get("job_id") == slug:
                j["job_category"] = new_category
                j["jobUrl"]       = new_job_url
                j["image_url"]    = new_image_url

    # 2. Patch flat_raw
    for j in flat_raw:
        if j.get("job_id") == slug:
            j["job_category"] = new_category
            j["jobUrl"]       = new_job_url
            j["image_url"]    = new_image_url

    # 3. Patch HTML
    with open(old_html, "r", encoding="utf-8") as f:
        html = f.read()
    html = html.replace(old_job_url, new_job_url)
    html = re.sub(re.escape(old_img_pfx) + r"[\w\-\.]+", new_image_url, html)
    html = html.replace(f"?category={old_category}", f"?category={new_category}")
    html = html.replace(
        f'itemprop="name">{_fmt_cat(old_category)}</span>',
        f'itemprop="name">{_fmt_cat(new_category)}</span>',
    )

    # 4. Move HTML
    new_html.parent.mkdir(parents=True, exist_ok=True)
    with open(new_html, "w", encoding="utf-8") as f:
        f.write(html)
    old_html.unlink()

    # Clean up empty old dir
    try:
        old_dir = JOBS_DIR / old_category
        if old_dir.exists() and not any(old_dir.iterdir()):
            old_dir.rmdir()
    except Exception:
        pass

    # 5. Patch jobs-table.html
    if JOBS_TABLE.exists():
        with open(JOBS_TABLE, "r", encoding="utf-8") as f:
            tbl = f.read()
        tbl = tbl.replace(old_job_url, new_job_url)
        tbl = re.sub(
            r'(data-title="[^"]*"[^>]*?data-category=")'
            + re.escape(old_category) + r'"',
            r'\g<1>' + new_category + '"',
            tbl,
        )
        tbl = tbl.replace(f">{_fmt_cat(old_category)}<", f">{_fmt_cat(new_category)}<")
        with open(JOBS_TABLE, "w", encoding="utf-8") as f:
            f.write(tbl)

    # 6. Audit log
    _append_change_log({
        "job_id":       slug,
        "title":        job.get("title", ""),
        "old_category": old_category,
        "new_category": new_category,
        "source":       "pipeline_post_check",
    })

    return True, ""


# ── Git helper ─────────────────────────────────────────────────────────────────

def _git_commit_push(changed_jobs: list) -> None:
    count = len(changed_jobs)
    if count == 1:
        msg = (f"fix: post-check reclassify '{changed_jobs[0]['job_id']}' "
               f"to '{changed_jobs[0]['new_category']}'")
    else:
        slugs = ", ".join(j["job_id"] for j in changed_jobs[:5])
        if count > 5:
            slugs += f" … (+{count - 5} more)"
        msg = f"fix: post-check reclassified {count} job(s) — {slugs}"

    repo = str(_ROOT_DIR)
    try:
        subprocess.run(["git", "add", "-A"], cwd=repo, capture_output=True, check=False)
        res = subprocess.run(
            ["git", "commit", "-m", msg],
            cwd=repo, capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if "nothing to commit" in (res.stdout + res.stderr).lower():
            logger.info("[cat_check] Nothing new to commit.")
            return
        subprocess.run(["git", "push"], cwd=repo, capture_output=True, check=False)
        logger.info("[cat_check] Git committed + pushed: %s", msg)
    except Exception as exc:
        logger.warning("[cat_check] Git error: %s", exc)


# ── Main background worker ─────────────────────────────────────────────────────

def _run_check(jobs_to_check: list[dict]) -> None:
    """
    Called in a daemon thread.  jobs_to_check is a list of freshly formatted
    job dicts (from the pipeline's newly_formatted_batch).
    """
    if not jobs_to_check:
        return

    # 1. Detect Ollama
    model = _detect_best_model()
    if model is None:
        logger.info("[cat_check] Ollama offline — skipping post-check for this batch.")
        return

    # 2. Load valid categories
    cat_data = _load_json(CAT_JSON)
    valid_cats = cat_data.get("categories", []) if cat_data else []
    if not valid_cats:
        logger.warning("[cat_check] all_jobs_cat.json missing or empty — skipping.")
        return

    logger.info("[cat_check] Starting post-check on %d job(s) with model %s", len(jobs_to_check), model)

    changed_jobs = []

    with _file_lock:
        # Load JSON stores once, under lock
        jobs_raw = _load_json(JOBS_JSON)
        flat_raw = _load_json(FLAT_JSON) or []
        if jobs_raw is None:
            logger.warning("[cat_check] jobs.json not found — aborting.")
            return

        for job in jobs_to_check:
            title       = job.get("title", "Untitled")
            company     = job.get("company", "")
            description = job.get("formatted_description") or job.get("description", "")
            current_cat = job.get("job_category", "other")
            slug        = job.get("job_id", "")

            if not slug:
                continue

            suggested = _ask_ollama(model, title, company, description, current_cat, valid_cats)

            if suggested is None or suggested == current_cat:
                logger.debug("[cat_check] ✓ %s — category OK (%s)", title, current_cat)
                continue

            logger.info("[cat_check] → %s: '%s' → '%s'", title, current_cat, suggested)

            success, err = _apply_change(jobs_raw, flat_raw, job, suggested)
            if success:
                job["job_category"] = suggested   # update in-memory reference
                changed_jobs.append({
                    "job_id":       slug,
                    "title":        title,
                    "old_category": current_cat,
                    "new_category": suggested,
                })
                logger.info("[cat_check] ✓ Changed '%s' → '%s'", current_cat, suggested)
            else:
                logger.warning("[cat_check] ✗ Failed to apply change for '%s': %s", slug, err)

            time.sleep(0.2)   # small pause between Ollama calls

        # Persist updated JSON files (still under lock)
        if changed_jobs:
            _save_jobs_json(JOBS_JSON, jobs_raw)
            _save_json(FLAT_JSON, flat_raw)
            logger.info("[cat_check] Saved updated jobs.json + formatted_jobs_flat.json")

    # Git outside the file lock
    if changed_jobs:
        _git_commit_push(changed_jobs)
        logger.info("[cat_check] Post-check complete. %d correction(s) applied.", len(changed_jobs))
    else:
        logger.info("[cat_check] Post-check complete. All categories correct.")


# ── Public API ─────────────────────────────────────────────────────────────────

def run_check_sync(newly_formatted_jobs: list[dict]) -> None:
    """
    Synchronous (blocking) entry point called by run_pipeline.py after each batch.

    Runs the full category verification pass for the batch and returns only when
    all checks, corrections, JSON/HTML patches are complete.
    The pipeline's git commit + push then follows immediately after this returns,
    so every correction is included in the same batch commit.

    Args:
        newly_formatted_jobs: list of fully formatted job dicts from Job_formatter.format_jobs()
    """
    if not newly_formatted_jobs:
        return
    _run_check(newly_formatted_jobs)


def schedule_check(newly_formatted_jobs: list[dict]) -> None:
    """
    Asynchronous (daemon thread) variant — kept for ad-hoc / external callers.
    The pipeline uses run_check_sync() instead.
    """
    if not newly_formatted_jobs:
        return
    t = threading.Thread(
        target=_run_check,
        args=(list(newly_formatted_jobs),),
        daemon=True,
        name="CatPostCheck",
    )
    t.start()
    logger.info("[cat_check] Background category check scheduled for %d job(s).", len(newly_formatted_jobs))
