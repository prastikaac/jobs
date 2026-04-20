"""
category_changer.py — Local HTTP server for the Category Changer tool.

Usage:  python scraper/category_changer.py
        (run from the project root)

The server listens on http://localhost:8765
API endpoints:
  GET  /api/jobs          — returns all current jobs
  GET  /api/categories    — returns all valid categories
  GET  /api/history       — returns the change-log (for the debug panel)
  POST /api/change        — changes a job's category
  GET  /                  — serves category-changer.html
"""

import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.parse
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
SCRIPT_DIR  = Path(__file__).parent                        # .../scraper/
ROOT_DIR    = SCRIPT_DIR.parent                             # project root
DATA_DIR    = SCRIPT_DIR / "data"
JOBS_JSON   = DATA_DIR / "jobs.json"
FLAT_JSON   = DATA_DIR / "formatted_jobs_flat.json"
CAT_JSON    = SCRIPT_DIR / "all_jobs_cat.json"
JOBS_DIR     = ROOT_DIR / "jobs"                            # jobs/<category>/<slug>.html
JOBS_TABLE   = ROOT_DIR / "jobs-table.html"
HTML_UI      = ROOT_DIR / "category-changer.html"
CHANGES_LOG  = DATA_DIR / "category_changes_log.json"       # audit log

SITE_BASE   = "https://findjobsinfinland.fi"
PORT        = 8765

# ── Helper — load JSON ────────────────────────────────────────────────────────
def load_json(path: Path):
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: Path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ── Change-log helpers ────────────────────────────────────────────────────────
def load_change_log() -> list[dict]:
    return load_json(CHANGES_LOG) or []


def append_change_log(entry: dict) -> None:
    """Append one change record to the persistent audit log."""
    import datetime
    log = load_change_log()
    entry.setdefault("timestamp", datetime.datetime.now().isoformat(timespec="seconds"))
    log.append(entry)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    save_json(CHANGES_LOG, log)


# ── Helper — flatten jobs.json ────────────────────────────────────────────────
def flat_jobs_from_jobs_json(data) -> list[dict]:
    flat = []
    for item in data:
        if isinstance(item, dict) and "jobs" in item:
            flat.extend(item["jobs"])
        elif isinstance(item, dict):
            flat.append(item)
    return flat


# ── API: list jobs ────────────────────────────────────────────────────────────
def api_get_jobs() -> list[dict]:
    raw = load_json(JOBS_JSON)
    if raw is None:
        return []
    all_jobs = flat_jobs_from_jobs_json(raw)
    result = []
    for j in all_jobs:
        result.append({
            "id":           j.get("id", ""),
            "job_id":       j.get("job_id", ""),
            "title":        j.get("title", "Untitled"),
            "company":      j.get("company", ""),
            "job_category": j.get("job_category", "other"),
            "jobLocation":  j.get("jobLocation", []),
            "date_posted":  j.get("date_posted", ""),
            "jobUrl":       j.get("jobUrl", ""),
            "image_url":    j.get("image_url", ""),
        })
    return result


# ── API: list categories ──────────────────────────────────────────────────────
def api_get_categories() -> list[str]:
    data = load_json(CAT_JSON)
    if data and isinstance(data, dict):
        return data.get("categories", [])
    return []


# ── Core: change category ─────────────────────────────────────────────────────
def change_category(job_id: str, new_category: str) -> dict:
    """
    1. Find job in jobs.json and formatted_jobs_flat.json
    2. Update job_category, jobUrl, image_url in both JSON files
    3. Update all occurrences in the HTML file itself
    4. Move HTML file to new category folder
    5. Update jobs-table.html row
    6. git add + commit + push
    """
    # Load data
    jobs_raw = load_json(JOBS_JSON)
    flat_raw = load_json(FLAT_JSON) or []

    if jobs_raw is None:
        return {"ok": False, "error": "jobs.json not found"}

    # Find old category
    all_jobs = flat_jobs_from_jobs_json(jobs_raw)
    target_job = next((j for j in all_jobs if j.get("job_id") == job_id), None)
    if not target_job:
        return {"ok": False, "error": f"Job '{job_id}' not found in jobs.json"}

    old_category = target_job.get("job_category", "other")
    if old_category == new_category:
        return {"ok": False, "error": "New category is the same as the current category"}

    slug = target_job.get("job_id", "")  # e.g. information-security-manager-kuopio-bf9cadbd

    # --- 1. Locate the HTML file ---
    old_html = JOBS_DIR / old_category / f"{slug}.html"
    new_html_dir = JOBS_DIR / new_category
    new_html = new_html_dir / f"{slug}.html"

    if not old_html.exists():
        return {"ok": False, "error": f"HTML file not found: {old_html}"}

    # --- 2. Pick a random image from the new category images folder ---
    img_base = ROOT_DIR / "images" / "jobs" / new_category
    new_image_url = target_job.get("image_url", "")  # default: keep old
    if img_base.exists():
        imgs = [p.name for p in img_base.iterdir() if p.suffix.lower() == ".png"]
        if imgs:
            import random
            chosen = random.choice(imgs)
            new_image_url = f"{SITE_BASE}/images/jobs/{new_category}/{chosen}"

    # --- 3. Build old/new URL strings ---
    old_job_url = f"{SITE_BASE}/jobs/{old_category}/{slug}"
    new_job_url = f"{SITE_BASE}/jobs/{new_category}/{slug}"
    old_img_prefix = f"{SITE_BASE}/images/jobs/{old_category}/"
    new_img_prefix = f"{SITE_BASE}/images/jobs/{new_category}/"

    # --- 4. Update jobs.json ---
    for item in jobs_raw:
        if isinstance(item, dict) and "jobs" in item:
            for j in item["jobs"]:
                if j.get("job_id") == job_id:
                    j["job_category"] = new_category
                    j["jobUrl"] = new_job_url
                    j["image_url"] = new_image_url
        elif isinstance(item, dict) and item.get("job_id") == job_id:
            item["job_category"] = new_category
            item["jobUrl"] = new_job_url
            item["image_url"] = new_image_url

    with open(JOBS_JSON, "w", encoding="utf-8") as f:
        json_str = json.dumps(jobs_raw, ensure_ascii=False, indent=2)
        json_str = json_str.replace("  },\n  {", "  },\n\n  {")
        f.write(json_str)

    # --- 5. Update formatted_jobs_flat.json ---
    for j in flat_raw:
        if j.get("job_id") == job_id:
            j["job_category"] = new_category
            j["jobUrl"] = new_job_url
            j["image_url"] = new_image_url
    save_json(FLAT_JSON, flat_raw)

    # --- 6. Patch HTML file ---
    with open(old_html, "r", encoding="utf-8") as f:
        html_content = f.read()

    # Replace category-bearing URLs (canonical, og:url, og:image, etc.)
    html_content = html_content.replace(old_job_url, new_job_url)
    # Replace image paths under old category with new image
    html_content = re.sub(
        re.escape(old_img_prefix) + r'[\w\-\.]+',
        new_image_url,
        html_content
    )
    # Replace ?category=old_category query param in breadcrumb links etc.
    html_content = html_content.replace(
        f"?category={old_category}",
        f"?category={new_category}"
    )

    # --- 7. Move HTML file ---
    new_html_dir.mkdir(parents=True, exist_ok=True)
    with open(new_html, "w", encoding="utf-8") as f:
        f.write(html_content)
    old_html.unlink()

    # Remove old category folder if it's now empty
    if old_category != new_category:
        try:
            old_dir = JOBS_DIR / old_category
            if old_dir.exists() and not any(old_dir.iterdir()):
                old_dir.rmdir()
        except Exception:
            pass

    # --- 8. Update jobs-table.html ---
    _patch_jobs_table(slug, old_category, new_category, new_job_url, new_image_url)

    # --- 9. Write to change audit log ---
    append_change_log({
        "job_id":       slug,
        "title":        target_job.get("title", ""),
        "old_category": old_category,
        "new_category": new_category,
        "source":       "manual",
    })

    # --- 10. Git add + commit + push ---
    git_result = _git_commit_and_push(slug, old_category, new_category)

    return {
        "ok": True,
        "job_id": job_id,
        "old_category": old_category,
        "new_category": new_category,
        "new_url": new_job_url,
        "git": git_result,
    }


# ── Patch jobs-table.html ─────────────────────────────────────────────────────
def _patch_jobs_table(slug: str, old_cat: str, new_cat: str, new_url: str, new_img: str):
    if not JOBS_TABLE.exists():
        return
    with open(JOBS_TABLE, "r", encoding="utf-8") as f:
        content = f.read()

    old_job_url = f"{SITE_BASE}/jobs/{old_cat}/{slug}"
    content = content.replace(old_job_url, new_url)

    # Update data-category attribute for the row
    # Pattern: data-category="old_cat" inside the row containing the slug
    content = re.sub(
        r'(data-title="[^"]*"[^>]*?data-category=")' + re.escape(old_cat) + r'"',
        r'\g<1>' + new_cat + '"',
        content
    )

    # Update category badge text in jobs-table (capitalised display label)
    old_label = old_cat.replace("-", " ").title()
    new_label = new_cat.replace("-", " ").title()
    content = content.replace(f">{old_label}<", f">{new_label}<")

    with open(JOBS_TABLE, "w", encoding="utf-8") as f:
        f.write(content)


# ── Git helpers ───────────────────────────────────────────────────────────────
def _run_git(args: list[str]) -> tuple[int, str, str]:
    result = subprocess.run(
        ["git"] + args,
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True
    )
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def _git_commit_and_push(slug: str, old_cat: str, new_cat: str) -> dict:
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


# ── HTTP server ──────────────────────────────────────────────────────────────--
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
        path = parsed.path.rstrip("/") or "/"

        if path == "/" or path == "/category-changer":
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
        path = parsed.path

        if path == "/api/change":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            try:
                payload = json.loads(body)
            except json.JSONDecodeError:
                self.send_json({"ok": False, "error": "Invalid JSON"}, 400)
                return

            job_id      = payload.get("job_id", "")
            new_category = payload.get("new_category", "")

            if not job_id or not new_category:
                self.send_json({"ok": False, "error": "job_id and new_category are required"}, 400)
                return

            result = change_category(job_id, new_category)
            self.send_json(result, 200 if result["ok"] else 400)
        else:
            self._send_404()


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    # Reconfigure stdout to UTF-8 so logging works on all Windows terminals
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print("=" * 56)
    print("   Category Changer -- findjobsinfinland.fi")
    print("=" * 56)
    print(f"  Server : http://localhost:{PORT}")
    print(f"  Root   : {ROOT_DIR}")
    print(f"  Jobs   : {JOBS_JSON}")
    print("  Press Ctrl+C to stop.\n")

    server = http.server.HTTPServer(("localhost", PORT), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
