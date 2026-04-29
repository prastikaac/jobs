"""
schedule_jobs.py — Runs run_all_jobs.bat on a weekday schedule.

Schedule:
    Mon-Fri: 10:15, 13:30, 17:00
    Sat-Sun: Off

If the previous run is still active when the next slot fires,
the scheduler waits for it to finish before starting the new one.
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
SCHEDULE_SLOTS = [(10, 15), (13, 30), (17, 0)]   # (hour, minute) UTC+local
WEEKDAYS       = {0, 1, 2, 3, 4}                 # Mon=0 … Fri=4, Sat/Sun skip

SCRAPER_DIR = os.path.dirname(os.path.abspath(__file__))
BAT_FILE    = os.path.join(SCRAPER_DIR, "run_all_jobs.bat")

POLL_SECS   = 20   # how often to check the clock
WAIT_SECS   = 30   # how long to sleep between "is previous run done?" checks

# ── State ─────────────────────────────────────────────────────────────────────
_run_lock   = threading.Lock()
_is_running = False


# ── Job runner ────────────────────────────────────────────────────────────────
def _do_run():
    global _is_running
    with _run_lock:
        _is_running = True
    try:
        logger.info("=" * 60)
        logger.info("Job run STARTED")
        logger.info("=" * 60)
        proc = subprocess.run(["cmd", "/c", BAT_FILE], cwd=SCRAPER_DIR)
        logger.info("=" * 60)
        logger.info("Job run FINISHED  (exit code %d)", proc.returncode)
        logger.info("=" * 60)
    except Exception as exc:
        logger.error("Job run ERROR: %s", exc)
    finally:
        with _run_lock:
            _is_running = False


def _wait_for_previous_and_run(slot_label: str):
    """Wait until any active run finishes, then fire the job in a thread."""
    logger.info("Slot %s fired — checking if previous run is still active...", slot_label)

    while True:
        with _run_lock:
            running = _is_running
        if not running:
            break
        logger.info("Previous run still active. Waiting %ds before retrying...", WAIT_SECS)
        time.sleep(WAIT_SECS)

    logger.info("Starting run for slot %s", slot_label)
    t = threading.Thread(target=_do_run, name=f"run-{slot_label}", daemon=False)
    t.start()


# ── Main loop ─────────────────────────────────────────────────────────────────
def main():
    logger.info("Scheduler started.")
    logger.info("Schedule: Mon-Fri at %s",
                ", ".join(f"{h:02d}:{m:02d}" for h, m in SCHEDULE_SLOTS))
    logger.info("Bat file: %s", BAT_FILE)

    fired_today: set[tuple[int, int]] = set()   # (hour, minute) already fired today
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
        slot    = (now.hour, now.minute)

        if weekday not in WEEKDAYS:
            # Weekend — sleep until Monday
            time.sleep(POLL_SECS)
            continue

        if slot in SCHEDULE_SLOTS and slot not in fired_today:
            fired_today.add(slot)
            slot_label = f"{slot[0]:02d}:{slot[1]:02d}"
            # Fire in a separate thread so the scheduler loop keeps running
            t = threading.Thread(
                target=_wait_for_previous_and_run,
                args=(slot_label,),
                daemon=False,
            )
            t.start()

        time.sleep(POLL_SECS)


if __name__ == "__main__":
    main()
