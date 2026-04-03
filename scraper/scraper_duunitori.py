"""
scraper_duunitori.py — Scraper for Duunitori (duunitori.fi).

Fetches paginated job listings, then fetches each job's detail page to get
the full description and apply URL. Returns normalised raw job dicts.

Important:
- Duunitori usually does not provide municipality codes in the same clean way
- so raw location text is preserved as-is
"""

import logging
import time
from urllib.parse import urlencode

import config
from scraper import (
    fetch_with_retry,
    make_job_id,
    normalise_raw_job,
    _sanitise,
    fetch_job_detail,
    parse_listings_page,
    has_next_page,
)

logger = logging.getLogger("scraper.duunitori")


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
    """
    logger.info("=== [Duunitori] Scrape started ===")
    new_jobs: list[dict] = []
    skipped = 0
    total_found = 0

    for page_num in range(1, config.MAX_PAGES + 1):
        if limit > 0 and len(new_jobs) >= limit:
            break

        params = {**config.SEARCH_PARAMS, "sivu": page_num}
        logger.info(
            "[Duunitori] Fetching page %d → %s?%s",
            page_num, config.SEARCH_URL, urlencode(params),
        )

        response = fetch_with_retry(lambda: requests_get_wrapper(config.SEARCH_URL, params=params))
        if not response:
            logger.warning("[Duunitori] No response for page %d — stopping.", page_num)
            break

        html = response.text
        cards = parse_listings_page(html)

        if not cards:
            logger.info("[Duunitori] No cards on page %d — end of results.", page_num)
            break

        total_found += len(cards)

        for card in cards:
            if limit > 0 and len(new_jobs) >= limit:
                break

            link = card["jobLink"]

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

            detail_res = fetch_with_retry(lambda: fetch_job_detail(link))
            if not detail_res:
                logger.warning("[Duunitori] Detail fetch failed for %s — skipping.", link)
                skipped += 1
                continue

            raw_text, apply_url = detail_res
            card["jobcontent"] = _sanitise(raw_text)
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


def requests_get_wrapper(url, params=None):
    import requests
    resp = requests.get(
        url,
        params=params,
        headers=config.REQUEST_HEADERS,
        timeout=15,
    )
    resp.raise_for_status()
    return resp