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
    Write a minimal job document to the Firebase 'jobs' collection.
    This triggers the Cloud Function (index.js) which sends email + push alerts.

    Only called ONCE per job (tracked via sent_alerts.json).

    Args:
        job: normalised job dict from jobs.json (must include 'id')

    Returns:
        Firestore document ID used for the alert.

    Raises:
        RuntimeError if Firebase is not initialised.
    """
    _require_db()

    from firebase_admin import firestore as fs

    job_id     = job["id"]
    image_url  = job.get("image_url", "")

    # Minimal payload — exactly what concept.txt specifies
    alert_doc = {
        "title":       job.get("title", ""),
        "description": (job.get("description") or "")[:300],  # keep email short
        "jobCategory": job.get("jobCategory", []),
        "jobLocation": job.get("jobLocation", []),
        "jobLink":     job.get("jobLink", ""),
        "imageUrl":    image_url,
        "created_at":  fs.SERVER_TIMESTAMP,
    }

    _db.collection(config.FIREBASE_ALERT_COLLECTION).document(job_id).set(alert_doc)
    jobs_store.mark_alert_sent(job_id)
    logger.info("Firebase alert sent for job [%s]: %s", job_id[:12], job.get("title"))
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
