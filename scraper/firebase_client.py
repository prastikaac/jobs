"""
firebase_client.py — Firebase job alert client.

Jobs are NOT stored in Firestore — they live in /data/jobs.json.
Firebase Cloud Messaging (FCM) is used to notify users about new jobs.
"""

import logging
from typing import Optional

import config
import jobs_store

logger = logging.getLogger("firebase_client")

_db = None


# ── Initialisation ────────────────────────────────────────────────────────────

def init_firebase(credentials_path: Optional[str] = None) -> None:
    """Initialise Firebase Admin SDK (idempotent)."""
    global _db

    import firebase_admin
    from firebase_admin import credentials, firestore

    if not firebase_admin._apps:
        cred_path = credentials_path or config.FIREBASE_CREDENTIALS_PATH
        cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
        logger.info("Firebase initialised: %s", cred_path)

    _db = firestore.client()
    logger.info("Firestore client ready (alert collection: '%s')", config.FIREBASE_ALERT_COLLECTION)


def _require_db() -> None:
    if _db is None:
        raise RuntimeError(
            "Firebase not initialised. Call init_firebase() first "
            "or run the pipeline with --dry-run."
        )


# ── Alert sender ──────────────────────────────────────────────────────────────

def send_job_alert(job: dict) -> str:
    """
    Write a job document to the Firebase 'jobs' collection.
    This triggers the Cloud Function (index.js) via onDocumentCreated,
    which sends email + push alerts to matched users.

    Document shape matches exactly what index.js reads:
        createdAt   : SERVER_TIMESTAMP  (Timestamp)
        description : str               (truncated to 300 chars)
        imageUrl    : str
        jobCategory : list[str]
        jobLink     : str
        jobLocation : list[str]
        title       : str

    Only called ONCE per job (tracked via sent_alerts.json).
    """
    _require_db()

    from firebase_admin import firestore as fs

    job_id = job["id"]

    # jobCategory — always a list
    job_category = job.get("job_category") or job.get("jobCategory") or []
    if isinstance(job_category, str):
        job_category = [job_category]

    # jobLocation — always a list
    job_location = job.get("jobLocation") or []
    if isinstance(job_location, str):
        job_location = [job_location]

    # jobLink — pipeline stores apply link as 'jobapply_link'
    job_link = (
        job.get("jobapply_link")
        or job.get("jobLink")
        or job.get("jobUrl")
        or ""
    )

    # imageUrl
    image_url = job.get("image_url") or job.get("imageUrl") or ""

    # description — short for email/push body
    description = (job.get("description") or "")[:300]

    # Map jobTimes (frontend: "full-time", "part-time")
    work_time_str = job.get("workTime", "").lower()
    job_times = []
    if "full" in work_time_str: job_times.append("full-time")
    elif "part" in work_time_str: job_times.append("part-time")
    
    # Map jobType (frontend: "permanent", "temporary", "seasonal", "summer")
    continuity_str = job.get("continuityOfWork", "").lower()
    job_type = []
    if "permanent" in continuity_str or "continuous" in continuity_str or "regular" in continuity_str:
        job_type.append("permanent")
    else:
        if "temp" in continuity_str or "fixed" in continuity_str: job_type.append("temporary")
        if "season" in continuity_str: job_type.append("seasonal")
        if "summer" in continuity_str: job_type.append("summer")
    
    # Map jobLanguage (frontend: "finnish", "english", "swedish")
    langs = job.get("language_requirements") or []
    job_language = [str(l).lower() for l in langs if str(l).lower() in ["finnish", "english", "swedish"]]

    alert_doc = {
        "createdAt":   fs.SERVER_TIMESTAMP,
        "description": description,
        "imageUrl":    image_url,
        "jobCategory": job_category,
        "jobLink":     job_link,
        "jobLocation": job_location,
        "title":       job.get("title", ""),
        "jobLanguage": job_language,
        "jobTimes":    job_times,
        "jobType":     job_type,
    }

    # Use add() so Firestore generates a fresh doc ID → always fires onDocumentCreated
    _db.collection(config.FIREBASE_ALERT_COLLECTION).document(job_id).set(alert_doc)
    jobs_store.mark_alert_sent(job_id)
    logger.info(
        "Firebase alert sent for job [%s]: %s | category=%s | location=%s",
        job_id[:12], job.get("title"), job_category, job_location,
    )
    return job_id


def send_new_job_alerts(new_jobs: list[dict], dry_run: bool = False) -> int:
    """
    Send Firebase alerts for all new jobs that haven't been alerted yet.

    Returns the number of alerts actually sent.
    """
    sent_alerts = jobs_store.load_sent_alerts()
    count = 0

    for job in new_jobs:
        job_id = job.get("id")
        if not job_id:
            continue

        if job_id in sent_alerts:
            logger.debug("Alert already sent for %s — skipping", job_id)
            continue

        if dry_run:
            logger.info("[DRY-RUN] Would send Firebase alert: %s (%s)", job_id, job.get("title"))
            count += 1
            continue

        try:
            send_job_alert(job)
            count += 1
        except Exception as exc:
            logger.error("Failed to send alert for %s: %s", job_id, exc)

    logger.info("Firebase alerts sent: %d / %d", count, len(new_jobs))
    return count
