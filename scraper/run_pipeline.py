"""
run_pipeline.py — Post-scrape pipeline orchestrator.

Reads rawjobs.json and processing_state.json and runs:
  Phase 2 — Translation   : Argos translates Finnish → English (offline)
  Phase 3 — AI Formatting : Ollama formats translated text → structured extraction
  Phase 4 — Job Formatter : Python locks factual fields + builds final jobs
  Phase 5 — Site Gen      : HTML pages, images, Firebase alerts

Resume flags:
  (default)      — Resume from Phase 2 (Translation) onward
  --ai-only      — Resume from Phase 3 (AI Formatting) onward, skip Translation
  --format-only  — Resume from Phase 4 (Job Formatter) onward, skip Translation + AI
  --html-only    — Phase 5 (Site Gen) only, re-render HTML from existing formatted jobs

Maintenance:
  --cleanup      — Remove all intermediate data for jobs already saved in jobs.json
"""

import argparse
import json
import logging
import re
import subprocess
import sys
import os
import time
from datetime import date, datetime, timedelta

# ── Fix Windows console Unicode ───────────────────────────────────────────────
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("pipeline.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("pipeline")

# ── Ensure cwd is the scraper directory ──────────────────────────────────────
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import config
import jobs_store
import rawjobs_store
import job_translator
import ai_processor
import Job_formatter
import image_generator
import html_generator
import expiration
import firebase_client
import category_checker


# ══════════════════════════════════════════════════════════════════════════════
# CLEANUP HELPER
# ══════════════════════════════════════════════════════════════════════════════

def cleanup_completed_jobs(completed_ids: set[str] | None = None) -> int:
    """
    Remove completed jobs from all intermediate pipeline files.

    A job is considered "completed" when it exists in jobs.json.
    Its data is wiped from:
      - rawjobs.json
      - processing_state.json
      - translated_raw_jobs.json   (also aliased as translated_jobs.json)
      - formatted_jobs_flat.json
      - sent_alerts.json           (IDs list — keep, but entries are already IDs)
      - ai_field_issues.json

    Args:
        completed_ids: Optional explicit set of job IDs to clean up.
                       If None, all IDs present in jobs.json are used.

    Returns:
        Number of job IDs that were cleaned from at least one file.
    """
    # ── Determine which IDs are done ─────────────────────────────────────────
    if completed_ids is None:
        completed_ids = {str(j.get("id")) for j in jobs_store.load_jobs() if j.get("id")}

    if not completed_ids:
        logger.info("[cleanup] No completed job IDs found in jobs.json — nothing to clean.")
        return 0

    logger.info("[cleanup] Cleaning %d completed job IDs from intermediate files.", len(completed_ids))
    cleaned_count = 0

    # ── rawjobs.json ─────────────────────────────────────────────────────────
    raw_jobs = rawjobs_store.load_raw_jobs()
    before = len(raw_jobs)
    raw_jobs = [j for j in raw_jobs if str(j.get("id", "")) not in completed_ids]
    if len(raw_jobs) < before:
        rawjobs_store.save_raw_jobs(raw_jobs)
        removed = before - len(raw_jobs)
        logger.info("[cleanup] rawjobs.json: removed %d entries.", removed)
        cleaned_count += removed

    # ── processing_state.json ────────────────────────────────────────────────
    processing_state = rawjobs_store.load_processing_state()
    before = len(processing_state)
    processing_state = {k: v for k, v in processing_state.items() if str(k) not in completed_ids}
    if len(processing_state) < before:
        rawjobs_store.save_processing_state(processing_state)
        removed = before - len(processing_state)
        logger.info("[cleanup] processing_state.json: removed %d entries.", removed)
        cleaned_count += removed

    # ── translated_raw_jobs.json (also covers translated_jobs.json alias) ────
    translated_raw = jobs_store.load_translated_raw_jobs()
    before = len(translated_raw)
    translated_raw = [j for j in translated_raw if str(j.get("id", "")) not in completed_ids]
    if len(translated_raw) < before:
        jobs_store.save_translated_raw_jobs(translated_raw)
        removed = before - len(translated_raw)
        logger.info("[cleanup] translated_raw_jobs.json: removed %d entries.", removed)
        cleaned_count += removed

    # ── formatted_jobs_flat.json ─────────────────────────────────────────────
    flat_jobs = jobs_store.load_formatted_jobs_flat()
    before = len(flat_jobs)
    flat_jobs = [j for j in flat_jobs if str(j.get("id", "")) not in completed_ids]
    if len(flat_jobs) < before:
        jobs_store.save_formatted_jobs_flat(flat_jobs)
        removed = before - len(flat_jobs)
        logger.info("[cleanup] formatted_jobs_flat.json: removed %d entries.", removed)
        cleaned_count += removed

    # ── sent_alerts.json (stored as a list of ID strings) ───────────────────
    sent_alerts_path = config.SENT_ALERTS_PATH
    if os.path.exists(sent_alerts_path):
        try:
            with open(sent_alerts_path, "r", encoding="utf-8") as f:
                sent_alerts = json.load(f)
            if isinstance(sent_alerts, list):
                before = len(sent_alerts)
                # Keep alert history for completed jobs (they already fired), so
                # we only remove IDs that are NOT in jobs.json anymore (safety net).
                # Actually per the user requirement we DO remove them from sent_alerts too.
                sent_alerts = [aid for aid in sent_alerts if str(aid) not in completed_ids]
                if len(sent_alerts) < before:
                    with open(sent_alerts_path, "w", encoding="utf-8") as f:
                        json.dump(sorted(sent_alerts), f, indent=2)
                    removed = before - len(sent_alerts)
                    logger.info("[cleanup] sent_alerts.json: removed %d entries.", removed)
                    cleaned_count += removed
        except Exception as exc:
            logger.warning("[cleanup] Could not clean sent_alerts.json: %s", exc)

    # ── ai_field_issues.json ─────────────────────────────────────────────────
    ai_issues_path = os.path.join(config.DATA_DIR, "ai_field_issues.json")
    if os.path.exists(ai_issues_path):
        try:
            with open(ai_issues_path, "r", encoding="utf-8") as f:
                ai_issues = json.load(f)
            if isinstance(ai_issues, list):
                before = len(ai_issues)
                ai_issues = [item for item in ai_issues if str(item.get("id", "")) not in completed_ids]
                if len(ai_issues) < before:
                    with open(ai_issues_path, "w", encoding="utf-8") as f:
                        json.dump(ai_issues, f, ensure_ascii=False, indent=2)
                    removed = before - len(ai_issues)
                    logger.info("[cleanup] ai_field_issues.json: removed %d entries.", removed)
                    cleaned_count += removed
            elif isinstance(ai_issues, dict):
                before = len(ai_issues)
                ai_issues = {k: v for k, v in ai_issues.items() if str(k) not in completed_ids}
                if len(ai_issues) < before:
                    with open(ai_issues_path, "w", encoding="utf-8") as f:
                        json.dump(ai_issues, f, ensure_ascii=False, indent=2)
                    removed = before - len(ai_issues)
                    logger.info("[cleanup] ai_field_issues.json: removed %d entries.", removed)
                    cleaned_count += removed
        except Exception as exc:
            logger.warning("[cleanup] Could not clean ai_field_issues.json: %s", exc)

    logger.info("[cleanup] Done. Total entries removed across all files: %d", cleaned_count)
    return cleaned_count


def cmd_cleanup() -> None:
    """Standalone command: clean all intermediate data for jobs already in jobs.json."""
    logger.info("── Cleanup: removing completed job data from intermediate files ──")
    n = cleanup_completed_jobs()
    print(f"Cleanup complete. {n} total entries removed from intermediate files.")


# ══════════════════════════════════════════════════════════════════════════════
# UTILITY COMMANDS
# ══════════════════════════════════════════════════════════════════════════════

def _load_grouped_jobs_file() -> list[dict]:
    if not os.path.exists(config.JOBS_JSON_PATH):
        return []
    try:
        with open(config.JOBS_JSON_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except Exception:
        return []


def cmd_check_expires() -> None:
    data = _load_grouped_jobs_file()
    jobs = [j for s in data for j in s.get("jobs", [])] if data else []
    print(f"Total jobs: {len(jobs)}")
    for j in jobs[-5:]:
        print(
            f"  posted={j.get('date_posted')}  "
            f"expires={j.get('date_expires')}  "
            f"title={j.get('title', '')[:40]}"
        )


def cmd_check_db() -> None:
    try:
        firebase_client.init_firebase()
        db = firebase_client._db
        collection = config.FIREBASE_ALERT_COLLECTION

        print("Connecting to Firebase project...")
        print(f"Collection: {collection}")

        docs = db.collection(collection).get()
        doc_list = list(docs)
        print(f"TOTAL DOCUMENTS: {len(doc_list)}")

        for i, doc in enumerate(doc_list[:10]):
            data = doc.to_dict()
            print(f"  {i + 1}. ID: {doc.id} | Title: {data.get('title')}")

    except Exception as exc:
        print(f"ERROR: {exc}")
        import traceback
        traceback.print_exc()


def _fix_title_and_date(job: dict) -> dict:
    title = job.get("title", "")
    if title.isupper() or title.islower():
        job["title"] = title.capitalize()

    raw_posted = job.get("date_posted", "")
    if re.match(r"^\d{1,2}\.\d{1,2}\.(\d{4})?$", raw_posted):
        parts = raw_posted.rstrip(".").split(".")
        day, month = int(parts[0]), int(parts[1])
        year = int(parts[2]) if len(parts) > 2 and parts[2] else date.today().year
        try:
            job["date_posted"] = datetime(year, month, day).strftime("%Y-%m-%d")
        except Exception:
            pass

    return job


def cmd_fix_dates() -> None:
    data = _load_grouped_jobs_file()
    all_jobs = []

    for session in data:
        for i, job in enumerate(session.get("jobs", [])):
            session["jobs"][i] = _fix_title_and_date(job)
            all_jobs.append(session["jobs"][i])

    with open(config.JOBS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    html_generator.generate_job_pages(all_jobs)
    html_generator.update_main_pages(all_jobs)
    html_generator.update_sitemap(all_jobs)

    print(f"Fixed {len(all_jobs)} jobs — dates, titles, and HTML regenerated.")


_CATEGORY_PRIORITY = [
    "Cleaning", "Restaurant", "Caregiver", "Driver", "Logistics",
    "Security", "IT", "Sales", "Construction", "Hospitality", "Other",
]


def _best_category(cats: list) -> str:
    if not cats:
        return "Other"
    for priority_cat in _CATEGORY_PRIORITY:
        if priority_cat in cats:
            return priority_cat
    return cats[0]


def _parse_finnish_date(posted: str) -> datetime | None:
    posted = str(posted).strip()
    m = re.match(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})?$", posted)
    if m:
        day, month = int(m.group(1)), int(m.group(2))
        year = int(m.group(3)) if m.group(3) else date.today().year
        try:
            return datetime(year, month, day)
        except ValueError:
            return None
    try:
        return datetime.strptime(posted[:10], "%Y-%m-%d")
    except Exception:
        return None


def _migrate_job(job: dict) -> dict:
    cats = job.get("jobCategory", ["Other"])
    if isinstance(cats, list):
        job["jobCategory"] = _best_category(cats)

    if not job.get("date_expires"):
        posted_dt = _parse_finnish_date(job.get("date_posted", ""))
        if posted_dt:
            job["date_expires"] = (posted_dt + timedelta(days=60)).strftime("%Y-%m-%d")
        else:
            job["date_expires"] = (date.today() + timedelta(days=60)).strftime("%Y-%m-%d")

    if not job.get("salary"):
        job["salary"] = "Competitive hourly wage based on Finnish collective agreements"

    if not job.get("jobApplyLink"):
        job["jobApplyLink"] = job.get("jobLink", "")

    cat_slug = job["jobCategory"].lower().replace(" ", "-")
    job_id = job.get("id")
    job["jobUrl"] = f"/jobs/{cat_slug}/{job_id}/"
    job["image_url"] = f"{config.GITHUB_PAGES_BASE_URL}/jobs/{cat_slug}/{job_id}/image.png"

    return job


def cmd_migrate() -> None:
    data = _load_grouped_jobs_file()
    total = 0

    for session in data:
        for i, job in enumerate(session.get("jobs", [])):
            session["jobs"][i] = _migrate_job(job)
            total += 1

    with open(config.JOBS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"Migrated {total} jobs in {len(data)} session(s).")


def cmd_reset() -> None:
    raw_jobs = rawjobs_store.load_raw_jobs()
    state = rawjobs_store.load_processing_state()
    state = rawjobs_store.reset_processing_state(raw_jobs, state=state, reset_translation=True)

    for job in raw_jobs:
        job.pop("translated_content", None)

    rawjobs_store.save_raw_jobs(raw_jobs)
    rawjobs_store.save_processing_state(state)
    jobs_store.save_formatted_jobs_flat([])
    jobs_store.save_jobs([])

    if os.path.exists(config.TRANSLATED_RAW_JOBS_JSON_PATH):
        with open(config.TRANSLATED_RAW_JOBS_JSON_PATH, "w", encoding="utf-8") as f:
            json.dump([], f, ensure_ascii=False, indent=2)

    print(f"Reset {len(raw_jobs)} raw jobs, cleared processing state, and emptied job outputs.")


_TITLE_PATCHES = {
    "Kattomyyjä & Asiakashankkija": "Roofing Sales Representative & Customer Acquisition Specialist",
    "Haussa myyjiä Helsinkiin, Tampereelle ja Turkuun": "Sales Representatives for Helsinki, Tampere and Turku",
}


def cmd_patch_titles() -> None:
    jobs_data = _load_grouped_jobs_file()

    patched = 0
    all_jobs = []
    for session in jobs_data:
        for job in session.get("jobs", []):
            title = job.get("title", "")
            for fi_title, en_title in _TITLE_PATCHES.items():
                if fi_title in title:
                    job["title"] = en_title
                    patched += 1
            all_jobs.append(job)

    with open(config.JOBS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(jobs_data, f, ensure_ascii=False, indent=2)

    html_generator.generate_job_pages(all_jobs)
    html_generator.update_main_pages(all_jobs)

    print(f"Patched {patched} title(s). Regenerated HTML for {len(all_jobs)} jobs.")


def cmd_schedule() -> None:
    try:
        import schedule as schedule_lib
    except ImportError:
        print("ERROR: 'schedule' package not installed. Run: pip install schedule")
        sys.exit(1)

    sched_logger = logging.getLogger("scheduler")

    def _run_scrape():
        sched_logger.info(">>> Scheduled pipeline run triggered")
        try:
            run()
            sched_logger.info(">>> Pipeline run complete")
        except Exception as exc:
            sched_logger.error(">>> Pipeline run failed: %s", exc, exc_info=True)

    sched_logger.info("Running first pipeline run immediately...")
    _run_scrape()

    schedule_lib.every(1).hours.do(_run_scrape)
    sched_logger.info("Scheduler active — next run in 1 hour. Press Ctrl+C to stop.")

    while True:
        schedule_lib.run_pending()
        time.sleep(30)


# ══════════════════════════════════════════════════════════════════════════════
# PIPELINE
# ══════════════════════════════════════════════════════════════════════════════

def sync_category_dirs() -> None:
    import shutil

    for parent in [config.IMAGES_JOBS_DIR, config.JOBS_OUTPUT_DIR]:
        if not os.path.exists(parent):
            continue

        for dirname in os.listdir(parent):
            full_path = os.path.join(parent, dirname)
            if os.path.isdir(full_path) and "_" in dirname:
                new_name = dirname.replace("_", "-")
                new_path = os.path.join(parent, new_name)

                if os.path.exists(new_path) and new_path != full_path:
                    logger.info("Merging %s into %s", dirname, new_name)
                    for item in os.listdir(full_path):
                        shutil.move(
                            os.path.join(full_path, item),
                            os.path.join(new_path, item),
                        )
                    os.rmdir(full_path)
                else:
                    logger.info("Renaming category dir: %s -> %s", dirname, new_name)
                    os.rename(full_path, new_path)


def _load_phase2_input_jobs(raw_jobs: list[dict], ai_only: bool) -> list[dict]:
    if ai_only:
        translated_raw_jobs = jobs_store.load_translated_raw_jobs()
        return translated_raw_jobs if translated_raw_jobs else raw_jobs
    return raw_jobs


_AI_DATA_FIELDS = {
    "title", "description", "formatted_description", "meta_description",
    "job_responsibilities", "what_we_expect", "what_we_offer",
    "search_keywords", "job_category", "job_location", "job_regions",
}


def _inject_ai_data(jobs: list[dict]) -> list[dict]:
    """Wrap embedded AI fields back into an 'ai_data' sub-dict so that
    Job_formatter.format_jobs() takes the correct branch (not the translate fallback)."""
    result = []
    for job in jobs:
        j = dict(job)
        if "ai_data" not in j:
            j["ai_data"] = {k: j[k] for k in _AI_DATA_FIELDS if k in j}
        result.append(j)
    return result


def cmd_format_only() -> None:
    """Phase 4+5: run Job Formatter on all AI-processed jobs, then regenerate HTML/sitemap.

    Use this to resume the pipeline after Phase 3 (AI Formatting) completed.
    Reads translated_raw_jobs.json, finds jobs not yet in formatted_jobs_flat.json,
    runs Job_formatter (Phase 4) on them, then rebuilds the full site (Phase 5).
    """
    translated_raw_jobs = jobs_store.load_translated_raw_jobs()
    if not translated_raw_jobs:
        logger.error("--format-only: No AI-processed jobs found in translated_raw_jobs.json. Run Phase 3 first.")
        return

    processing_state = rawjobs_store.load_processing_state()
    existing_jobs = jobs_store.load_formatted_jobs_flat()
    if not existing_jobs:
        existing_jobs = jobs_store.load_jobs()

    # Find jobs that are AI-processed but not yet formatted
    already_formatted_ids = {j.get("id") for j in existing_jobs if j.get("id")}
    to_format = [
        j for j in translated_raw_jobs
        if processing_state.get(j.get("id"), {}).get("ai_processed", False)
        and j.get("id") not in already_formatted_ids
    ]

    if not to_format:
        logger.info("--format-only: All AI-processed jobs are already formatted. Re-generating HTML from existing data.")
        all_jobs = existing_jobs
        new_jobs_to_alert = []
    else:
        logger.info("── Format-Only Mode: Running Job Formatter on %d unformatted AI-processed jobs ──", len(to_format))
        # Inject ai_data so format_jobs() uses the correct branch (avoids translation fallback)
        to_format_with_ai = _inject_ai_data(to_format)
        newly_formatted = Job_formatter.format_jobs(to_format_with_ai)
        logger.info("  Job Formatter complete. Formatted: %d jobs", len(newly_formatted))

        for job in newly_formatted:
            Job_formatter.apply_manual_fixes(job)

        all_jobs, new_jobs_list = jobs_store.merge_new_jobs(existing_jobs, newly_formatted)
        new_jobs_to_alert = newly_formatted
        logger.info("  Merged: %d new jobs added (total: %d)", len(new_jobs_list), len(all_jobs))

    logger.info("── Format-Only Mode: Running Phase 5 (Site Generation) for %d total jobs ──", len(all_jobs))
    image_generator.generate_images_for_jobs(all_jobs)
    html_generator.generate_job_pages(all_jobs)
    html_generator.update_main_pages(all_jobs)
    html_generator.update_sitemap(all_jobs)
    jobs_store.save_formatted_jobs_flat(all_jobs)
    jobs_store.save_jobs(all_jobs)

    # Firebase alerts
    try:
        firebase_client.init_firebase()
        alert_count = firebase_client.send_new_job_alerts(new_jobs_to_alert, dry_run=False)
        logger.info("  Firebase alerts sent: %d", alert_count)
    except Exception as exc:
        logger.error("Firebase alert error: %s", exc)

    # Cleanup intermediate files for all jobs now in jobs.json
    logger.info("── Format-Only Mode: Cleaning up completed jobs from intermediate files ──")
    cleanup_completed_jobs()

    # Git commit + push
    _git_commit_and_push(message=f"Auto-update jobs [format-only] [+{len(new_jobs_to_alert)} new]")

    logger.info("── Format-Only Mode complete. %d total jobs rendered. ──", len(all_jobs))


def cmd_html_only() -> None:
    """Phase 5 only: regenerate HTML/sitemap from already-formatted jobs, no AI or translation."""
    all_jobs = jobs_store.load_formatted_jobs_flat()
    if not all_jobs:
        all_jobs = jobs_store.load_jobs()
    if not all_jobs:
        logger.error("--html-only: No formatted jobs found in formatted_jobs_flat.json or jobs.json. Run the full pipeline first.")
        return

    logger.info("── HTML-Only Mode: Regenerating site for %d jobs ──", len(all_jobs))
    image_generator.generate_images_for_jobs(all_jobs)
    html_generator.generate_job_pages(all_jobs)
    html_generator.update_main_pages(all_jobs)
    html_generator.update_sitemap(all_jobs)
    jobs_store.save_formatted_jobs_flat(all_jobs)
    jobs_store.save_jobs(all_jobs)
    logger.info("── HTML-Only Mode complete. %d jobs rendered. ──", len(all_jobs))


def run(dry_run: bool = False, ai_only: bool = False, reset_raw: bool = False) -> None:
    logger.info("=" * 60)
    logger.info("PIPELINE STARTED  (dry_run=%s, ai_only=%s)", dry_run, ai_only)
    logger.info("=" * 60)

    # ── Load stores ───────────────────────────────────────────────────────────
    logger.info("── Loading stores ──")
    raw_jobs = rawjobs_store.load_raw_jobs()
    processing_state = rawjobs_store.ensure_processing_state(raw_jobs, rawjobs_store.load_processing_state())
    existing_jobs = jobs_store.load_formatted_jobs_flat()
    if not existing_jobs:
        existing_jobs = jobs_store.load_jobs()

    logger.info(
        "Raw jobs: %d | Processing state entries: %d | Active formatted jobs: %d",
        len(raw_jobs), len(processing_state), len(existing_jobs),
    )

    # ── Reset if requested ────────────────────────────────────────────────────
    if reset_raw:
        logger.info("── Resetting processing state for all raw jobs ──")
        processing_state = rawjobs_store.reset_processing_state(raw_jobs, state=processing_state, reset_translation=True)

        for rj in raw_jobs:
            rj.pop("translated_content", None)

        if not dry_run:
            rawjobs_store.save_raw_jobs(raw_jobs)
            rawjobs_store.save_processing_state(processing_state)
            jobs_store.save_translated_raw_jobs([])
            jobs_store.save_formatted_jobs_flat([])

    if not dry_run:
        sync_category_dirs()

    # ── Expire old jobs ───────────────────────────────────────────────────────
    if not dry_run:
        logger.info("── Expiring old jobs ──")
        existing_jobs, expired = expiration.remove_expired_jobs(existing_jobs)
        logger.info("Removed %d expired jobs. Active: %d", len(expired), len(existing_jobs))
        
        if expired:
            expired_ids = {j.get("id") for j in expired if j.get("id")}
            if expired_ids:
                logger.info("Removing %d expired jobs from raw/processing stores", len(expired_ids))
                
                # Update rawjobs
                raw_jobs = [rj for rj in raw_jobs if rj.get("id") not in expired_ids]
                rawjobs_store.save_raw_jobs(raw_jobs)
                
                # Update processing state
                processing_state = {k: v for k, v in processing_state.items() if k not in expired_ids}
                rawjobs_store.save_processing_state(processing_state)
                
                # Update translated internal jobs
                translated_raw_jobs = jobs_store.load_translated_raw_jobs()
                if translated_raw_jobs:
                    translated_raw_jobs = [rj for rj in translated_raw_jobs if rj.get("id") not in expired_ids]
                    jobs_store.save_translated_raw_jobs(translated_raw_jobs)

    # ─────────────────────────────────────────────────────────────────────────
    # PHASE 2 — Translation
    # ─────────────────────────────────────────────────────────────────────────
    translated_raw_jobs = []

    if not dry_run and not ai_only:
        logger.info("═" * 60)
        logger.info("── Phase 2: Argos Translation ──")

        phase2_input = _load_phase2_input_jobs(raw_jobs, ai_only=False)
        raw_jobs = job_translator.run_phase2(phase2_input)

        translated_raw_jobs = jobs_store.load_translated_raw_jobs()
        if not translated_raw_jobs:
            translated_raw_jobs = raw_jobs

        logger.info("Phase 2 complete. Translated raw jobs available: %d", len(translated_raw_jobs))
    elif not dry_run and ai_only:
        translated_raw_jobs = jobs_store.load_translated_raw_jobs()
        if not translated_raw_jobs:
            logger.warning("AI-only mode requested but translated_raw_jobs.json is empty. Falling back to rawjobs.")
            translated_raw_jobs = raw_jobs
    else:
        logger.info("[DRY-RUN] Skipping Phase 2 (translation).")
        translated_raw_jobs = jobs_store.load_translated_raw_jobs() or raw_jobs

    # Refresh processing state after Phase 2
    processing_state = rawjobs_store.ensure_processing_state(translated_raw_jobs, processing_state)
    translated_raw_jobs_with_state = rawjobs_store.attach_processing_state(translated_raw_jobs, processing_state)

    # ─────────────────────────────────────────────────────────────────────────
    # PHASE 3 → 4 → 5 — Batched AI + Format + HTML + Git commit loop
    # ─────────────────────────────────────────────────────────────────────────
    all_jobs = existing_jobs
    total_actually_new: list[dict] = []
    total_img_count = 0
    total_alert_count = 0
    batch_size = config.PIPELINE_COMMIT_BATCH_SIZE

    if not dry_run:
        pending_jobs = rawjobs_store.get_unprocessed_jobs(translated_raw_jobs_with_state, processing_state)
        pending_jobs.sort(key=lambda j: j.get("retry_count", 0))
        total_pending = len(pending_jobs)

        logger.info("═" * 60)
        logger.info(
            "── Phase 3–5: Batched processing (%d unprocessed, batch=%d) ──",
            total_pending, batch_size,
        )

        batch_num = 0
        processed_so_far = 0

        while True:
            # Refresh pending list each iteration (state updated in-place)
            processing_state = rawjobs_store.ensure_processing_state(translated_raw_jobs, processing_state)
            translated_raw_jobs_with_state = rawjobs_store.attach_processing_state(translated_raw_jobs, processing_state)
            pending_jobs = rawjobs_store.get_unprocessed_jobs(translated_raw_jobs_with_state, processing_state)
            pending_jobs.sort(key=lambda j: j.get("retry_count", 0))

            if not pending_jobs:
                logger.info("Phase 3: No more unprocessed jobs. Batched loop complete.")
                break

            batch_num += 1
            chunk = pending_jobs[:batch_size]
            logger.info(
                "═" * 60
            )
            logger.info(
                "── Batch %d: AI formatting %d job(s) (total done so far: %d/%d) ──",
                batch_num, len(chunk), processed_so_far, total_pending,
            )

            # ── Phase 3: AI on this chunk ─────────────────────────────────
            newly_processed_translated, updated_translated_jobs = ai_processor.format_translated_jobs(
                chunk,
                batch_size=len(chunk),
            )
            processed_so_far += len(chunk)

            processing_state = rawjobs_store.sync_processing_state_from_jobs(updated_translated_jobs, processing_state)
            rawjobs_store.save_processing_state(processing_state)
            jobs_store.save_translated_raw_jobs(translated_raw_jobs)

            # ── Phase 4: Python formatter ─────────────────────────────────
            logger.info("── Batch %d / Phase 4: Job Formatter ──", batch_num)
            newly_formatted_batch = Job_formatter.format_jobs(newly_processed_translated)
            logger.info("Batch %d Phase 4 complete. Formatted: %d jobs", batch_num, len(newly_formatted_batch))

            if newly_formatted_batch:
                all_jobs, batch_actually_new = jobs_store.merge_new_jobs(all_jobs, newly_formatted_batch)
                total_actually_new.extend(batch_actually_new)
                logger.info("Batch %d: Actually new (post-merge dedup): %d", batch_num, len(batch_actually_new))
            else:
                batch_actually_new = []

            # Maintenance fixes — only apply to newly formatted jobs, not all 800+ existing ones
            for job in newly_formatted_batch:
                Job_formatter.apply_manual_fixes(job)

            # Saving to disk will happen after image generation to ensure image_urls are saved

            # ── Phase 5: Site Generation ──────────────────────────────────
            logger.info("── Batch %d / Phase 5: Site Generation ──", batch_num)

            if newly_formatted_batch:
                batch_img_count = image_generator.generate_images_for_jobs(newly_formatted_batch)
                total_img_count += batch_img_count
                logger.info("  Batch %d images generated: %d", batch_num, batch_img_count)

                batch_page_count = html_generator.generate_job_pages(newly_formatted_batch)
                logger.info("  Batch %d pages generated: %d", batch_num, batch_page_count)

            html_generator.update_main_pages(all_jobs)
            html_generator.update_sitemap(all_jobs)
            jobs_store.save_formatted_jobs_flat(all_jobs)
            rawjobs_store.save_raw_jobs(raw_jobs)
            jobs_store.save_jobs(all_jobs)

            # Firebase alerts for this batch
            if batch_actually_new:
                try:
                    firebase_client.init_firebase()
                    batch_alert_count = firebase_client.send_new_job_alerts(batch_actually_new, dry_run=False)
                    total_alert_count += batch_alert_count
                    logger.info("  Batch %d Firebase alerts sent: %d", batch_num, batch_alert_count)
                except Exception as exc:
                    logger.error("Firebase alert error in batch %d: %s", batch_num, exc)

            # ── Git commit + push for this batch ──────────────────────────
            logger.info("── Batch %d: Committing and pushing to GitHub ──", batch_num)
            _git_commit_and_push(
                message=f"Auto-update jobs batch {batch_num} [+{len(batch_actually_new)} new]"
            )

    else:
        logger.info("[DRY-RUN] Skipping Phase 3 / Phase 4 / Phase 5.")

    # ── Cleanup: remove all completed jobs from intermediate files (once, after all batches) ──
    if not dry_run and total_actually_new:
        logger.info("── Post-pipeline cleanup: removing completed job data from intermediate files ──")
        cleanup_completed_jobs()

    # ── Final summary ─────────────────────────────────────────────────────────
    _print_summary(all_jobs, total_actually_new, total_img_count, total_alert_count)


def _git_commit_and_push(message: str) -> None:
    """Run git add → commit → push from the repo root. Failures are logged, not raised."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    files_to_add = [
        "index.html",
        "jobs.html",
        "sitemap.xml",
        "sitemap-jobs.xml",
        "sitemap-pages.xml",
        "sitemap-blogs.xml",
        "jobs/",
        "images/jobs/",
        "scraper/data/jobs.json",
        "scraper/data/rawjobs.json",
        "scraper/data/formatted_jobs_flat.json",
        "scraper/data/processing_state.json",
    ]

    try:
        subprocess.run(
            ["git", "add"] + files_to_add,
            cwd=repo_root,
            check=True,
            capture_output=True,
        )
        result = subprocess.run(
            ["git", "commit", "-m", message],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            if "nothing to commit" in result.stdout or "nothing to commit" in result.stderr:
                logger.info("Git: nothing new to commit in this batch — skipping push.")
                return
            logger.warning("Git commit failed: %s", result.stderr.strip())
            return

        push_result = subprocess.run(
            ["git", "push", "origin", "main"],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        if push_result.returncode == 0:
            logger.info("Git push successful: %s", message)
        else:
            logger.warning("Git push failed: %s", push_result.stderr.strip())

    except Exception as exc:
        logger.warning("Git commit+push error: %s", exc)


def _finalize(all_jobs: list[dict]) -> None:
    html_generator.update_main_pages(all_jobs)
    html_generator.update_sitemap(all_jobs)
    jobs_store.save_formatted_jobs_flat(all_jobs)
    jobs_store.save_jobs(all_jobs)


def _print_summary(all_jobs, new_jobs, img_count, alert_count):
    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETE")
    logger.info("  Total active jobs  : %d", len(all_jobs))
    logger.info("  New jobs formatted : %d", len(new_jobs))
    logger.info("  Images generated   : %d", img_count)
    logger.info("  Firebase alerts    : %d", alert_count)
    logger.info("=" * 60)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Job aggregator pipeline + utility commands",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--dry-run", action="store_true",
        help="Run pipeline without disk writes or Firebase writes",
    )
    parser.add_argument(
        "--ai-only", action="store_true",
        help="Skip translation and only run AI processing + formatter + site generation",
    )
    parser.add_argument(
        "--format-only", action="store_true",
        help="Resume after Phase 3: run Job Formatter (Phase 4) + Site Gen (Phase 5) on AI-processed jobs",
    )
    parser.add_argument(
        "--html-only", action="store_true",
        help="Phase 5 only: re-render HTML/sitemap from existing formatted_jobs_flat.json",
    )
    parser.add_argument(
        "--reset-raw", action="store_true",
        help="Reset all raw jobs to untranslated/unprocessed before running",
    )

    parser.add_argument(
        "--check-expires", action="store_true",
        help="Print expiry/date stats for the last 5 jobs in jobs.json and exit",
    )
    parser.add_argument(
        "--check-db", action="store_true",
        help="Connect to Firebase and print document count + first 10 IDs, then exit",
    )
    parser.add_argument(
        "--fix-dates", action="store_true",
        help="Fix title casing + Finnish date formats in jobs.json, regenerate HTML, then exit",
    )
    parser.add_argument(
        "--migrate", action="store_true",
        help="One-time migration to fix jobCategory, dates, salary, URLs in jobs.json, then exit",
    )
    parser.add_argument(
        "--schedule", action="store_true",
        help="Run the full pipeline now, then every 1 hour (blocks until Ctrl+C)",
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="Reset raw state and clear output stores, then exit",
    )
    parser.add_argument(
        "--patch-titles", action="store_true",
        help="Patch known Finnish titles to English in jobs.json, regenerate HTML, then exit",
    )
    parser.add_argument(
        "--cleanup", action="store_true",
        help="Remove all intermediate data for jobs already saved in jobs.json, then exit",
    )

    args = parser.parse_args()

    if args.format_only:
        cmd_format_only()
        return

    if args.html_only:
        cmd_html_only()
        return

    if args.check_expires:
        cmd_check_expires()
        return

    if args.check_db:
        cmd_check_db()
        return

    if args.fix_dates:
        cmd_fix_dates()
        return

    if args.migrate:
        cmd_migrate()
        return

    if args.schedule:
        cmd_schedule()
        return

    if args.reset:
        cmd_reset()
        return

    if args.patch_titles:
        cmd_patch_titles()
        return

    if args.cleanup:
        cmd_cleanup()
        return

    run(dry_run=args.dry_run, ai_only=args.ai_only, reset_raw=args.reset_raw)


if __name__ == "__main__":
    main()