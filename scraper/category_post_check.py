"""
category_post_check.py — Per-job background category verifier for the scraping pipeline.

Architecture:
  - BatchChecker is created in run_pipeline.py before Phase 3 starts.
  - ai_processor.py calls checker.submit(job) immediately after each job
    finishes AI processing (one job at a time, as they complete).
  - A background worker thread receives jobs from an internal queue and runs
    the Ollama category verification concurrently with the AI processor.
  - run_pipeline.py calls checker.wait() after all AI processing is done.
    This blocks until every submitted job has been checked.
  - If any corrections were found they are already applied to JSON + HTML.
  - Phase 4 (Python formatter / site gen / git push) then proceeds with
    correct categories already in place.

Logging goes to:
  scraper/category_post_check.log  (dedicated file, INFO level)
  + the main pipeline logger at DEBUG level for in-console visibility.

If Ollama is offline, BatchChecker silently skips all checks — pipeline unaffected.
"""

import datetime
import json
import logging
import logging.handlers
import queue
import random
import re
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

# ── Dedicated log file (FILE ONLY — not shown on terminal) ──────────────────
_SCRAPER_DIR = Path(__file__).parent
_LOG_FILE    = _SCRAPER_DIR / "category_post_check.log"

_cat_logger = logging.getLogger("cat_post_check")
if not _cat_logger.handlers:
    _cat_logger.setLevel(logging.INFO)
    _fh = logging.FileHandler(_LOG_FILE, encoding="utf-8")
    _fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    _cat_logger.addHandler(_fh)
    _cat_logger.propagate = False   # ← logs stay in the file, NOT on the terminal

logger = _cat_logger

# Pipeline logger — used for the single end-of-batch summary shown on terminal
_pipe_logger = logging.getLogger("pipeline")

# ── Paths ────────────────────────────────────────────────────────────────────
_ROOT_DIR   = _SCRAPER_DIR.parent
_DATA_DIR   = _SCRAPER_DIR / "data"

JOBS_JSON        = _DATA_DIR / "jobs.json"
FLAT_JSON        = _DATA_DIR / "formatted_jobs_flat.json"
CAT_JSON         = _SCRAPER_DIR / "all_jobs_cat.json"
JOBS_DIR         = _ROOT_DIR / "jobs"
JOBS_TABLE       = _ROOT_DIR / "jobs-table.html"
CHANGES_LOG      = _DATA_DIR / "category_changes_log.json"
CATEGORY_CHECK_JSON = _DATA_DIR / "category_check.json"   # per-run detection log

SITE_BASE          = "https://findjobsinfinland.fi"
LM_STUDIO_BASE_URL = "http://localhost:1234"

# Sentinel posted to the queue to signal end-of-batch
_SENTINEL = object()

# Global file lock — shared across all BatchChecker instances (there will
# only ever be one active at a time, but safe regardless).
_file_lock = threading.Lock()

# Separate lock for the category_check.json writer so it never contends with
# the BatchChecker's internal file operations.
_cc_lock = threading.Lock()


# ══════════════════════════════════════════════════════════════════════════════
# Non-blocking category_check.json writer  (called from ai_processor)
# ══════════════════════════════════════════════════════════════════════════════

def save_to_category_check(raw_job: dict, detected_category: str) -> None:
    """
    Fire-and-forget: appends the detected category for one job to
    scraper/data/category_check.json without blocking the AI pipeline.

    Called by ai_processor immediately after detect_category_by_keywords(),
    before the Ollama AI call starts.  The write runs in a short-lived daemon
    thread so the main thread returns instantly.
    """
    record = {
        "id":                raw_job.get("id", ""),
        "job_id":            raw_job.get("job_id", ""),
        "title":             raw_job.get("title", ""),
        "company":           raw_job.get("company", ""),
        "detected_category": detected_category,
        "saved_at":          datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

    def _write() -> None:
        try:
            with _cc_lock:
                _DATA_DIR.mkdir(parents=True, exist_ok=True)
                existing: list = []
                if CATEGORY_CHECK_JSON.exists():
                    try:
                        with open(CATEGORY_CHECK_JSON, "r", encoding="utf-8") as f:
                            existing = json.load(f)
                        if not isinstance(existing, list):
                            existing = []
                    except Exception:
                        existing = []
                # Upsert by id so re-runs don't duplicate
                existing = [e for e in existing if e.get("id") != record["id"]]
                existing.append(record)
                with open(CATEGORY_CHECK_JSON, "w", encoding="utf-8") as f:
                    json.dump(existing, f, indent=2, ensure_ascii=False)
        except Exception as exc:
            logger.warning("[cat_check] Failed to write category_check.json: %s", exc)

    threading.Thread(target=_write, daemon=True, name="CatCheckWriter").start()


# ══════════════════════════════════════════════════════════════════════════════
# LM Studio helpers  (OpenAI-compatible API on port 1234)
# ══════════════════════════════════════════════════════════════════════════════

def _lmstudio_get(path: str):
    """GET a JSON endpoint from LM Studio; returns None if offline."""
    try:
        req = urllib.request.Request(f"{LM_STUDIO_BASE_URL}{path}")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def _detect_best_model() -> str | None:
    """
    Return the first model currently loaded in LM Studio, or None if
    LM Studio is offline / no model is loaded.
    GET /v1/models  →  {"data": [{"id": "model-id", ...}, ...]}
    """
    resp = _lmstudio_get("/v1/models")
    if resp is None:
        return None
    models = resp.get("data", [])
    if not models:
        return None
    # LM Studio only loads one model at a time; just return whatever is there
    return models[0]["id"]


_PROMPT_TMPL = """\
You are a precise job classification engine. Output ONE word only from the VALID CATEGORIES list below.

TASK:
Read the job details and output ONLY the best matching category slug.
Do NOT explain. Do NOT add punctuation. Output only the slug.

---
Job Title       : {title}
Company         : {company}
Job Description : {description}

VALID CATEGORIES:
{cat_list}
---
Category Slug:"""


def _ask_lmstudio(model: str, title: str, company: str, description: str,
                  valid_cats: list[str]) -> str | None:
    """Returns detected slug, or None if LM Studio unavailable/invalid."""
    cat_list = "\n".join(f"  - {c}" for c in valid_cats)
    prompt   = _PROMPT_TMPL.format(
        title=title,
        company=company,
        description=(description or "")[:350], # Trimmed to speed up inference
        cat_list=cat_list,
    )
    payload = json.dumps({
        "model":       model,
        "messages":    [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens":  64,
        "stream":      False,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{LM_STUDIO_BASE_URL}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            data = json.loads(resp.read())
        # OpenAI response: {"choices": [{"message": {"content": "..."}}]}
        raw = data["choices"][0]["message"]["content"].strip().lower()
        raw = raw.split()[0] if raw else ""
        raw = re.sub(r"[^a-z0-9\-]", "", raw)
    except Exception as exc:
        logger.warning("[cat_check] LM Studio error for '%s': %s", title, exc)
        return None

    if not raw:
        return None
    if raw in valid_cats:
        return raw
    for vc in valid_cats:
        if raw in vc or vc in raw:
            return vc
    logger.debug("[cat_check] Unknown slug '%s' for '%s' — ignoring.", raw, title)
    return None



# ══════════════════════════════════════════════════════════════════════════════
# File / JSON helpers
# ══════════════════════════════════════════════════════════════════════════════

def _load_json(path: Path):
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        return None


def _save_json(path: Path, data) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _save_jobs_json(path: Path, jobs_raw: list) -> None:
    text = json.dumps(jobs_raw, ensure_ascii=False, indent=2)
    text = text.replace("  },\n  {", "  },\n\n  {")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


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
    log: list = []
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


# ══════════════════════════════════════════════════════════════════════════════
# Category-change applier
# ══════════════════════════════════════════════════════════════════════════════

def _apply_change(jobs_raw: list, flat_raw: list, job: dict,
                  new_category: str) -> tuple[bool, str]:
    """
    Mutates jobs_raw + flat_raw in-place, moves the HTML file,
    patches jobs-table.html, and appends to the audit log.
    Returns (success, error_message).
    NOTE: caller must hold _file_lock before calling this.
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

    # 3. Patch + move HTML
    with open(old_html, "r", encoding="utf-8") as f:
        html = f.read()
    html = html.replace(old_job_url, new_job_url)
    html = re.sub(re.escape(old_img_pfx) + r"[\w\-\.]+", new_image_url, html)
    html = html.replace(f"?category={old_category}", f"?category={new_category}")
    html = html.replace(
        f'itemprop="name">{_fmt_cat(old_category)}</span>',
        f'itemprop="name">{_fmt_cat(new_category)}</span>',
    )
    new_html.parent.mkdir(parents=True, exist_ok=True)
    with open(new_html, "w", encoding="utf-8") as f:
        f.write(html)
    old_html.unlink()

    try:
        old_dir = JOBS_DIR / old_category
        if old_dir.exists() and not any(old_dir.iterdir()):
            old_dir.rmdir()
    except Exception:
        pass

    # 4. Patch jobs-table.html
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

    # 5. Audit log
    _append_change_log({
        "job_id":       slug,
        "title":        job.get("title", ""),
        "old_category": old_category,
        "new_category": new_category,
        "source":       "pipeline_post_check",
    })

    return True, ""


# ══════════════════════════════════════════════════════════════════════════════
# Git helper
# ══════════════════════════════════════════════════════════════════════════════

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


# ══════════════════════════════════════════════════════════════════════════════
# BatchChecker — public API used by the pipeline
# ══════════════════════════════════════════════════════════════════════════════

class BatchChecker:
    """
    Per-batch category verifier that runs concurrently with ai_processor.

    Usage in run_pipeline.py:
        checker = category_post_check.BatchChecker()
        checker.start()                           # starts background worker
        # ... Phase 3 runs, calling checker.submit(job) per completed job ...
        checker.wait()                            # block until all checks done
        # Phase 4 proceeds — categories already corrected

    The background worker:
    - Receives jobs one at a time from a queue as ai_processor finishes them
    - Asks Ollama whether the assigned category is correct
    - If wrong: applies corrections (JSON + HTML + audit log) immediately
    - Logs everything to category_post_check.log
    - After wait() returns, all corrections are on disk; no separate git push
      is needed here — the pipeline's own git commit covers them.
    """

    def __init__(self) -> None:
        self._queue: queue.Queue = queue.Queue()
        self._thread: threading.Thread | None = None
        self._changed_jobs: list[dict] = []
        self._total_checked: int = 0
        self._model: str | None = None
        self._valid_cats: list[str] = []
        self._ready = False          # True once Ollama + cats are confirmed
        self._jobs_raw: list = []
        self._flat_raw: list = []

    # ── Setup ─────────────────────────────────────────────────────────────────

    def start(self) -> None:
        """
        Detect LM Studio model + load categories once, then start the
        background worker thread.  Call this before Phase 3 begins.
        """
        model = _detect_best_model()
        if model is None:
            logger.info("[cat_check] LM Studio offline — category post-check disabled for this batch.")
            return

        cat_data   = _load_json(CAT_JSON)
        valid_cats = cat_data.get("categories", []) if cat_data else []
        if not valid_cats:
            logger.warning("[cat_check] all_jobs_cat.json missing or empty — post-check disabled.")
            return

        self._model      = model
        self._valid_cats = valid_cats
        self._ready      = True

        logger.info("[cat_check] BatchChecker started. LM Studio model=%s, categories=%d",
                    model, len(valid_cats))

        self._thread = threading.Thread(
            target=self._worker,
            daemon=True,
            name="CatPostCheck",
        )
        self._thread.start()

    # ── Producer side (called by ai_processor) ────────────────────────────────

    def submit(self, formatted_job: dict) -> None:
        """
        Called by ai_processor immediately after one job finishes Phase 3.
        Non-blocking — puts the job on the internal queue and returns instantly.
        Does nothing if Ollama was offline when start() was called.
        """
        if not self._ready:
            return
        self._queue.put(formatted_job)

    # ── Consumer side (background thread) ─────────────────────────────────────

    def _worker(self) -> None:
        """
        Runs in a daemon thread concurrently with ai_processor.
        Receives jobs one at a time from the queue as Phase 3 finishes them.
        Corrections are applied IN-MEMORY only (updates _raw_ref["ai_data"]["job_category"]).
        Phase 4 then runs with already-correct categories so HTML/JSON land in the
        right folders from the start — no post-hoc file patching required here.
        """
        logger.info("[cat_check] Worker thread started — waiting for jobs …")

        while True:
            try:
                job = self._queue.get(timeout=300)   # 5-min safety timeout
            except queue.Empty:
                logger.warning("[cat_check] Worker timed out waiting for jobs.")
                break

            if job is _SENTINEL:
                self._queue.task_done()
                break

            self._check_one(job)
            self._queue.task_done()

        if self._changed_jobs:
            n = len(self._changed_jobs)
            logger.info(
                "[cat_check] %d category correction(s) applied in-memory. "
                "Phase 4 will write HTML/JSON with the correct categories.", n
            )
        else:
            logger.info("[cat_check] All categories correct — no changes needed.")

        logger.info("[cat_check] Worker thread finished.")

    def _check_one(self, job: dict) -> None:
        """Verify the category of a single job and correct it in-memory if needed."""
        title       = job.get("title", "Untitled")
        company     = job.get("company", "")
        description = job.get("formatted_description") or job.get("description", "")
        current_cat = job.get("job_category", "other")
        slug        = job.get("job_id", "")

        logger.info("[cat_check] Checking: %s | current=%s", title, current_cat)

        suggested = _ask_lmstudio(
            self._model, title, company, description,
            self._valid_cats,
        )

        self._total_checked += 1

        if suggested is None or suggested == current_cat:
            logger.info("category is correct")
            return

        logger.info("category is incorrect, changed to category -- %s from -- %s",
                    suggested, current_cat)

        # ── In-memory correction only ──────────────────────────────────────
        # Update the submit_job dict itself
        job["job_category"] = suggested

        # Update the original raw dict from ai_processor so Phase 4 picks up
        # the corrected category when it calls Job_formatter.format_jobs().
        raw_ref = job.get("_raw_ref")
        if raw_ref is not None:
            ai_data = raw_ref.get("ai_data", {})
            ai_data["job_category"] = suggested
            raw_ref["ai_data"] = ai_data

        self._changed_jobs.append({
            "job_id":       slug or "(unknown)",
            "title":        title,
            "old_category": current_cat,
            "new_category": suggested,
        })

        # Append to the history JSON for the debug HTML page
        _append_change_log({
            "job_id":       slug or "(unknown)",
            "title":        title,
            "old_category": current_cat,
            "new_category": suggested,
            "source":       "pipeline_post_check",
        })

        # Removed verbose in-memory correction log to keep terminal/file clean

        time.sleep(0.1)   # brief pause between Ollama calls

    # ── Barrier (called by run_pipeline after Phase 3) ────────────────────────

    def wait(self) -> list[dict]:
        """
        Signal end-of-batch, then block until the background worker has
        processed every submitted job.  Returns the list of changed jobs.

        After returning, logs a single summary line to the TERMINAL via the
        pipeline logger.  All per-job detail is in category_post_check.log.
        """
        if not self._ready or self._thread is None:
            return []

        # Post sentinel so the worker knows no more jobs are coming
        self._queue.put(_SENTINEL)

        # Wait for queue to drain (task_done called for every item incl. sentinel)
        self._queue.join()

        # Wait for thread to fully exit
        self._thread.join(timeout=10)

        n = len(self._changed_jobs)
        if n:
            corrections = ", ".join(
                f"{j['title']} ({j['old_category']} → {j['new_category']})"
                for j in self._changed_jobs
            )
            _pipe_logger.info(
                "[cat_check] %d category correction(s) applied: %s | "
                "Details → scraper/category_post_check.log",
                n, corrections,
            )
        else:
            _pipe_logger.info(
                "[cat_check] All %d job(s) — categories correct. "
                "Details → scraper/category_post_check.log",
                self._total_checked,
            )

        # Generate static debug HTML
        generate_debug_html()

        return self._changed_jobs


# ══════════════════════════════════════════════════════════════════════════════
# Static Debug HTML Generator
# ══════════════════════════════════════════════════════════════════════════════

def generate_debug_html() -> None:
    """Statically builds category_debug.html at the end of the batch check."""
    from html import escape
    
    check_data = _load_json(CATEGORY_CHECK_JSON) or []
    changes_data = _load_json(CHANGES_LOG) or []

    changes_map = {c.get("job_id"): c for c in changes_data}
    
    tbody_html = ""
    global_jobs_js = "const globalJobData = [\n"
    changed_count = 0

    import html
    
    # Pre-calculate data
    for job in check_data:
        jid = job.get("job_id") or job.get("id")
        ch_log = changes_map.get(jid)
        is_changed = bool(ch_log)
        if is_changed:
            changed_count += 1
            
        final_cat = ch_log["new_category"] if is_changed else job.get("detected_category", "")
        title_esc = html.escape(job.get("title", ""))
        company_esc = html.escape(job.get("company", ""))
        
        global_jobs_js += f'  {{ title: {json.dumps(job.get("title", ""))}, category: {json.dumps(final_cat)} }},\n'

        if is_changed:
            cat_html = f'''
                <span class="category-pill" style="text-decoration: line-through; opacity: 0.6;">{html.escape(job.get('detected_category', ''))}</span>
                <span class="arrow">→</span>
                <span class="category-pill" style="border: 1px solid var(--warning); color: var(--warning);">{html.escape(ch_log['new_category'])}</span>
            '''
            status_html = '<span class="badge badge-changed">AI Corrected</span>'
        else:
            cat_html = f'<span class="category-pill">{html.escape(final_cat)}</span>'
            status_html = '<span class="badge badge-ok">AI Verified OK</span>'

        tbody_html += f'''
            <tr>
                <td>
                    <div class="job-title">{title_esc}</div>
                    <div class="company-name">{company_esc}</div>
                </td>
                <td>{cat_html}</td>
                <td>{status_html}</td>
                <td>
                    <button class="btn btn-small" onclick="copySingle({json.dumps(job.get('title', ''))}, {json.dumps(final_cat)})">
                        Copy
                    </button>
                </td>
            </tr>
        '''
        
    global_jobs_js += "];"

    page_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Category Post-Check Debugger</title>
    <style>
        :root {{
            --bg-color: #0f172a;
            --surface-color: #1e293b;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --primary: #3b82f6;
            --primary-hover: #2563eb;
            --success: #10b981;
            --warning: #f59e0b;
            --border: #334155;
        }}
        body {{
            font-family: 'Inter', system-ui, -apple-system, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-main);
            margin: 0;
            padding: 2rem;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}
        .header {{
            display: flex; justify-content: space-between; align-items: center;
            margin-bottom: 2rem; padding-bottom: 1rem; border-bottom: 1px solid var(--border);
        }}
        h1 {{ margin: 0; font-size: 1.5rem; font-weight: 600; }}
        .btn {{
            background-color: var(--primary); color: white; border: none;
            padding: 0.5rem 1rem; border-radius: 6px; font-weight: 500;
            cursor: pointer; transition: background-color 0.2s;
            display: inline-flex; align-items: center; gap: 0.5rem; font-size: 0.875rem;
        }}
        .btn:hover {{ background-color: var(--primary-hover); }}
        .btn-small {{
            padding: 0.25rem 0.75rem; font-size: 0.75rem;
            background-color: var(--surface-color); border: 1px solid var(--border);
        }}
        .btn-small:hover {{ background-color: #334155; }}
        table {{
            width: 100%; border-collapse: collapse; background-color: var(--surface-color);
            border-radius: 8px; overflow: hidden; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        }}
        th, td {{ padding: 1rem; text-align: left; border-bottom: 1px solid var(--border); }}
        th {{
            background-color: rgba(0,0,0,0.2); font-weight: 500; color: var(--text-muted);
            text-transform: uppercase; font-size: 0.75rem; letter-spacing: 0.05em;
        }}
        tr:last-child td {{ border-bottom: none; }}
        .job-title {{ font-weight: 500; }}
        .company-name {{ color: var(--text-muted); font-size: 0.875rem; margin-top: 0.25rem; }}
        .badge {{ display: inline-flex; padding: 0.25rem 0.5rem; border-radius: 9999px; font-size: 0.75rem; font-weight: 500; }}
        .badge-ok {{ background-color: rgba(16, 185, 129, 0.1); color: var(--success); }}
        .badge-changed {{ background-color: rgba(245, 158, 11, 0.1); color: var(--warning); }}
        .category-pill {{ display: inline-block; background-color: rgba(255,255,255,0.1); padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.875rem; }}
        .arrow {{ color: var(--text-muted); margin: 0 0.5rem; }}
        .toast {{
            position: fixed; bottom: 2rem; right: 2rem; background-color: var(--success); color: white;
            padding: 1rem 1.5rem; border-radius: 8px; box-shadow: 0 10px 15px -3px rgba(0,0,0,0.1);
            transform: translateY(150%); transition: transform 0.3s cubic-bezier(0.4, 0, 0.2, 1);
            z-index: 50; font-weight: 500;
        }}
        .toast.show {{ transform: translateY(0); }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div>
                <h1>Category Post-Check Debugger</h1>
                <div style="color: var(--text-muted); font-size: 0.875rem; margin-top: 0.5rem;" id="stats-text">
                    Total Scraped: {len(check_data)} | AI Corrections: {changed_count}
                </div>
            </div>
            <button class="btn" onclick="copyAll()">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>
                Copy All as Plain Text
            </button>
        </div>
        <table>
            <thead>
                <tr>
                    <th width="35%">Job details</th>
                    <th width="35%">Category Detection</th>
                    <th width="15%">AI Status</th>
                    <th width="15%">Actions</th>
                </tr>
            </thead>
            <tbody id="table-body">
                {tbody_html}
            </tbody>
        </table>
    </div>
    <div class="toast" id="toast">Copied to clipboard!</div>

    <script>
        {global_jobs_js}

        function copySingle(title, category) {{
            const text = title + " - " + category;
            navigator.clipboard.writeText(text).then(() => {{
                showToast("Copied: " + text);
            }});
        }}

        function copyAll() {{
            if (globalJobData.length === 0) return;
            const text = globalJobData.map(j => j.title + " - " + j.category).join('\\n');
            navigator.clipboard.writeText(text).then(() => {{
                showToast("Copied " + globalJobData.length + " jobs to clipboard");
            }});
        }}

        function showToast(msg) {{
            const toast = document.getElementById('toast');
            toast.textContent = msg;
            toast.classList.add('show');
            setTimeout(() => {{ toast.classList.remove('show'); }}, 3000);
        }}
    </script>
</body>
</html>
"""
    try:
        out_path = _SCRAPER_DIR / "category_debug.html"
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(page_html)
        logger.info("[cat_check] Generated static category_debug.html")
    except Exception as e:
        logger.warning("[cat_check] Failed to generate debug HTML: %s", e)

# ══════════════════════════════════════════════════════════════════════════════
# Legacy API (kept for backwards compatibility / manual use)
# ══════════════════════════════════════════════════════════════════════════════

def run_check_sync(newly_formatted_jobs: list[dict]) -> None:
    """Synchronous batch check — legacy entry point."""
    if not newly_formatted_jobs:
        return
    checker = BatchChecker()
    checker.start()
    for job in newly_formatted_jobs:
        checker.submit(job)
    checker.wait()


def schedule_check(newly_formatted_jobs: list[dict]) -> None:
    """Async (daemon thread) batch check — legacy entry point."""
    if not newly_formatted_jobs:
        return
    t = threading.Thread(
        target=run_check_sync,
        args=(list(newly_formatted_jobs),),
        daemon=True,
        name="CatPostCheckAsync",
    )
    t.start()
