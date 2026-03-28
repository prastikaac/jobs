"""
run_scraper.py — Multi-site job scraper (Phase 1 of the pipeline).

Scrapes jobs from 3 Finnish job sites sequentially and saves new jobs to rawjobs.json.
The processor (run_pipeline.py) then picks up rawjobs.json for AI + HTML generation.

Sites (in order):
  1. Työmarkkinatori  — https://tyomarkkinatori.fi/en/personal-customers/vacancies
  2. Duunitori        — https://duunitori.fi/tyopaikat
  3. Jobly            — https://www.jobly.fi/tyopaikat

Usage:
  python run_scraper.py             # Scrape all sites → rawjobs.json
  python run_scraper.py --dry-run   # Print what would be scraped, no disk writes
"""

import argparse
import logging
import sys
from dataclasses import dataclass, field

# ── Fix Windows console Unicode ───────────────────────────────────────────────
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import rawjobs_store

# Import modular scrapers
from scraper_tyomarkkinatori import scrape_tyomarkkinatori
from scraper_duunitori import scrape_duunitori
from scraper_jobly import scrape_jobly

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("scraper.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("run_scraper")


# ══════════════════════════════════════════════════════════════════════════════
# DEDUPLICATION STATE
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class DeduplicationState:
    """Holds shared state across all scrapers to prevent intra-run duplicates."""
    ids: set = field(default_factory=set)
    job_ids: set = field(default_factory=set)
    title_co: set = field(default_factory=set)
    links: set = field(default_factory=set)

    @classmethod
    def build_from(cls, raw_jobs: list[dict]) -> "DeduplicationState":
        """Build the dedup state from existing raw jobs."""
        state = cls()
        for j in raw_jobs:
            jid = str(j.get("id") or "").split("-")[-1]
            if jid:
                state.ids.add(jid)

            if j.get("job_id"):
                state.job_ids.add(str(j["job_id"]))

            title = str(j.get("title") or "").lower().strip()
            co    = str(j.get("company") or "").lower().strip()
            locs  = j.get("jobLocation") or [""]
            loc   = str(locs[0] if locs else "").lower().strip()
            if title:
                state.title_co.add((title, co, loc))

            for f in ("jobapply_link", "jobLink"):
                link = str(j.get(f) or "").strip()
                if link:
                    state.links.add(link)
        return state

    def is_duplicate(self, job: dict) -> bool:
        """Returns True if the proposed job already exists."""
        jid = str(job.get("id") or "").split("-")[-1]
        if jid and jid in self.ids:
            return True

        if job.get("job_id") and job["job_id"] in self.job_ids:
            return True

        title = str(job.get("title") or "").lower().strip()
        co    = str(job.get("company") or "").lower().strip()
        locs  = job.get("jobLocation") or [""]
        loc   = str(locs[0] if locs else "").lower().strip()
        if title and (title, co, loc) in self.title_co:
            return True

        for f in ("jobapply_link", "jobLink"):
            link = str(job.get(f) or "").strip()
            if link and link in self.links:
                return True

        return False

    def add(self, job: dict) -> None:
        """Register a newly accepted job into the dedup sets."""
        jid = str(job.get("id") or "").split("-")[-1]
        if jid:
            self.ids.add(jid)
        if job.get("job_id"):
            self.job_ids.add(str(job["job_id"]))

        title = str(job.get("title") or "").lower().strip()
        co    = str(job.get("company") or "").lower().strip()
        locs  = job.get("jobLocation") or [""]
        loc   = str(locs[0] if locs else "").lower().strip()
        if title:
            self.title_co.add((title, co, loc))

        for f in ("jobapply_link", "jobLink"):
            link = str(job.get(f) or "").strip()
            if link:
                self.links.add(link)


# ══════════════════════════════════════════════════════════════════════════════
# MAIN ORCHESTRATOR
# ══════════════════════════════════════════════════════════════════════════════

def run(dry_run: bool = False, limit: int = None, site_filter: str = None) -> None:
    logger.info("=" * 60)
    logger.info("SCRAPER STARTED (dry_run=%s, limit=%s)", dry_run, limit)
    logger.info("=" * 60)

    # 1. Load existing deduplication state
    raw_jobs = rawjobs_store.load_raw_jobs()
    logger.info("Existing raw jobs loaded: %d", len(raw_jobs))
    dedup = DeduplicationState.build_from(raw_jobs)

    # 2. Run scrapers sequentially
    all_new: list[dict] = []
    scrapers = [
        ("Työmarkkinatori", scrape_tyomarkkinatori),
        ("Duunitori",       scrape_duunitori),
        ("Jobly",           scrape_jobly),
    ]

    for name, func in scrapers:
        if site_filter and site_filter.lower() not in name.lower():
            logger.info("[%s] Skipping (filter: %s)", name, site_filter)
            continue

        if limit and len(all_new) >= limit:
            break
        try:
            curr_limit = max(0, limit - len(all_new)) if limit else 0
            # Pass the 4 sets + callables backward-compatibly
            new = func(
                existing_ids=dedup.ids,
                existing_job_ids=dedup.job_ids,
                existing_title_co=dedup.title_co,
                existing_links=dedup.links,
                limit=curr_limit,
                # Provide the dataclass methods bridging the gap
                is_duplicate=lambda j, i, ji, tc, l: dedup.is_duplicate(j),
                add_to_dedup=lambda j, i, ji, tc, l: dedup.add(j),
            )
            all_new.extend(new)
            if limit and len(all_new) >= limit:
                all_new = all_new[:limit]
                logger.info("[%s] Global limit reached (%d total new jobs).", name, limit)
                break
        except Exception as exc:
            logger.error("[%s] Scraper crashed: %s", name, exc, exc_info=True)

    # 3. Summary & saving
    logger.info("=" * 60)
    logger.info("SCRAPER COMPLETE — total new jobs: %d", len(all_new))
    logger.info("=" * 60)

    if dry_run:
        logger.info("[DRY-RUN] Would add %d jobs to rawjobs.json. No disk writes.", len(all_new))
        for j in all_new:
            logger.info("  [%s] %s @ %s", j.get("source", "?").ljust(15), j.get("title"), j.get("company"))
        return

    if not all_new:
        logger.info("No new jobs found. rawjobs.json unchanged.")
        return

    merged, actually_added = rawjobs_store.merge_new_raw_jobs(raw_jobs, all_new)
    rawjobs_store.save_raw_jobs(merged)

    logger.info("rawjobs.json updated: %d new jobs added (%d total).",
                len(actually_added), len(merged))


def main():
    parser = argparse.ArgumentParser(
        description="Multi-site job scraper — saves new jobs to rawjobs.json",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print what would be scraped without writing to rawjobs.json",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Stop after scraping this many NEW jobs across all sites",
    )
    parser.add_argument(
        "--site", type=str, default=None,
        help="Only run specific scraper (e.g., Työmarkkinatori, Duunitori, Jobly)",
    )
    args = parser.parse_args()
    run(dry_run=args.dry_run, limit=args.limit, site_filter=args.site)


if __name__ == "__main__":
    main()
