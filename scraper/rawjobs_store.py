"""
rawjobs_store.py — Raw job queue storage (Phase 1 of pipeline).

rawjobs.json is a flat list of raw scraped+translated jobs.
Each entry has a 'processed' flag:
  - False: job has not been formatted by AI yet
  - True:  job has been processed and written to jobs.json
"""

import json
import logging
import os
from datetime import datetime

import config

logger = logging.getLogger("rawjobs_store")


# ── Load / Save ───────────────────────────────────────────────────────────────

def load_raw_jobs() -> list[dict]:
    """Load all raw jobs from rawjobs.json."""
    os.makedirs(config.DATA_DIR, exist_ok=True)
    if not os.path.exists(config.RAWJOBS_JSON_PATH):
        logger.info("rawjobs.json not found — starting fresh.")
        return []
    try:
        with open(config.RAWJOBS_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            logger.warning("rawjobs.json root is not a list — resetting.")
            return []
        logger.info("Loaded %d raw jobs from rawjobs.json", len(data))
        return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to load rawjobs.json: %s", exc)
        return []


def save_raw_jobs(jobs: list[dict]) -> None:
    """Save raw jobs list to rawjobs.json."""
    os.makedirs(config.DATA_DIR, exist_ok=True)
    with open(config.RAWJOBS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False, indent=2, default=str)
    logger.info("Saved %d raw jobs to rawjobs.json", len(jobs))


# ── ID helpers ────────────────────────────────────────────────────────────────

def get_existing_raw_ids(raw_jobs: list[dict]) -> set:
    """Return the set of all job hashes in rawjobs.json."""
    def extract_hash(jid: str) -> str:
        return str(jid).split("-")[-1] if "-" in str(jid) else str(jid)
    return {extract_hash(j["id"]) for j in raw_jobs if j.get("id")}


def get_unprocessed_jobs(raw_jobs: list[dict]) -> list[dict]:
    """
    Return jobs that need AI processing.
    Handles both new schema (ai_processed/ai_retry_needed) and old schema (processed).
    """
    result = []
    for j in raw_jobs:
        has_new_schema = "ai_processed" in j
        
        if has_new_schema:
            # New schema: only include if AI not done AND retry is enabled
            if not j["ai_processed"] and j.get("ai_retry_needed", True):
                result.append(j)
        else:
            # Old schema: only include if processed is False
            if not j.get("processed", False):
                result.append(j)
    
    return result


# ── Status updates ────────────────────────────────────────────────────────────

def merge_new_raw_jobs(existing: list[dict], new_jobs: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Add new raw jobs to the list (skip duplicates by ID).
    Returns (all_raw_jobs, actually_added).
    """
    existing_ids = get_existing_raw_ids(existing)
    actually_new = []
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for job in new_jobs:
        if job.get("id") in existing_ids:
            continue
        # Ensure required queue fields (Granular Status)
        job.setdefault("scraped", True)
        job.setdefault("ai_processed", False)
        job.setdefault("ai_status", "pending")
        job.setdefault("retry_count", 0)
        job.setdefault("max_retries", 3)
        job.setdefault("ai_retry_needed", True)
        job.setdefault("last_ai_error", "")
        job.setdefault("display_mode", "fallback")
        
        # Backward compatibility
        job.setdefault("processed", False)
        
        job.setdefault("scraped_at", now_str)
        actually_new.append(job)
        existing_ids.add(job["id"])

    merged = existing + actually_new
    logger.info(
        "Raw jobs: %d existing + %d new = %d total",
        len(existing), len(actually_new), len(merged)
    )
    return merged, actually_new


def update_ai_status(raw_jobs: list[dict], job_id: str, success: bool, status: str = "success", error: str = "") -> None:
    """Update granular AI status fields for a specific job."""
    for job in raw_jobs:
        if job.get("id") == job_id:
            job["ai_processed"]  = success
            job["ai_status"]     = status
            job["last_ai_error"] = error
            
            if success:
                job["ai_retry_needed"] = False
                job["display_mode"]    = "ideal"
            else:
                job["retry_count"] = job.get("retry_count", 0) + 1
                if job["retry_count"] >= job.get("max_retries", 3):
                    job["ai_retry_needed"] = False
                    logger.info("Job %s reached max retries (%d). Marking as permanently failed.", job_id, job["max_retries"])
            
            # Legacy flag for backward compat
            job["processed"] = job["ai_processed"]
            return


def mark_job_processed(raw_jobs: list[dict], job_id: str) -> None:
    """Legacy helper: Mark a specific job as processed=True."""
    update_ai_status(raw_jobs, job_id, success=True, status="success")
