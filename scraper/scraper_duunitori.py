"""
scraper_duunitori.py — Scraper for Duunitori (duunitori.fi).

Fetches paginated job listings, then fetches each job's detail page to get
the full description and apply URL. Returns normalised raw job dicts.
"""

import logging
import time
from urllib.parse import urlencode

import config
from scraper import (
    fetch_with_retry,
    make_job_id,
    normalise_raw_job,
    _get,
    _sanitise,
    fetch_job_detail,
    parse_listings_page,
    has_next_page,
)

logger = logging.getLogger("scraper.duunitori")


# ── Public scraper entrypoint ─────────────────────────────────────────────────

def scrape_duunitori(
    existing_ids: set,
    existing_job_ids: set,
    existing_title_co: set,
    existing_links: set,
    limit: int = 0,
    is_duplicate=None,
    add_to_dedup=None,
) -> list[dict]:
    """
    Scrape Duunitori across all configured pages.

    Args:
        existing_ids / existing_job_ids / existing_title_co / existing_links:
            Dedup sets maintained by the main runner.
        limit: Stop after this many NEW jobs (0 = no limit).
        is_duplicate: callable(job, ids, job_ids, title_co, links) → bool
        add_to_dedup: callable(job, ids, job_ids, title_co, links) → None

    Returns:
        List of normalised raw job dicts (new jobs only).
    """
    logger.info("=== [Duunitori] Scrape started ===")
    new_jobs: list[dict] = []
    skipped     = 0
    total_found = 0

    for page_num in range(1, config.MAX_PAGES + 1):
        if limit > 0 and len(new_jobs) >= limit:
            break

        params = {**config.SEARCH_PARAMS, "sivu": page_num}
        logger.info(
            "[Duunitori] Fetching page %d → %s?%s",
            page_num, config.SEARCH_URL, urlencode(params),
        )

        response = fetch_with_retry(lambda: _get(config.SEARCH_URL, params=params))
        if not response:
            logger.warning("[Duunitori] No response for page %d — stopping.", page_num)
            break

        html  = response.text
        cards = parse_listings_page(html)

        if not cards:
            logger.info("[Duunitori] No cards on page %d — end of results.", page_num)
            break

        total_found += len(cards)

        for card in cards:
            if limit > 0 and len(new_jobs) >= limit:
                break

            link = card["jobLink"]

            # Fast pre-check before hitting the network for a detail page
            url_hash, _ = make_job_id(card["title"], card.get("location", ""), link)
            if url_hash in existing_ids:
                logger.debug("[Duunitori] SKIP (id exists): %s", url_hash)
                skipped += 1
                continue
            if link in existing_links:
                logger.debug("[Duunitori] SKIP (link exists): %s", link)
                skipped += 1
                continue

            logger.info("[Duunitori] NEW: %s", card["title"])

            # Fetch full description
            detail_res = fetch_with_retry(lambda: fetch_job_detail(link))
            if not detail_res:
                logger.warning("[Duunitori] Detail fetch failed for %s — skipping.", link)
                skipped += 1
                continue

            raw_text, apply_url = detail_res
            card["raw_text"]      = _sanitise(raw_text)
            card["jobapply_link"] = apply_url or link

            job = normalise_raw_job(card)
            job["source"] = "duunitori"

            if is_duplicate and is_duplicate(job, existing_ids, existing_job_ids, existing_title_co, existing_links):
                skipped += 1
                continue

            new_jobs.append(job)
            if add_to_dedup:
                add_to_dedup(job, existing_ids, existing_job_ids, existing_title_co, existing_links)

            time.sleep(config.DETAIL_DELAY_SECONDS)

        time.sleep(config.REQUEST_DELAY_SECONDS)

        if not has_next_page(html, page_num):
            logger.info("[Duunitori] No next page after page %d.", page_num)
            break

    logger.info(
        "=== [Duunitori] Done. Found: %d | Skipped: %d | New: %d ===",
        total_found, skipped, len(new_jobs),
    )
    return new_jobs
