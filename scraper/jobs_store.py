"""
jobs_store.py — Persistence layer for processed, AI-formatted jobs.

All jobs are persisted to /data/jobs.json inside the website directory.
The website's frontend fetches this file to display results.
"""

import json
import logging
import os
from datetime import date, datetime

import config

logger = logging.getLogger("jobs_store")


# ── Load / Save ───────────────────────────────────────────────────────────────

def load_jobs() -> list[dict]:
    """Load existing jobs from jobs.json. Converts session-grouped format to flat list."""
    os.makedirs(config.DATA_DIR, exist_ok=True)
    if not os.path.exists(config.JOBS_JSON_PATH):
        logger.info("jobs.json not found — starting fresh.")
        return []
    try:
        with open(config.JOBS_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            logger.warning("jobs.json root is not a list — resetting.")
            return []
        
        # Flatten session arrays into a single active job list
        flat_jobs = []
        for item in data:
            if isinstance(item, dict) and "scrape_timestamp" in item and "jobs" in item:
                flat_jobs.extend(item.get("jobs", []))
            else:
                flat_jobs.append(item)

        logger.info("Loaded %d active jobs from jobs.json", len(flat_jobs))
        return flat_jobs
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to load jobs.json: %s", exc)
        return []


def save_jobs(jobs: list[dict]) -> None:
    """Save jobs list to jobs.json (grouped by scrape_timestamp, pretty-printed with blank lines)."""
    os.makedirs(config.DATA_DIR, exist_ok=True)
    
    # Group by scrape_timestamp
    sessions = {}
    for j in jobs:
        ts = j.get("scraped_at", "Unknown Date")
        if ts not in sessions:
            sessions[ts] = []
        sessions[ts].append(j)
        
    # Build list of session objects sorted chronologically
    sorted_sessions = sorted(sessions.items(), key=lambda x: x[0])
    output_data = []
    for ts, session_jobs in sorted_sessions:
        output_data.append({
            "scrape_timestamp": ts,
            "jobs": session_jobs
        })

    json_str = json.dumps(output_data, ensure_ascii=False, indent=2, default=str)
    
    # Add an empty line between scrape sessions for the user's readability request
    json_str = json_str.replace('  },\n  {', '  },\n\n  {')

    with open(config.JOBS_JSON_PATH, "w", encoding="utf-8") as f:
        f.write(json_str)
        
    logger.info("Saved %d jobs across %d scrape sessions to jobs.json", len(jobs), len(output_data))


# ── Merge ─────────────────────────────────────────────────────────────────────

def get_existing_ids(jobs: list[dict]) -> set[str]:
    """Return the set of 8-character job hashes already in the store."""
    def extract_hash(jid: str) -> str:
        return str(jid).split("-")[-1] if "-" in str(jid) else str(jid)
    return {extract_hash(j["id"]) for j in jobs if j.get("id")}


def merge_new_jobs(existing: list[dict], new_jobs: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Merge new_jobs into existing list. 
    Duplicates by ID are updated if the new job is 'ideal' and the old is 'fallback'.
    """
    existing_map = {j["id"]: j for j in existing}
    actually_processed_or_new = []
    
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for new_job in new_jobs:
        jid = new_job["id"]
        if "scraped_at" not in new_job:
            new_job["scraped_at"] = now_str
            
        if jid not in existing_map:
            # Truly new job
            existing_map[jid] = new_job
            actually_processed_or_new.append(new_job)
        else:
            # Existing job: Check if we should upgrade from fallback to ideal
            old_job = existing_map[jid]
            is_upgrade = (
                new_job.get("display_mode") == "ideal" 
                and old_job.get("display_mode") == "fallback"
            )
            if is_upgrade:
                logger.info("Upgrading job %s from fallback to ideal AI formatting.", jid)
                existing_map[jid] = new_job
                actually_processed_or_new.append(new_job)
            else:
                # Keep the old one (it's either already ideal or the new one is also fallback)
                pass

    merged_all = list(existing_map.values())
    
    # Sort by scraped_at to maintain chronological order in sessions
    merged_all.sort(key=lambda x: x.get("scraped_at", ""), reverse=True)
    
    logger.info("Merged: %d total jobs (%d new/upgraded)", len(merged_all), len(actually_processed_or_new))
    return merged_all, actually_processed_or_new


# ── Sent-Alerts tracking ──────────────────────────────────────────────────────

def load_sent_alerts() -> set[str]:
    """Load the set of job IDs that have already had a Firebase alert sent."""
    if not os.path.exists(config.SENT_ALERTS_PATH):
        return set()
    try:
        with open(config.SENT_ALERTS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return set(data)
    except Exception:
        return set()


def mark_alert_sent(job_id: str) -> None:
    """Record that a Firebase alert has been sent for this job ID."""
    alerts = load_sent_alerts()
    alerts.add(job_id)
    os.makedirs(config.DATA_DIR, exist_ok=True)
    with open(config.SENT_ALERTS_PATH, "w", encoding="utf-8") as f:
        json.dump(sorted(alerts), f, indent=2)
