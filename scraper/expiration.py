"""
expiration.py — Job expiration logic (Step 6 of the pipeline).

Removes jobs older than EXPIRATION_DAYS from jobs.json
and deletes their corresponding /jobs/{id}/ folders from the website.
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

    Also deletes the folder /jobs/{id}/ for each expired job.
    """
    today     = date.today()
    active    = []
    expired   = []

    for job in jobs:
        posted = _parse_date(job.get("date_posted"))
        if posted is None:
            # Can't parse date — keep the job to be safe
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
    """Delete the /jobs/{category}/{job_id}/ directory if it exists."""
    job_id = job["id"]
    categories = job.get("jobCategory", ["Other"])
    if isinstance(categories, list):
        cat_slug = categories[0].lower().replace(" ", "-") if categories else "other"
    else:
        cat_slug = categories.lower().replace(" ", "-")
    
    folder = os.path.join(config.JOBS_OUTPUT_DIR, cat_slug, job_id)
    if os.path.exists(folder):
        try:
            shutil.rmtree(folder)
            logger.info("Deleted expired job folder: %s", folder)
        except OSError as exc:
            logger.error("Failed to delete folder %s: %s", folder, exc)
    else:
        logger.debug("Folder not found (already deleted?): %s", folder)
