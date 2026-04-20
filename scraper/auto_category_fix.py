"""
auto_category_fix.py — AI-powered automated job category auditor & fixer.

What it does:
  1. Loads all jobs from scraper/data/jobs.json
  2. Loads all valid category slugs from scraper/all_jobs_cat.json
  3. For every job, asks Ollama AI whether the current category is correct.
  4. If AI disagrees it suggests the correct category.
  5. Applies all changes:
       - scraper/data/jobs.json
       - scraper/data/formatted_jobs_flat.json
       - jobs/<category>/<slug>.html  (moved + patched)
       - jobs-table.html
  6. One batched git commit + push at the end.

Usage:
    python scraper/auto_category_fix.py

Requirements:
    Ollama running locally (https://ollama.com)  — no extra pip packages needed.
    Recommended model: llama3.2 or higher (auto-detected).
"""

import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

# ─── Paths ────────────────────────────────────────────────────────────────────
SCRIPT_DIR  = Path(__file__).parent
ROOT_DIR    = SCRIPT_DIR.parent
DATA_DIR    = SCRIPT_DIR / "data"
JOBS_JSON   = DATA_DIR   / "jobs.json"
FLAT_JSON   = DATA_DIR   / "formatted_jobs_flat.json"
CAT_JSON    = SCRIPT_DIR / "all_jobs_cat.json"
JOBS_DIR    = ROOT_DIR   / "jobs"
JOBS_TABLE  = ROOT_DIR   / "jobs-table.html"
CHANGES_LOG = DATA_DIR   / "category_changes_log.json"   # shared audit log

SITE_BASE        = "https://findjobsinfinland.fi"
OLLAMA_BASE_URL  = "http://localhost:11434"

# Models to try in preference order (best → fallback)
# llama3.1 8B is preferred over llama3.2 3B for better reasoning accuracy
PREFERRED_MODELS = [
    "llama3.1", "llama3.2", "llama3", "llama3:8b",
    "gemma3", "gemma2", "mistral", "phi3", "phi",
]

# ─── Logging helpers ───────────────────────────────────────────────────────────
def _c(code, text): return f"\033[{code}m{text}\033[0m"
def green(t):  return _c("92", t)
def yellow(t): return _c("93", t)
def red(t):    return _c("91", t)
def cyan(t):   return _c("96", t)
def bold(t):   return _c("1",  t)
def grey(t):   return _c("90", t)

def log(msg):   print(f"  {msg}")
def ok(msg):    print(f"  {green('✓')} {msg}")
def warn(msg):  print(f"  {yellow('⚠')} {msg}")
def err(msg):   print(f"  {red('✗')} {msg}")
def info(msg):  print(f"  {cyan('→')} {msg}")
def head(msg):  print(f"\n{bold(msg)}")

# ─── JSON helpers ──────────────────────────────────────────────────────────────
def load_json(path: Path):
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path: Path, data) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def append_change_log(entry: dict) -> None:
    """Append one change record to the shared persistent audit log."""
    import datetime
    existing = []
    if CHANGES_LOG.exists():
        try:
            with open(CHANGES_LOG, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            existing = []
    entry.setdefault("timestamp", datetime.datetime.now().isoformat(timespec="seconds"))
    existing.append(entry)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(CHANGES_LOG, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)
def flat_from_jobs(raw: list) -> list[dict]:
    """Flatten the grouped jobs.json into a simple list."""
    flat = []
    for item in raw:
        if isinstance(item, dict) and "jobs" in item:
            flat.extend(item["jobs"])
        elif isinstance(item, dict):
            flat.append(item)
    return flat

# ─── Ollama detection ──────────────────────────────────────────────────────────
def _ollama_get(path: str) -> dict | None:
    try:
        req = urllib.request.Request(f"{OLLAMA_BASE_URL}{path}")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read())
    except Exception:
        return None

def detect_best_model() -> str | None:
    """Return the best available Ollama model, or None if Ollama is offline."""
    resp = _ollama_get("/api/tags")
    if resp is None:
        return None
    available = [m["name"].split(":")[0] for m in resp.get("models", [])]
    if not available:
        return None
    for pref in PREFERRED_MODELS:
        for avail in available:
            if avail.lower().startswith(pref.lower()):
                # Return the full tag name
                full = next(m["name"] for m in resp["models"]
                            if m["name"].split(":")[0].lower() == avail.lower())
                return full
    # fallback: just use the first available model
    return resp["models"][0]["name"]

def ollama_generate(model: str, prompt: str, timeout: int = 60) -> str:
    """Send a non-streaming generate request to Ollama."""
    payload = json.dumps({
        "model":  model,
        "prompt": prompt,
        "stream": False,
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

# ─── AI category verification ──────────────────────────────────────────────────
_CATEGORY_PROMPT_TMPL = """\
You are a precise job classification engine. Your ONLY job is to output a single category slug.

TASK:
Determine the best category for this job from the VALID CATEGORIES list below.
If the CURRENT CATEGORY is already correct, output exactly: CORRECT
If the CURRENT CATEGORY is wrong, output ONLY the correct slug from the list (e.g. healthcare).

Do NOT explain. Do NOT add punctuation. Output one word or CORRECT.

---
Job Title      : {title}
Company        : {company}
Job Summary    : {description}
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
    valid_cats: list[str],
) -> str | None:
    """
    Returns:
        None           — current category is correct (AI said CORRECT)
        "<slug>"       — AI suggested this new category
    """
    cat_list = "\n".join(f"  - {c}" for c in valid_cats)
    prompt = _CATEGORY_PROMPT_TMPL.format(
        title=title,
        company=company,
        description=(description or "")[:500],   # keep token count low
        current_cat=current_cat,
        cat_list=cat_list,
    )
    try:
        response = ollama_generate(model, prompt)
    except Exception as ex:
        warn(f"Ollama error for '{title}': {ex}")
        return None  # treat as correct to be safe

    # Normalise response
    raw = response.strip().lower().split()[0] if response.strip() else ""
    raw = re.sub(r"[^a-z0-9\-]", "", raw)

    if raw == "correct" or not raw:
        return None

    # Validate it's actually in our list
    if raw in valid_cats:
        return raw

    # Fuzzy: see if it's a substring match of a valid cat
    for vc in valid_cats:
        if raw in vc or vc in raw:
            return vc

    # Not valid — ignore
    warn(f"AI returned unknown category '{raw}' for '{title}' — ignoring.")
    return None

# ─── Category change logic ─────────────────────────────────────────────────────
def _pick_image(new_category: str, old_image_url: str) -> str:
    """Random image from new category images folder, or keep old."""
    import random
    img_dir = ROOT_DIR / "images" / "jobs" / new_category
    if img_dir.exists():
        pngs = [p.name for p in img_dir.iterdir() if p.suffix.lower() == ".png"]
        if pngs:
            return f"{SITE_BASE}/images/jobs/{new_category}/{random.choice(pngs)}"
    return old_image_url

def apply_category_change(
    jobs_raw: list,
    flat_raw: list,
    job: dict,
    new_category: str,
) -> tuple[bool, str]:
    """
    Mutates jobs_raw and flat_raw in-place, patches + moves HTML, updates jobs-table.
    Returns (success, error_message).
    """
    old_category = job.get("job_category", "other")
    slug         = job.get("job_id", "")
    old_image    = job.get("image_url", "")

    old_html = JOBS_DIR / old_category / f"{slug}.html"
    new_html = JOBS_DIR / new_category / f"{slug}.html"

    if not old_html.exists():
        return False, f"HTML file not found: {old_html}"

    new_image_url = _pick_image(new_category, old_image)
    old_job_url   = f"{SITE_BASE}/jobs/{old_category}/{slug}"
    new_job_url   = f"{SITE_BASE}/jobs/{new_category}/{slug}"
    old_img_pfx   = f"{SITE_BASE}/images/jobs/{old_category}/"

    # ── 1. Patch jobs_raw ──────────────────────────────────────────────────
    for item in jobs_raw:
        bucket = item.get("jobs", [item]) if "jobs" in item else [item]
        for j in bucket:
            if j.get("job_id") == slug:
                j["job_category"] = new_category
                j["jobUrl"]       = new_job_url
                j["image_url"]    = new_image_url

    # ── 2. Patch flat_raw ──────────────────────────────────────────────────
    for j in flat_raw:
        if j.get("job_id") == slug:
            j["job_category"] = new_category
            j["jobUrl"]       = new_job_url
            j["image_url"]    = new_image_url

    # ── 3. Patch HTML file ─────────────────────────────────────────────────
    with open(old_html, "r", encoding="utf-8") as f:
        html = f.read()

    html = html.replace(old_job_url, new_job_url)
    html = re.sub(
        re.escape(old_img_pfx) + r"[\w\-\.]+",
        new_image_url,
        html,
    )
    html = html.replace(f"?category={old_category}", f"?category={new_category}")
    html = html.replace(
        f'itemprop="name">{_fmt_cat(old_category)}</span>',
        f'itemprop="name">{_fmt_cat(new_category)}</span>',
    )

    # ── 4. Move HTML file ──────────────────────────────────────────────────
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

    # ── 5. Patch jobs-table.html ───────────────────────────────────────────
    if JOBS_TABLE.exists():
        with open(JOBS_TABLE, "r", encoding="utf-8") as f:
            tbl = f.read()
        tbl = tbl.replace(old_job_url, new_job_url)
        tbl = re.sub(
            r'(data-title="[^"]*"[^>]*?data-category=")' + re.escape(old_category) + r'"',
            r'\g<1>' + new_category + '"',
            tbl,
        )
        tbl = tbl.replace(f">{_fmt_cat(old_category)}<", f">{_fmt_cat(new_category)}<")
        with open(JOBS_TABLE, "w", encoding="utf-8") as f:
            f.write(tbl)

    # ── 6. Write to shared audit log ────────────────────────────────
    append_change_log({
        "job_id":       job.get("job_id", ""),
        "title":        job.get("title", ""),
        "old_category": old_category,
        "new_category": new_category,
        "source":       "ai",
    })

    return True, ""

def _fmt_cat(slug: str) -> str:
    """'information-technology' → 'Information Technology'"""
    return slug.replace("-", " ").title()

# ─── Save helpers ──────────────────────────────────────────────────────────────
def save_jobs_json(path: Path, jobs_raw: list) -> None:
    json_str = json.dumps(jobs_raw, ensure_ascii=False, indent=2)
    json_str = json_str.replace("  },\n  {", "  },\n\n  {")
    with open(path, "w", encoding="utf-8") as f:
        f.write(json_str)

# ─── Git helpers ───────────────────────────────────────────────────────────────
def _git(args: list[str]) -> tuple[int, str, str]:
    r = subprocess.run(
        ["git"] + args, cwd=str(ROOT_DIR),
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return r.returncode, r.stdout.strip(), r.stderr.strip()

def git_commit_push(changed_jobs: list[dict]) -> None:
    head("\nStep 4 — Committing to Git")
    count = len(changed_jobs)

    code, out, err_txt = _git(["add", "-A"])
    log(f"git add: {out or err_txt or 'ok'}")

    if count == 1:
        msg = (f"fix: reclassify '{changed_jobs[0]['job_id']}' "
               f"to '{changed_jobs[0]['new_category']}'")
    else:
        slugs = ", ".join(j["job_id"] for j in changed_jobs[:5])
        if count > 5:
            slugs += f" … (+{count-5} more)"
        msg = f"fix: AI reclassified {count} job(s) — {slugs}"

    code, out, err_txt = _git(["commit", "-m", msg])
    log(f"git commit: {out or err_txt or 'ok'}")

    if "nothing to commit" in (out + err_txt).lower():
        ok("Nothing to commit — all files already up to date.")
        return

    code, out, err_txt = _git(["push"])
    if code == 0:
        ok(f"Pushed {count} change(s) to GitHub.")
    else:
        err(f"Push failed: {err_txt}")
    log(out or err_txt or "")

# ─── Main ──────────────────────────────────────────────────────────────────────
def main() -> None:
    # Force UTF-8 output on Windows
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    print()
    print("=" * 60)
    print("  Auto Category Fix  --  findjobsinfinland.fi")
    print("=" * 60)

    # ── Step 1: Load data ──────────────────────────────────────────────────
    head("Step 1 — Loading data")

    jobs_raw = load_json(JOBS_JSON)
    if jobs_raw is None:
        err(f"jobs.json not found at {JOBS_JSON}"); sys.exit(1)

    flat_raw = load_json(FLAT_JSON) or []
    all_cats_data = load_json(CAT_JSON)
    if not all_cats_data:
        err(f"all_jobs_cat.json not found at {CAT_JSON}"); sys.exit(1)

    valid_cats: list[str] = all_cats_data.get("categories", [])
    all_jobs = flat_from_jobs(jobs_raw)

    ok(f"Loaded {len(all_jobs)} job(s)")
    ok(f"Loaded {len(valid_cats)} valid categories")

    # ── Step 2: Detect Ollama model ────────────────────────────────────────
    head("Step 2 — Connecting to Ollama")

    model = detect_best_model()
    if model is None:
        err("Ollama is not running or has no models installed.")
        err("Start Ollama with:  ollama serve")
        err("Pull a model with:  ollama pull llama3.2")
        sys.exit(1)

    ok(f"Using model: {bold(model)}")

    # ── Step 3: Audit each job ────────────────────────────────────────────--
    head("Step 3 — AI category audit")

    changed_jobs: list[dict] = []
    errors:        list[str] = []

    for idx, job in enumerate(all_jobs, 1):
        title        = job.get("title", "Untitled")
        company      = job.get("company", "")
        description  = job.get("description", "")
        current_cat  = job.get("job_category", "other")
        slug         = job.get("job_id", "")

        prefix = f"[{idx:>3}/{len(all_jobs)}]"

        print()
        log(f"{grey(prefix)} {bold(title)}")
        log(f"         Company  : {grey(company)}")
        log(f"         Current  : {cyan(current_cat)}")

        suggested = ai_check_category(
            model=model,
            title=title,
            company=company,
            description=description,
            current_cat=current_cat,
            valid_cats=valid_cats,
        )

        if suggested is None:
            ok(f"         Category OK — no change needed.")
            continue

        if suggested == current_cat:
            ok(f"         Category OK — no change needed.")
            continue

        info(f"         AI suggests : {yellow(suggested)}  (was: {current_cat})")

        success, err_msg = apply_category_change(
            jobs_raw=jobs_raw,
            flat_raw=flat_raw,
            job=job,
            new_category=suggested,
        )

        if success:
            ok(f"         Changed '{current_cat}' -> '{suggested}'")
            changed_jobs.append({
                "job_id":       slug,
                "title":        title,
                "old_category": current_cat,
                "new_category": suggested,
            })
            # Update the in-memory job dict so later iterations are consistent
            job["job_category"] = suggested
        else:
            err(f"         Failed: {err_msg}")
            errors.append(f"{slug}: {err_msg}")

        time.sleep(0.2)   # brief pause between Ollama calls

    # ── Save updated JSON files ────────────────────────────────────────────
    if changed_jobs:
        save_jobs_json(JOBS_JSON, jobs_raw)
        save_json(FLAT_JSON, flat_raw)
        ok(f"Saved updated jobs.json and formatted_jobs_flat.json")

    # ── Step 4: Summary ────────────────────────────────────────────────────
    head("Summary")
    log(f"Total jobs   : {len(all_jobs)}")
    log(f"Unchanged    : {len(all_jobs) - len(changed_jobs) - len(errors)}")
    log(f"Fixed        : {green(str(len(changed_jobs)))}")
    if errors:
        log(f"Errors       : {red(str(len(errors)))}")
        for e in errors:
            log(f"  {red('!')} {e}")

    if changed_jobs:
        print()
        log("Changes made:")
        for c in changed_jobs:
            log(f"  {grey(c['job_id'])}")
            log(f"    {c['old_category']}  ->  {green(c['new_category'])}")

        # ── Step 4: Git commit + push ──────────────────────────────────────
        git_commit_push(changed_jobs)
    else:
        print()
        ok("All job categories are already correct. Nothing to commit.")

    print()
    print("=" * 60)
    print("  Done!")
    print("=" * 60)
    print()

if __name__ == "__main__":
    main()
