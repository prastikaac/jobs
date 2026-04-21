"""
category_changer.py — Manual Category Manager
           for findjobsinfinland.fi

Usage:  python scraper/category_cheanger.py
        (run from the project root)

The server listens on http://localhost:8765
API endpoints:
  GET  /api/jobs          — returns all current jobs
  GET  /api/categories    — returns all valid categories
  GET  /api/history       — returns the change-log (audit panel)
  POST /api/change        — manually change a single job's category
  GET  /                  — serves category-changer.html
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
import html_generator

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

# ═══════════════════════════════════════════════════════════════════════════════
# ── Shared helpers ─────────────────────────────────────────────────────────────
# ═══════════════════════════════════════════════════════════════════════════════

def load_json(path: Path):
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        # Avoid crashing if the file is 0 bytes or corrupted during pipeline writes
        return None


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
    img_dir = ROOT_DIR / "https://findjobsinfinland.fi/images" / "jobs" / new_category
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

    # Update index.html and jobs.html
    try:
        updated_all_jobs = flat_jobs_from_jobs_json(jobs_raw)
        html_generator.update_main_pages(updated_all_jobs)
    except Exception as exc:
        print("[category_changer] Failed to update main pages HTML:", exc)

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
    print("  UI      : http://localhost:8765")
    print("  Press Ctrl+C to stop.\n")

    server = http.server.HTTPServer(("localhost", PORT), Handler)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
