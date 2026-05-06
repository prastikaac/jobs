"""
expiration.py — Job expiration logic.

Removes jobs older than EXPIRATION_DAYS from the active formatted job store
and deletes their corresponding /jobs/{category}/{job_id}/ folders.
"""

import logging
import os
import shutil
from datetime import date, datetime

import config

logger = logging.getLogger("expiration")


def _parse_date(date_str: str) -> date | None:
    """Parse an ISO date string (YYYY-MM-DD) to a date object.
    
    Returns None for any value that doesn't cleanly represent a real date,
    including short garbage strings like '2' or '30'.
    """
    if not date_str:
        return None
    s = str(date_str).strip()
    # Must be at least 8 chars (YYYY-MM-DD shortest valid ISO date)
    if len(s) < 8:
        return None
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def is_job_expired(job: dict) -> bool:
    """
    Check if a job is expired based on explicit date_expires,
    falling back to age based on posting date.
    """
    today = date.today()
    
    # Priority 1: Explicit expiration date
    expires = _parse_date(job.get("date_expires"))
    if expires:
        return expires < today
        
    # Priority 2: Fallback to posting date + config.EXPIRATION_DAYS
    posted = _parse_date(job.get("date_posted"))
    if posted is None:
        posted = _parse_date(job.get("scraped_at"))
        
    if posted is None:
        logger.warning(
            "Cannot parse date for job %s (date_posted=%r) — "
            "treating as not expired to avoid premature removal.",
            job.get("id"), job.get("date_posted")
        )
        return False
        
    age_days = (today - posted).days
    return age_days > config.EXPIRATION_DAYS


def remove_expired_jobs(jobs: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Filter out jobs using the is_job_expired logic.

    Returns:
        (active_jobs, expired_jobs)
    """
    active = []
    expired = []

    for job in jobs:
        if is_job_expired(job):
            expired.append(job)
            _delete_job_html(job)
        else:
            active.append(job)

    if expired:
        logger.info(
            "Expired %d jobs: %s",
            len(expired),
            [j.get("id") for j in expired],
        )
    else:
        logger.info("No expired jobs found.")

    return active, expired

def _delete_job_html(job: dict) -> None:
    """
    Delete the /jobs/{category-slug}/{job_id}.html file if it exists.

    New pipeline uses:
    - job_category
    - job_id

    Falls back safely if one is missing.
    """
    job_id = str(job.get("job_id") or job.get("id") or "").strip()
    if not job_id:
        logger.warning("Cannot delete job file: missing job_id/id in job %s", job)
        return

    category = str(job.get("job_category") or "other").strip().lower()
    cat_slug = config.slugify_category(category) if category else "other"

    file_path = os.path.join(config.JOBS_OUTPUT_DIR, cat_slug, f"{job_id}.html")

    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            logger.info("Deleted expired job html: %s", file_path)
        except OSError as exc:
            logger.error("Failed to delete file %s: %s", file_path, exc)
    else:
        logger.debug("File not found (already deleted?): %s", file_path)