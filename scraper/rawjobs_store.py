"""
rawjobs_store.py — Raw job storage + sidecar processing state storage.

New design:
- rawjobs.json stores raw scraped jobs
- processing_state.json stores retry / AI / translation status by job id

Compatibility:
- helper functions still expose embedded fields when needed so older code
  can continue to work during migration.
"""

import json
import logging
import os
from datetime import datetime

import config

logger = logging.getLogger("rawjobs_store")

PROCESSING_FIELDS = {
    "translated",
    "translated_at",
    "ai_processed",
    "ai_status",
    "retry_count",
    "max_retries",
    "ai_retry_needed",
    "last_ai_error",
    "formatted_at",
    "processed",
}


# ── Load / Save rawjobs.json ──────────────────────────────────────────────────

def load_raw_jobs() -> list[dict]:
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
    """
    Save raw jobs list to rawjobs.json.
    Processing-state fields are stripped so rawjobs stays mostly raw.
    """
    os.makedirs(config.DATA_DIR, exist_ok=True)

    cleaned = []
    for job in jobs:
        item = dict(job)
        for field in PROCESSING_FIELDS:
            item.pop(field, None)
        cleaned.append(item)

    with open(config.RAWJOBS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2, default=str)

    logger.info("Saved %d raw jobs to rawjobs.json", len(cleaned))


# ── Load / Save processing_state.json ─────────────────────────────────────────

def load_processing_state() -> dict[str, dict]:
    os.makedirs(config.DATA_DIR, exist_ok=True)
    if not os.path.exists(config.PROCESSING_STATE_JSON_PATH):
        logger.info("processing_state.json not found — starting fresh.")
        return {}

    try:
        with open(config.PROCESSING_STATE_JSON_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not isinstance(data, dict):
            logger.warning("processing_state.json root is not an object — resetting.")
            return {}

        if "jobs" in data and isinstance(data["jobs"], dict):
            jobs_map = data["jobs"]
        else:
            jobs_map = data

        logger.info("Loaded processing state for %d jobs", len(jobs_map))
        return jobs_map

    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to load processing_state.json: %s", exc)
        return {}


def save_processing_state(state: dict[str, dict]) -> None:
    os.makedirs(config.DATA_DIR, exist_ok=True)
    payload = {
        "version": config.PROCESSING_STATE_VERSION,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "jobs": state,
    }
    with open(config.PROCESSING_STATE_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
    logger.info("Saved processing state for %d jobs", len(state))


# ── State helpers ─────────────────────────────────────────────────────────────

def _default_processing_state(job: dict | None = None) -> dict:
    translated = bool((job or {}).get("translated_content"))
    translated_at = ""
    if translated:
        translated_at = (job or {}).get("translated_at", "") or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    return {
        "translated": translated,
        "translated_at": translated_at,
        "ai_processed": False,
        "ai_status": "pending",
        "retry_count": 0,
        "max_retries": config.AI_MAX_RETRIES,
        "ai_retry_needed": True,
        "last_ai_error": "",
        "formatted_at": "",
    }


def ensure_processing_state(raw_jobs: list[dict], state: dict[str, dict] | None = None) -> dict[str, dict]:
    """
    Ensure every raw job has a sidecar state entry.
    Imports any legacy embedded fields if they exist.
    """
    state = state or load_processing_state()

    for job in raw_jobs:
        jid = job.get("id")
        if not jid:
            continue

        existing = state.get(jid, _default_processing_state(job))

        if "translated_content" in job and job.get("translated_content"):
            existing["translated"] = True
            existing["translated_at"] = existing.get("translated_at") or job.get("translated_at", "")

        if "ai_processed" in job:
            existing["ai_processed"] = bool(job.get("ai_processed"))
        if "ai_status" in job:
            existing["ai_status"] = job.get("ai_status", existing["ai_status"])
        if "retry_count" in job:
            existing["retry_count"] = int(job.get("retry_count", existing["retry_count"]))
        if "max_retries" in job:
            existing["max_retries"] = int(job.get("max_retries", existing["max_retries"]))
        if "ai_retry_needed" in job:
            existing["ai_retry_needed"] = bool(job.get("ai_retry_needed"))
        if "last_ai_error" in job:
            existing["last_ai_error"] = job.get("last_ai_error", existing["last_ai_error"])
        if "formatted_at" in job:
            existing["formatted_at"] = job.get("formatted_at", existing["formatted_at"])

        state[jid] = existing

    return state


def attach_processing_state(jobs: list[dict], state: dict[str, dict]) -> list[dict]:
    """
    Return a new list where sidecar processing fields are attached into each job dict.
    This is mainly for compatibility with older code that expects embedded fields.
    """
    attached = []
    for job in jobs:
        item = dict(job)
        jid = item.get("id")
        ps = state.get(jid, _default_processing_state(item))
        item.update(ps)
        item["processed"] = bool(ps.get("ai_processed", False))
        attached.append(item)
    return attached


def sync_processing_state_from_jobs(jobs: list[dict], state: dict[str, dict] | None = None) -> dict[str, dict]:
    """
    Pull processing fields back out of embedded job dicts into sidecar state.
    """
    state = state or {}

    for job in jobs:
        jid = job.get("id")
        if not jid:
            continue

        ps = state.get(jid, _default_processing_state(job))
        ps["translated"] = bool(job.get("translated", ps.get("translated", False)) or job.get("translated_content"))
        ps["translated_at"] = job.get("translated_at", ps.get("translated_at", ""))
        ps["ai_processed"] = bool(job.get("ai_processed", ps.get("ai_processed", False)))
        ps["ai_status"] = job.get("ai_status", ps.get("ai_status", "pending"))
        ps["retry_count"] = int(job.get("retry_count", ps.get("retry_count", 0)))
        ps["max_retries"] = int(job.get("max_retries", ps.get("max_retries", config.AI_MAX_RETRIES)))
        ps["ai_retry_needed"] = bool(job.get("ai_retry_needed", ps.get("ai_retry_needed", True)))
        ps["last_ai_error"] = job.get("last_ai_error", ps.get("last_ai_error", ""))
        ps["formatted_at"] = job.get("formatted_at", ps.get("formatted_at", ""))

        state[jid] = ps

    return state


def reset_processing_state(
    raw_jobs: list[dict],
    state: dict[str, dict] | None = None,
    reset_translation: bool = False,
) -> dict[str, dict]:
    """
    Reset AI state for all known jobs.
    If reset_translation=True, also resets translation state.
    """
    state = ensure_processing_state(raw_jobs, state)

    for job in raw_jobs:
        jid = job.get("id")
        if not jid:
            continue

        state[jid]["ai_processed"] = False
        state[jid]["ai_status"] = "pending"
        state[jid]["retry_count"] = 0
        state[jid]["ai_retry_needed"] = True
        state[jid]["last_ai_error"] = ""
        state[jid]["formatted_at"] = ""

        if reset_translation:
            state[jid]["translated"] = False
            state[jid]["translated_at"] = ""

    return state


# ── ID helpers ────────────────────────────────────────────────────────────────

def get_existing_raw_ids(raw_jobs: list[dict]) -> set[str]:
    return {str(j["id"]) for j in raw_jobs if j.get("id")}


def get_unprocessed_jobs(raw_jobs: list[dict], state: dict[str, dict] | None = None) -> list[dict]:
    """
    Return jobs that need AI processing.
    Works with:
    - embedded processing fields
    - sidecar state
    """
    result = []
    for job in raw_jobs:
        jid = job.get("id")
        embedded = "ai_processed" in job or "processed" in job

        if embedded:
            ai_processed = bool(job.get("ai_processed", job.get("processed", False)))
            ai_retry_needed = bool(job.get("ai_retry_needed", True))
        elif state and jid in state:
            ai_processed = bool(state[jid].get("ai_processed", False))
            ai_retry_needed = bool(state[jid].get("ai_retry_needed", True))
        else:
            ai_processed = False
            ai_retry_needed = True

        if not ai_processed and ai_retry_needed:
            result.append(job)

    return result


# ── Merge / status updates ────────────────────────────────────────────────────

def merge_new_raw_jobs(existing: list[dict], new_jobs: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Add new raw jobs to the list (skip duplicates by ID).
    Raw storage stays mostly raw; processing state is initialized separately.
    """
    existing_ids = get_existing_raw_ids(existing)
    actually_new = []
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for job in new_jobs:
        jid = job.get("id")
        if not jid or jid in existing_ids:
            continue

        item = dict(job)
        item.setdefault("scraped_at", now_str)
        actually_new.append(item)
        existing_ids.add(jid)

    merged = existing + actually_new
    logger.info("Raw jobs: %d existing + %d new = %d total", len(existing), len(actually_new), len(merged))
    return merged, actually_new


def mark_translation_status(
    jobs: list[dict],
    job_id: str,
    translated: bool,
    processing_state: dict[str, dict] | None = None,
) -> None:
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if processing_state is not None:
        ps = processing_state.setdefault(job_id, _default_processing_state())
        ps["translated"] = translated
        ps["translated_at"] = now_str if translated else ""

    for job in jobs:
        if job.get("id") == job_id:
            job["translated"] = translated
            job["translated_at"] = now_str if translated else ""
            return


def update_ai_status(
    raw_jobs: list[dict],
    job_id: str,
    success: bool,
    status: str = "success",
    error: str = "",
    processing_state: dict[str, dict] | None = None,
) -> None:
    """
    Update granular AI status fields for a specific job.
    Updates both embedded fields and sidecar state.
    """
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if processing_state is not None:
        ps = processing_state.setdefault(job_id, _default_processing_state())
        ps["ai_processed"] = success
        ps["ai_status"] = status
        ps["last_ai_error"] = error

        if success:
            ps["ai_retry_needed"] = False
            ps["formatted_at"] = now_str
        else:
            ps["retry_count"] = int(ps.get("retry_count", 0)) + 1
            if ps["retry_count"] >= int(ps.get("max_retries", config.AI_MAX_RETRIES)):
                ps["ai_retry_needed"] = False
                logger.info(
                    "Job %s reached max retries (%d). Marking as permanently failed.",
                    job_id,
                    ps["max_retries"],
                )

    for job in raw_jobs:
        if job.get("id") != job_id:
            continue

        job["ai_processed"] = success
        job["ai_status"] = status
        job["last_ai_error"] = error

        if success:
            job["ai_retry_needed"] = False
            job["processed"] = True
            job["formatted_at"] = now_str
        else:
            job["retry_count"] = int(job.get("retry_count", 0)) + 1
            job["processed"] = False
            if job["retry_count"] >= int(job.get("max_retries", config.AI_MAX_RETRIES)):
                job["ai_retry_needed"] = False

        return


def mark_job_processed(
    raw_jobs: list[dict],
    job_id: str,
    processing_state: dict[str, dict] | None = None,
) -> None:
    update_ai_status(raw_jobs, job_id, success=True, status="success", processing_state=processing_state)