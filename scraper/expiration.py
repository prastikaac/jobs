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
    """Parse an ISO date string (YYYY-MM-DD) to a date object."""
    try:
        return datetime.strptime(str(date_str)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def remove_expired_jobs(jobs: list[dict]) -> tuple[list[dict], list[dict]]:
    """
    Filter out jobs older than config.EXPIRATION_DAYS.

    Returns:
        (active_jobs, expired_jobs)

    Expiration uses:
    1. date_posted if valid
    2. otherwise scraped_at if valid
    3. otherwise keeps the job to be safe
    """
    today = date.today()
    active = []
    expired = []

    for job in jobs:
        posted = _parse_date(job.get("date_posted"))

        if posted is None:
            posted = _parse_date(job.get("scraped_at"))

        if posted is None:
            logger.warning("Cannot parse date for job %s — keeping it.", job.get("id"))
            active.append(job)
            continue

        age_days = (today - posted).days

        if age_days > config.EXPIRATION_DAYS:
            expired.append(job)
            _delete_job_folder(job)
        else:
            active.append(job)

    if expired:
        logger.info(
            "Expired %d jobs (older than %d days): %s",
            len(expired),
            config.EXPIRATION_DAYS,
            [j.get("id") for j in expired],
        )
    else:
        logger.info("No expired jobs found.")

    return active, expired


def _delete_job_folder(job: dict) -> None:
    """
    Delete the /jobs/{category-slug}/{job_id}/ directory if it exists.

    New pipeline uses:
    - job_category
    - job_id

    Falls back safely if one is missing.
    """
    job_id = str(job.get("job_id") or job.get("id") or "").strip()
    if not job_id:
        logger.warning("Cannot delete job folder: missing job_id/id in job %s", job)
        return

    category = str(job.get("job_category") or "other").strip().lower()
    cat_slug = config.slugify_category(category) if category else "other"

    folder = os.path.join(config.JOBS_OUTPUT_DIR, cat_slug, job_id)

    if os.path.exists(folder):
        try:
            shutil.rmtree(folder)
            logger.info("Deleted expired job folder: %s", folder)
        except OSError as exc:
            logger.error("Failed to delete folder %s: %s", folder, exc)
    else:
        logger.debug("Folder not found (already deleted?): %s", folder)