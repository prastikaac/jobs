"""
category_post_check.py — Optimized version

Key Improvements:
- Lightweight LM Studio prompt (title + category only)
- Faster inference (max_tokens=16, timeout=45)
- Removed artificial delay
- Uses Qwen2.5-1.5B recommended model
"""

import datetime
import json
import logging
import queue
import re
import threading
import urllib.request
from pathlib import Path

# ── Setup ─────────────────────────────────────────
_SCRAPER_DIR = Path(__file__).parent
_LOG_FILE = _SCRAPER_DIR / "category_post_check.log"

logger = logging.getLogger("cat_post_check")
if not logger.handlers:
    logger.setLevel(logging.INFO)
    fh = logging.FileHandler(_LOG_FILE, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(fh)
    logger.propagate = False

LM_STUDIO_BASE_URL = "http://localhost:1234"
_SENTINEL = object()

# ── Prompt (SIMPLIFIED) ───────────────────────────
_PROMPT_TMPL = """\
Check if the given job category is correct according to the job title.

Job Title: {title}
Current Category: {current_category}

Valid Categories:
{cat_list}

Rules:
- If correct → output: correct
- If incorrect → output ONLY the correct category slug
- No explanation
- One word only

Answer:
"""

# ── LM Studio helpers ─────────────────────────────
def _detect_best_model():
    return "qwen2.5-1.5b-instruct"

def _ask_lmstudio(model, title, current_category, valid_cats):
    cat_list = "\n".join(f"- {c}" for c in valid_cats)

    prompt = _PROMPT_TMPL.format(
        title=title,
        current_category=current_category,
        cat_list=cat_list
    )

    payload = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.0,
        "max_tokens": 16,
        "stream": False,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{LM_STUDIO_BASE_URL}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read())
        raw = data["choices"][0]["message"]["content"].strip().lower()
        raw = re.sub(r"[^a-z0-9\-]", "", raw)
    except Exception as e:
        logger.warning(f"LM Studio error: {e}")
        return None

    if raw == "correct":
        return current_category

    if raw in valid_cats:
        return raw

    return None

# ── Batch Checker ─────────────────────────────────
class BatchChecker:

    def __init__(self):
        self._queue = queue.Queue()
        self._thread = None
        self._model = None
        self._valid_cats = []
        self._ready = False
        self._changed = []
        self._total = 0

    def start(self):
        self._model = _detect_best_model()

        cat_path = _SCRAPER_DIR / "all_jobs_cat.json"
        if not cat_path.exists():
            return

        with open(cat_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self._valid_cats = data.get("categories", [])
        if not self._valid_cats:
            return

        self._ready = True

        self._thread = threading.Thread(target=self._worker, daemon=True)
        self._thread.start()

    def submit(self, job):
        if not self._ready:
            return
        self._queue.put(job)

    def _worker(self):
        while True:
            job = self._queue.get()

            if job is _SENTINEL:
                self._queue.task_done()
                break

            self._check_one(job)
            self._queue.task_done()

    def _check_one(self, job):
        title = job.get("title", "")
        current_cat = job.get("job_category", "other")

        suggested = _ask_lmstudio(
            self._model,
            title,
            current_cat,
            self._valid_cats
        )

        self._total += 1

        if not suggested or suggested == current_cat:
            return

        job["job_category"] = suggested

        raw_ref = job.get("_raw_ref")
        if raw_ref:
            raw_ref["ai_data"]["job_category"] = suggested

        self._changed.append({
            "title": title,
            "old": current_cat,
            "new": suggested
        })

    def wait(self):
        if not self._ready:
            return []

        self._queue.put(_SENTINEL)
        self._queue.join()
        self._thread.join()

        logger.info(f"Checked: {self._total}, Changed: {len(self._changed)}")

        return self._changed


# ── Helpers ───────────────────────────────────────
def run_check_sync(jobs):
    checker = BatchChecker()
    checker.start()

    for j in jobs:
        checker.submit(j)

    return checker.wait()