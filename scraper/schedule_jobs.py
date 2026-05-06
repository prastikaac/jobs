"""
schedule_jobs.py — Runs run_all_jobs.bat on a weekday schedule.

Schedule:
    Mon-Fri: 10:00, 13:30, 17:00
    Sat-Sun: Off

Overlap protection:
    - Each scheduled slot fires only once per day.
    - If the previous run is still active when a new slot fires, the new
      run is QUEUED (at most one pending run at a time).
    - When the active run finishes, the queued run starts immediately.
    - If the previous run finishes BEFORE the next scheduled slot,
      nothing extra happens — the next slot fires at its normal time.
"""

import datetime
import logging
import os
import subprocess
import threading
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] scheduler — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("scheduler")

# ── Config ────────────────────────────────────────────────────────────────────
SCHEDULE_SLOTS = [(10, 0), (13, 30), (17, 0)]    # (hour, minute) local time
WEEKDAYS       = {0, 1, 2, 3, 4}                 # Mon=0 … Fri=4, Sat/Sun skip

SCRAPER_DIR = os.path.dirname(os.path.abspath(__file__))
BAT_FILE    = os.path.join(SCRAPER_DIR, "run_all_jobs.bat")

POLL_SECS   = 15   # how often to check the clock

# ── State ─────────────────────────────────────────────────────────────────────
_lock       = threading.Lock()
_is_running = False           # True while run_all_jobs.bat is executing
_pending    = None            # slot label of a queued run (e.g. "13:30"), or None


# ── Job runner ────────────────────────────────────────────────────────────────
def _do_run(slot_label: str):
    """Execute run_all_jobs.bat. When done, check if a pending run is queued."""
    global _is_running, _pending

    with _lock:
        _is_running = True

    try:
        logger.info("=" * 60)
        logger.info("Job run STARTED  [slot %s]", slot_label)
        logger.info("=" * 60)
        proc = subprocess.run(["cmd", "/c", BAT_FILE], cwd=SCRAPER_DIR)
        logger.info("=" * 60)
        logger.info("Job run FINISHED  [slot %s]  (exit code %d)", slot_label, proc.returncode)
        logger.info("=" * 60)
    except Exception as exc:
        logger.error("Job run ERROR  [slot %s]: %s", slot_label, exc)
    finally:
        with _lock:
            _is_running = False
            queued = _pending
            _pending = None

        # If a slot fired while we were running, start it now
        if queued:
            logger.info("Pending run [slot %s] detected — starting immediately.", queued)
            _start_run(queued)


def _start_run(slot_label: str):
    """Launch _do_run in a background thread."""
    t = threading.Thread(target=_do_run, args=(slot_label,), name=f"run-{slot_label}", daemon=False)
    t.start()


def _handle_slot(slot_label: str):
    """Called when a scheduled slot fires. Either starts immediately or queues."""
    global _pending

    with _lock:
        if _is_running:
            if _pending:
                logger.info(
                    "Slot %s fired but previous run is still active AND "
                    "a run [slot %s] is already queued. Replacing queued slot.",
                    slot_label, _pending,
                )
            else:
                logger.info(
                    "Slot %s fired but previous run is still active. "
                    "Queuing — will start when current run finishes.",
                    slot_label,
                )
            _pending = slot_label
            return

    # No run active — start immediately
    logger.info("Slot %s fired — starting run.", slot_label)
    _start_run(slot_label)


# ── Main loop ─────────────────────────────────────────────────────────────────
def main():
    logger.info("Scheduler started.")
    logger.info("Schedule: Mon-Fri at %s",
                ", ".join(f"{h:02d}:{m:02d}" for h, m in SCHEDULE_SLOTS))
    logger.info("Bat file: %s", BAT_FILE)

    fired_today: set[tuple[int, int]] = set()   # slots already fired today
    last_day = None

    while True:
        now = datetime.datetime.now()

        # Reset daily tracking at midnight
        if now.date() != last_day:
            if last_day is not None:
                logger.info("New day — resetting fired slots.")
            fired_today.clear()
            last_day = now.date()

        weekday = now.weekday()

        if weekday not in WEEKDAYS:
            # Weekend — just sleep
            time.sleep(POLL_SECS)
            continue

        # Check if we are within the firing window for any slot.
        # A slot (H, M) fires if we are anywhere in [H:M:00 .. H:M:59]
        # and we haven't already fired it today.
        for slot_h, slot_m in SCHEDULE_SLOTS:
            if (slot_h, slot_m) in fired_today:
                continue
            if now.hour == slot_h and now.minute == slot_m:
                fired_today.add((slot_h, slot_m))
                slot_label = f"{slot_h:02d}:{slot_m:02d}"
                _handle_slot(slot_label)

        time.sleep(POLL_SECS)


if __name__ == "__main__":
    main()
