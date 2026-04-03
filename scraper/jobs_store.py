"""
jobs_store.py — Persistence layer for translated raw jobs, flat formatted jobs,
and grouped site-ready jobs.
"""

import json
import logging
import os
from datetime import datetime

import config

logger = logging.getLogger("jobs_store")


def _load_json_list(path: str, label: str) -> list[dict]:
    if not os.path.exists(path):
        logger.info("%s not found — starting fresh.", os.path.basename(path))
        return []

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            logger.warning("%s root is not a list — resetting.", label)
            return []
        return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to load %s: %s", label, exc)
        return []


def _save_json_list(path: str, jobs: list[dict], label: str) -> None:
    os.makedirs(config.DATA_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(jobs, f, indent=2, ensure_ascii=False, default=str)
    logger.info("Saved %d records to %s", len(jobs), label)


# ── Site-ready jobs.json (grouped by scrape session) ──────────────────────────

def load_jobs() -> list[dict]:
    """
    Load active jobs from jobs.json.
    Supports both:
    - grouped session format
    - flat list format
    """
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
    """
    Save site-ready jobs to jobs.json grouped by scrape_timestamp / scraped_at.
    """
    os.makedirs(config.DATA_DIR, exist_ok=True)

    sessions: dict[str, list[dict]] = {}
    for job in jobs:
        ts = job.get("scraped_at") or "Unknown Date"
        sessions.setdefault(ts, []).append(job)

    sorted_sessions = sorted(sessions.items(), key=lambda x: x[0], reverse=False)
    output_data = [{"scrape_timestamp": ts, "jobs": session_jobs} for ts, session_jobs in sorted_sessions]

    json_str = json.dumps(output_data, ensure_ascii=False, indent=2, default=str)
    json_str = json_str.replace("  },\n  {", "  },\n\n  {")

    with open(config.JOBS_JSON_PATH, "w", encoding="utf-8") as f:
        f.write(json_str)

    logger.info("Saved %d jobs across %d scrape sessions to jobs.json", len(jobs), len(output_data))


# ── Translated raw jobs (Phase 2 output only) ─────────────────────────────────

def load_translated_raw_jobs() -> list[dict]:
    """
    Load translated raw jobs from translated_raw_jobs.json.
    """
    return _load_json_list(config.TRANSLATED_RAW_JOBS_JSON_PATH, "translated_raw_jobs.json")


def save_translated_raw_jobs(jobs: list[dict]) -> None:
    """
    Save translated raw jobs (Phase 2 output only).
    Removes AI-only and processing-state fields if they were attached in memory.
    """
    cleaned = []
    for job in jobs:
        item = dict(job)
        item.pop("ai_data", None)
        item.pop("processed", None)
        item.pop("ai_processed", None)
        item.pop("ai_status", None)
        item.pop("retry_count", None)
        item.pop("max_retries", None)
        item.pop("ai_retry_needed", None)
        item.pop("last_ai_error", None)
        item.pop("translated", None)
        item.pop("translated_at", None)
        item.pop("formatted_at", None)
        cleaned.append(item)

    _save_json_list(config.TRANSLATED_RAW_JOBS_JSON_PATH, cleaned, "translated_raw_jobs.json")


# ── Flat formatted jobs (canonical active flat store) ────────────────────────

def load_formatted_jobs_flat() -> list[dict]:
    return _load_json_list(config.FORMATTED_JOBS_FLAT_JSON_PATH, "formatted_jobs_flat.json")


def save_formatted_jobs_flat(jobs: list[dict]) -> None:
    _save_json_list(config.FORMATTED_JOBS_FLAT_JSON_PATH, jobs, "formatted_jobs_flat.json")


# ── Backward compatibility wrappers ───────────────────────────────────────────

def load_translated_jobs() -> list[dict]:
    return load_translated_raw_jobs()


def save_translated_jobs(jobs: list[dict]) -> None:
    save_translated_raw_jobs(jobs)


# ── Merge helpers ─────────────────────────────────────────────────────────────

def get_existing_ids(jobs: list[dict]) -> set[str]:
    """Return the set of job IDs already in the store."""
    return {str(j["id"]) for j in jobs if j.get("id")}


def merge_new_jobs(existing: list[dict], new_jobs: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Merge new formatted jobs into the canonical active flat list.
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
            existing_map[jid] = new_job
            actually_processed_or_new.append(new_job)
            continue

        old_job = existing_map[jid]
        is_upgrade = (
            new_job.get("display_mode") == "ideal"
            and old_job.get("display_mode") == "fallback"
        )

        if is_upgrade:
            logger.info("Upgrading job %s from fallback to ideal AI formatting.", jid)
            existing_map[jid] = new_job
            actually_processed_or_new.append(new_job)

    merged_all = list(existing_map.values())
    merged_all.sort(key=lambda x: x.get("scraped_at", ""), reverse=True)

    logger.info("Merged: %d total jobs (%d new/upgraded)", len(merged_all), len(actually_processed_or_new))
    return merged_all, actually_processed_or_new


# ── Sent-alerts tracking ──────────────────────────────────────────────────────

def load_sent_alerts() -> set[str]:
    if not os.path.exists(config.SENT_ALERTS_PATH):
        return set()
    try:
        with open(config.SENT_ALERTS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return set(data)
    except Exception:
        return set()


def mark_alert_sent(job_id: str) -> None:
    alerts = load_sent_alerts()
    alerts.add(job_id)
    os.makedirs(config.DATA_DIR, exist_ok=True)
    with open(config.SENT_ALERTS_PATH, "w", encoding="utf-8") as f:
        json.dump(sorted(alerts), f, indent=2)