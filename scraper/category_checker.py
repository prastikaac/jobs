"""
category_changer.py — Combined Category Manager & AI Auditor
           for findjobsinfinland.fi

Usage:  python scraper/category_changer.py
        (run from the project root)

The server listens on http://localhost:8765
API endpoints:
  GET  /api/jobs          — returns all current jobs
  GET  /api/categories    — returns all valid categories
  GET  /api/history       — returns the change-log (audit panel)
  POST /api/change        — manually change a single job's category
  POST /api/auto_audit    — run AI-powered batch audit on all jobs
  GET  /                  — serves category-changer.html

AI audit uses Ollama running locally (https://ollama.com)
  Recommended model: llama3.1 or higher (auto-detected)
"""

import datetime
import http.server
import json
import os
import random
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
SCRIPT_DIR  = Path(__file__).parent                        # .../scraper/
ROOT_DIR    = SCRIPT_DIR.parent                             # project root
DATA_DIR    = SCRIPT_DIR / "data"
JOBS_JSON   = DATA_DIR / "jobs.json"
FLAT_JSON   = DATA_DIR / "formatted_jobs_flat.json"
CAT_JSON    = SCRIPT_DIR / "all_jobs_cat.json"
JOBS_DIR    = ROOT_DIR / "jobs"                             # jobs/<category>/<slug>.html
JOBS_TABLE  = ROOT_DIR / "jobs-table.html"
HTML_UI     = ROOT_DIR / "category-changer.html"
CHANGES_LOG = DATA_DIR / "category_changes_log.json"        # shared audit log

SITE_BASE   = "https://findjobsinfinland.fi"
PORT        = 8765

# ── Ollama settings ────────────────────────────────────────────────────────────
OLLAMA_BASE_URL  = "http://localhost:11434"
PREFERRED_MODELS = [
    "llama3.1", "llama3.2", "llama3", "llama3:8b",
    "gemma3", "gemma2", "mistral", "phi3", "phi",
]

# ── Audit state (shared between requests) ─────────────────────────────────────
_audit_lock   = threading.Lock()
_audit_status = {
    "running":   False,
    "total":     0,
    "processed": 0,
    "changed":   0,
    "errors":    [],
    "log":       [],       # live per-job messages streamed to UI
    "done":      False,
    "result":    None,
}

# ═══════════════════════════════════════════════════════════════════════════════
# ── Shared helpers ─────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

def load_json(path: Path):
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def save_jobs_json(path: Path, jobs_raw: list) -> None:
    """Save jobs.json preserving the blank-line separator between top-level items."""
    json_str = json.dumps(jobs_raw, ensure_ascii=False, indent=2)
    json_str = json_str.replace("  },\n  {", "  },\n\n  {")
    with open(path, "w", encoding="utf-8") as f:
        f.write(json_str)


def append_change_log(entry: dict) -> None:
    """Append one change record to the persistent audit log."""
    log = []
    if CHANGES_LOG.exists():
        try:
            with open(CHANGES_LOG, "r", encoding="utf-8") as f:
                log = json.load(f)
        except Exception:
            log = []
    entry.setdefault("timestamp", datetime.datetime.now().isoformat(timespec="seconds"))
    log.append(entry)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    save_json(CHANGES_LOG, log)


def load_change_log() -> list:
    return load_json(CHANGES_LOG) or []


def flat_jobs_from_jobs_json(data) -> list:
    flat = []
    for item in data:
        if isinstance(item, dict) and "jobs" in item:
            flat.extend(item["jobs"])
        elif isinstance(item, dict):
            flat.append(item)
    return flat


def _fmt_cat(slug: str) -> str:
    return slug.replace("-", " ").title()


# ── Git helpers ────────────────────────────────────────────────────────────────

def _run_git(args: list) -> tuple:
    result = subprocess.run(
        ["git"] + args,
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def _git_commit_and_push(slug: str, old_cat: str, new_cat: str) -> dict:
    """Single-job git commit (used by manual change)."""
    messages = []
    code, out, err = _run_git(["add", "-A"])
    messages.append(f"git add: {out or err or 'ok'}")

    commit_msg = f"chore: reclassify '{slug}' from '{old_cat}' to '{new_cat}'"
    code, out, err = _run_git(["commit", "-m", commit_msg])
    messages.append(f"git commit: {out or err or 'ok'}")

    if code != 0 and "nothing to commit" in (out + err).lower():
        return {"success": True, "messages": ["Nothing to commit — already up to date."]}

    code, out, err = _run_git(["push"])
    messages.append(f"git push: {out or err or 'ok'}")
    return {"success": code == 0, "messages": messages}


def _git_batch_commit_push(changed_jobs: list) -> dict:
    """Batched git commit for AI audit."""
    count = len(changed_jobs)
    messages = []

    code, out, err = _run_git(["add", "-A"])
    messages.append(f"git add: {out or err or 'ok'}")

    if count == 1:
        msg = (f"fix: AI reclassify '{changed_jobs[0]['job_id']}' "
               f"to '{changed_jobs[0]['new_category']}'")
    else:
        slugs = ", ".join(j["job_id"] for j in changed_jobs[:5])
        if count > 5:
            slugs += f" … (+{count-5} more)"
        msg = f"fix: AI reclassified {count} job(s) — {slugs}"

    code, out, err = _run_git(["commit", "-m", msg])
    messages.append(f"git commit: {out or err or 'ok'}")

    if "nothing to commit" in (out + err).lower():
        return {"success": True, "messages": ["Nothing to commit — all files already up to date."]}

    code, out, err = _run_git(["push"])
    messages.append(f"git push: {out or err or 'ok'}")
    return {"success": code == 0, "messages": messages}


# ═══════════════════════════════════════════════════════════════════════════════
# ── Manual category-change API ─────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

def api_get_jobs() -> list:
    raw = load_json(JOBS_JSON)
    if raw is None:
        return []
    return [
        {
            "id":           j.get("id", ""),
            "job_id":       j.get("job_id", ""),
            "title":        j.get("title", "Untitled"),
            "company":      j.get("company", ""),
            "job_category": j.get("job_category", "other"),
            "jobLocation":  j.get("jobLocation", []),
            "date_posted":  j.get("date_posted", ""),
            "jobUrl":       j.get("jobUrl", ""),
            "image_url":    j.get("image_url", ""),
        }
        for j in flat_jobs_from_jobs_json(raw)
    ]


def api_get_categories() -> list:
    data = load_json(CAT_JSON)
    if data and isinstance(data, dict):
        return data.get("categories", [])
    return []


def _pick_image(new_category: str, old_image_url: str) -> str:
    img_dir = ROOT_DIR / "images" / "jobs" / new_category
    if img_dir.exists():
        pngs = [p.name for p in img_dir.iterdir() if p.suffix.lower() == ".png"]
        if pngs:
            return f"{SITE_BASE}/images/jobs/{new_category}/{random.choice(pngs)}"
    return old_image_url


def _apply_category_change_to_files(
    jobs_raw: list,
    flat_raw: list,
    job: dict,
    new_category: str,
    source: str = "manual",
) -> tuple:
    """
    Shared low-level mutator used by both manual and AI change paths.
    Mutates jobs_raw and flat_raw in-place, patches + moves HTML, updates jobs-table.
    Returns (success: bool, error_message: str).
    """
    old_category  = job.get("job_category", "other")
    slug          = job.get("job_id", "")
    old_image     = job.get("image_url", "")

    old_html = JOBS_DIR / old_category / f"{slug}.html"
    new_html = JOBS_DIR / new_category / f"{slug}.html"

    if not old_html.exists():
        return False, f"HTML file not found: {old_html}"

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

    # 3. Patch HTML file
    with open(old_html, "r", encoding="utf-8") as f:
        html = f.read()

    html = html.replace(old_job_url, new_job_url)
    html = re.sub(re.escape(old_img_pfx) + r"[\w\-\.]+", new_image_url, html)
    html = html.replace(f"?category={old_category}", f"?category={new_category}")
    html = html.replace(
        f'itemprop="name">{_fmt_cat(old_category)}</span>',
        f'itemprop="name">{_fmt_cat(new_category)}</span>',
    )

    # 4. Move HTML file
    new_html.parent.mkdir(parents=True, exist_ok=True)
    with open(new_html, "w", encoding="utf-8") as f:
        f.write(html)
    old_html.unlink()

    # Remove old dir if empty
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
            r'(data-title="[^"]*"[^>]*?data-category=")' + re.escape(old_category) + r'"',
            r'\g<1>' + new_category + '"',
            tbl,
        )
        old_label = _fmt_cat(old_category)
        new_label = _fmt_cat(new_category)
        tbl = tbl.replace(f">{old_label}<", f">{new_label}<")
        with open(JOBS_TABLE, "w", encoding="utf-8") as f:
            f.write(tbl)

    # 6. Write to shared audit log
    append_change_log({
        "job_id":       slug,
        "title":        job.get("title", ""),
        "old_category": old_category,
        "new_category": new_category,
        "source":       source,
    })

    return True, ""


def change_category(job_id: str, new_category: str) -> dict:
    """
    Full manual-change flow:
      load → validate → apply → save JSON files → git commit/push
    """
    jobs_raw = load_json(JOBS_JSON)
    flat_raw = load_json(FLAT_JSON) or []

    if jobs_raw is None:
        return {"ok": False, "error": "jobs.json not found"}

    all_jobs   = flat_jobs_from_jobs_json(jobs_raw)
    target_job = next((j for j in all_jobs if j.get("job_id") == job_id), None)
    if not target_job:
        return {"ok": False, "error": f"Job '{job_id}' not found in jobs.json"}

    old_category = target_job.get("job_category", "other")
    if old_category == new_category:
        return {"ok": False, "error": "New category is the same as the current category"}

    success, err_msg = _apply_category_change_to_files(
        jobs_raw, flat_raw, target_job, new_category, source="manual"
    )
    if not success:
        return {"ok": False, "error": err_msg}

    # Save updated JSON
    save_jobs_json(JOBS_JSON, jobs_raw)
    save_json(FLAT_JSON, flat_raw)

    git_result = _git_commit_and_push(job_id, old_category, new_category)

    return {
        "ok":           True,
        "job_id":       job_id,
        "old_category": old_category,
        "new_category": new_category,
        "new_url":      f"{SITE_BASE}/jobs/{new_category}/{job_id}",
        "git":          git_result,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# ── AI / Ollama helpers ────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

def _ollama_get(path: str):
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE_URL}{path}")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def detect_best_model():
    """Return the best available Ollama model name, or None if Ollama is offline."""
    resp = _ollama_get("/api/tags")
    if resp is None:
        return None
    available = [m["name"].split(":")[0] for m in resp.get("models", [])]
    if not available:
        return None
    for pref in PREFERRED_MODELS:
        for avail in available:
            if avail.lower().startswith(pref.lower()):
                full = next(
                    m["name"] for m in resp["models"]
                    if m["name"].split(":")[0].lower() == avail.lower()
                )
                return full
    return resp["models"][0]["name"]


def ollama_generate(model: str, prompt: str, timeout: int = 60) -> str:
    """Send a non-streaming generate request to Ollama and return the text."""
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
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read())
    return data.get("response", "").strip()


_CATEGORY_PROMPT_TMPL = """\
You are a precise job classification engine. Your ONLY job is to output a single category slug.

TASK:
Determine the best category for this job from the VALID CATEGORIES list below.
If the CURRENT CATEGORY is already correct, output exactly: CORRECT
If the CURRENT CATEGORY is wrong, output ONLY the correct slug from the list (e.g. healthcare).

Do NOT explain. Do NOT add punctuation. Output one word or CORRECT.

---
Job Title       : {title}
Company         : {company}
Job Summary     : {description}
Current Category: {current_cat}

VALID CATEGORIES (pick EXACTLY one slug if correcting):
{cat_list}
---
Your answer:"""


def ai_check_category(
    model: str,
    title: str,
    company: str,
    description: str,
    current_cat: str,
    valid_cats: list,
):
    """
    Returns None if the current category is correct, or a new slug string if wrong.
    """
    cat_list = "\n".join(f"  - {c}" for c in valid_cats)
    prompt   = _CATEGORY_PROMPT_TMPL.format(
        title=title,
        company=company,
        description=(description or "")[:500],
        current_cat=current_cat,
        cat_list=cat_list,
    )
    try:
        response = ollama_generate(model, prompt)
    except Exception as ex:
        print(f"  [AI] Ollama error for '{title}': {ex}")
        return None

    raw = response.strip().lower().split()[0] if response.strip() else ""
    raw = re.sub(r"[^a-z0-9\-]", "", raw)

    if raw == "correct" or not raw:
        return None

    if raw in valid_cats:
        return raw

    for vc in valid_cats:
        if raw in vc or vc in raw:
            return vc

    print(f"  [AI] Unknown category '{raw}' for '{title}' — ignoring.")
    return None


# ═══════════════════════════════════════════════════════════════════════════════
# ── AI Audit – runs in a background thread ─────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

def _run_auto_audit_thread():
    """
    Background thread that performs the AI audit and updates _audit_status.
    Called by api_auto_audit(); result is polled by the UI via GET /api/audit_status.
    """
    global _audit_status

    def _log(msg):
        print(f"  [audit] {msg}")
        with _audit_lock:
            _audit_status["log"].append(msg)

    with _audit_lock:
        _audit_status.update({
            "running":   True,
            "total":     0,
            "processed": 0,
            "changed":   0,
            "errors":    [],
            "log":       [],
            "done":      False,
            "result":    None,
        })

    try:
        # Load data
        jobs_raw = load_json(JOBS_JSON)
        if jobs_raw is None:
            with _audit_lock:
                _audit_status["running"] = False
                _audit_status["done"]    = True
                _audit_status["result"]  = {"ok": False, "error": "jobs.json not found"}
            return

        flat_raw      = load_json(FLAT_JSON) or []
        all_cats_data = load_json(CAT_JSON)
        if not all_cats_data:
            with _audit_lock:
                _audit_status["running"] = False
                _audit_status["done"]    = True
                _audit_status["result"]  = {"ok": False, "error": "all_jobs_cat.json not found"}
            return

        valid_cats = all_cats_data.get("categories", [])
        all_jobs   = flat_jobs_from_jobs_json(jobs_raw)
        total      = len(all_jobs)

        with _audit_lock:
            _audit_status["total"] = total

        _log(f"Loaded {total} jobs and {len(valid_cats)} categories.")

        # Detect Ollama model
        model = detect_best_model()
        if model is None:
            with _audit_lock:
                _audit_status["running"] = False
                _audit_status["done"]    = True
                _audit_status["result"]  = {
                    "ok":    False,
                    "error": "Ollama is not running or has no models installed.",
                }
            return

        _log(f"Using Ollama model: {model}")

        changed_jobs = []
        errors       = []

        for idx, job in enumerate(all_jobs, 1):
            title       = job.get("title", "Untitled")
            company     = job.get("company", "")
            description = job.get("description", "")
            current_cat = job.get("job_category", "other")
            slug        = job.get("job_id", "")

            _log(f"[{idx}/{total}] {title} — current: {current_cat}")

            suggested = ai_check_category(
                model=model,
                title=title,
                company=company,
                description=description,
                current_cat=current_cat,
                valid_cats=valid_cats,
            )

            with _audit_lock:
                _audit_status["processed"] = idx

            if suggested is None or suggested == current_cat:
                _log(f"  ✓ Correct — no change.")
                continue

            _log(f"  → AI suggests: {suggested}  (was: {current_cat})")

            success, err_msg = _apply_category_change_to_files(
                jobs_raw, flat_raw, job, suggested, source="ai"
            )

            if success:
                _log(f"  ✓ Changed '{current_cat}' → '{suggested}'")
                changed_jobs.append({
                    "job_id":       slug,
                    "title":        title,
                    "old_category": current_cat,
                    "new_category": suggested,
                })
                job["job_category"] = suggested  # keep in-memory consistent
                with _audit_lock:
                    _audit_status["changed"] = len(changed_jobs)
            else:
                _log(f"  ✗ Failed: {err_msg}")
                errors.append(f"{slug}: {err_msg}")
                with _audit_lock:
                    _audit_status["errors"] = errors[:]

            time.sleep(0.2)   # brief pause between Ollama calls

        # Save updated JSON files
        if changed_jobs:
            save_jobs_json(JOBS_JSON, jobs_raw)
            save_json(FLAT_JSON, flat_raw)
            _log(f"Saved updated jobs.json and formatted_jobs_flat.json.")

        # Batched git commit + push
        git_result = None
        if changed_jobs:
            _log("Running git add / commit / push…")
            git_result = _git_batch_commit_push(changed_jobs)
            _log(f"Git: {'; '.join(git_result.get('messages', []))}")
        else:
            _log("No changes — nothing to commit.")

        result = {
            "ok":          True,
            "total":       total,
            "changed":     len(changed_jobs),
            "errors":      errors,
            "model":       model,
            "git":         git_result,
            "changed_jobs": changed_jobs,
        }
        with _audit_lock:
            _audit_status["done"]    = True
            _audit_status["result"]  = result

        _log(f"Audit complete. {len(changed_jobs)} fix(es) applied.")

    except Exception as ex:
        import traceback
        msg = traceback.format_exc()
        print(f"  [audit] EXCEPTION:\n{msg}")
        with _audit_lock:
            _audit_status["running"] = False
            _audit_status["done"]    = True
            _audit_status["result"]  = {"ok": False, "error": str(ex)}
    finally:
        with _audit_lock:
            _audit_status["running"] = False


def api_auto_audit() -> dict:
    """Start the AI audit in a background thread (if not already running)."""
    with _audit_lock:
        if _audit_status["running"]:
            return {"ok": False, "error": "Audit is already running."}

    t = threading.Thread(target=_run_auto_audit_thread, daemon=True)
    t.start()
    return {"ok": True, "message": "AI audit started."}


def api_audit_status() -> dict:
    """Return a snapshot of the current audit status for polling."""
    with _audit_lock:
        return dict(_audit_status)


# ═══════════════════════════════════════════════════════════════════════════════
# ── HTTP server ────────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

class Handler(http.server.BaseHTTPRequestHandler):

    def log_message(self, fmt, *args):
        print(f"[server] {self.address_string()} — {fmt % args}")

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def send_html_file(self, path: Path):
        if not path.exists():
            self._send_404()
            return
        with open(path, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_404(self):
        self.send_response(404)
        self.end_headers()
        self.wfile.write(b"404 Not Found")

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path   = parsed.path.rstrip("/") or "/"

        if path in ("/", "/category-changer"):
            self.send_html_file(HTML_UI)
        elif path == "/api/jobs":
            self.send_json(api_get_jobs())
        elif path == "/api/categories":
            self.send_json(api_get_categories())
        elif path == "/api/history":
            self.send_json(load_change_log())
        elif path == "/api/audit_status":
            self.send_json(api_audit_status())
        else:
            self._send_404()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path   = parsed.path

        if path == "/api/change":
            length  = int(self.headers.get("Content-Length", 0))
            body    = self.rfile.read(length)
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                self.send_json({"ok": False, "error": "Invalid JSON"}, 400)
                return

            job_id       = payload.get("job_id", "")
            new_category = payload.get("new_category", "")

            if not job_id or not new_category:
                self.send_json({"ok": False, "error": "job_id and new_category are required"}, 400)
                return

            result = change_category(job_id, new_category)
            self.send_json(result, 200 if result["ok"] else 400)

        elif path == "/api/auto_audit":
            result = api_auto_audit()
            self.send_json(result, 200 if result["ok"] else 409)

        else:
            self._send_404()


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("=" * 60)
    print("   Category Manager — findjobsinfinland.fi")
    print("=" * 60)
    print(f"  Server  : http://localhost:{PORT}")
    print(f"  Root    : {ROOT_DIR}")
    print(f"  Jobs    : {JOBS_JSON}")
    print(f"  Ollama  : {OLLAMA_BASE_URL}")
    print("  UI      : http://localhost:8765")
    print("  Press Ctrl+C to stop.\n")

    server = http.server.HTTPServer(("localhost", PORT), Handler)

    # ── Auto-start AI audit immediately in a background thread ─────────────────
    print("[auto-audit] Starting AI category audit in background…")
    _audit_thread = threading.Thread(target=_run_auto_audit_thread, daemon=True)
    _audit_thread.start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
