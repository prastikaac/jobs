"""
scraper_jobly.py — Scraper for Jobly (jobly.fi).

Uses an XML sitemap to discover job URLs (bypassing Cloudflare / JS rendering),
then extracts job data from JSON-LD embedded in each job page.
Requires the 'cloudscraper' package (pip install cloudscraper).
"""

import json
import logging
import re
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup

import config
from scraper import fetch_with_retry, normalise_raw_job, _sanitise

logger = logging.getLogger("scraper.jobly")

# ── Constants ─────────────────────────────────────────────────────────────────

JOBLY_BASE     = "https://www.jobly.fi"
JOBLY_SITEMAPS = [
    "https://www.jobly.fi/sitemap.xml?page=1",
    "https://www.jobly.fi/sitemap.xml?page=2",
]


# ── Public scraper entrypoint ─────────────────────────────────────────────────

def scrape_jobly(
    existing_ids: set,
    existing_job_ids: set,
    existing_title_co: set,
    existing_links: set,
    limit: int = 0,
    is_duplicate=None,
    add_to_dedup=None,
) -> list[dict]:
    """
    Scrape Jobly via XML sitemap + JSON-LD extraction.

    Strategy:
      1. Fetch sitemap pages and collect all /tyopaikka/ URLs.
      2. Sort by lastmod (newest first) and cap at MAX_PAGES * 25.
      3. Fetch each job page in parallel (via cloudscraper) and parse JSON-LD.
      4. Normalise and deduplicate.

    Args:
        existing_ids / existing_job_ids / existing_title_co / existing_links:
            Dedup sets maintained by the main runner.
        limit: Stop after this many NEW jobs (0 = no limit).
        is_duplicate: callable(job, ids, job_ids, title_co, links) → bool
        add_to_dedup: callable(job, ids, job_ids, title_co, links) → None

    Returns:
        List of normalised raw job dicts (new jobs only).
    """
    logger.info("=== [Jobly] Scrape started ===")

    try:
        import cloudscraper
    except ImportError:
        logger.error(
            "[Jobly] 'cloudscraper' not installed. Run: pip install cloudscraper — skipping Jobly."
        )
        return []

    s = cloudscraper.create_scraper()
    new_jobs: list[dict] = []
    skipped     = 0
    total_found = 0
    job_urls: list[tuple] = []

    logger.info("[Jobly] Using cloudscraper to bypass Cloudflare bot protection.")
    logger.info("[Jobly] If scraping consistently fails, update cloudscraper via pip.")

    # ── Step 1: Collect job URLs from sitemaps ────────────────────────────────
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    for sm_url in JOBLY_SITEMAPS:
        logger.info("[Jobly] Fetching sitemap: %s", sm_url)
        try:
            resp = fetch_with_retry(lambda: s.get(sm_url, timeout=20))
            if not resp or resp.status_code != 200:
                logger.warning("[Jobly] Failed to fetch sitemap %s (status=%s)",
                               sm_url, getattr(resp, "status_code", "N/A"))
                continue
            resp_text = getattr(resp, "text", "")
            if not resp_text:
                logger.warning("[Jobly] Empty response for sitemap %s", sm_url)
                continue

            root = ET.fromstring(resp_text)
            count_before = len(job_urls)
            for url_node in root.findall("sm:url", ns):
                loc     = url_node.find("sm:loc", ns)
                lastmod = url_node.find("sm:lastmod", ns)
                if loc is not None and loc.text and "/tyopaikka/" in loc.text:
                    lm = lastmod.text if lastmod is not None else ""
                    job_urls.append((loc.text, lm))
            logger.info("[Jobly] Sitemap %s → %d job URLs found",
                        sm_url, len(job_urls) - count_before)
        except ET.ParseError as exc:
            logger.warning("[Jobly] XML parse error for sitemap %s: %s", sm_url, exc)
        except Exception as exc:
            logger.warning("[Jobly] Unexpected error parsing sitemap %s: %s", sm_url, exc)

    if not job_urls:
        logger.warning("[Jobly] No job URLs found in any sitemap — aborting.")
        return []

    # Sort newest first and cap at MAX_PAGES * 25 (approx 25 jobs per page)
    job_urls.sort(key=lambda x: x[1], reverse=True)
    max_inspect = config.MAX_PAGES * 25
    candidates  = [url for url, _ in job_urls[:max_inspect]]
    logger.info("[Jobly] Inspecting %d URLs (of %d total)", len(candidates), len(job_urls))

    # Pre-filter already-seen links
    valid_candidates = []
    for url in candidates:
        if url in existing_links:
            skipped += 1
            logger.debug("[Jobly] SKIP (link exists): %s", url)
            continue
        valid_candidates.append(url)

    total_found += len(valid_candidates)

    # ── Step 2: Fetch + parse job pages in parallel ───────────────────────────

    def _fetch_page(url_to_fetch: str):
        """Worker: fetch an individual Jobly page, return (url, html_text | None)."""
        try:
            res = fetch_with_retry(lambda: s.get(url_to_fetch, timeout=15))
            if res and res.status_code == 200:
                return url_to_fetch, res.text
            logger.warning("[Jobly] HTTP %s for %s",
                           getattr(res, "status_code", "N/A"), url_to_fetch)
            return url_to_fetch, None
        except Exception as exc:
            logger.warning("[Jobly] Fetch error for %s: %s", url_to_fetch, exc)
            return url_to_fetch, None

    with ThreadPoolExecutor(max_workers=5) as executor:
        future_map = {executor.submit(_fetch_page, url): url for url in valid_candidates}

        for future in as_completed(future_map):
            if limit > 0 and len(new_jobs) >= limit:
                executor.shutdown(wait=False, cancel_futures=True)
                break

            job_url = future_map[future]
            try:
                job_url, html = future.result()
            except Exception as exc:
                logger.warning("[Jobly] Unexpected future error for %s: %s", job_url, exc)
                skipped += 1
                continue

            if not html:
                skipped += 1
                continue

            # ── Parse slug for a stable source_id ────────────────────────────
            slug_match = re.search(r"-(\d+)$", job_url.rstrip("/"))
            jobly_id   = slug_match.group(1) if slug_match else ""

            soup = BeautifulSoup(html, "html.parser")

            # ── Extract from JSON-LD (primary strategy) ───────────────────────
            title       = ""
            company     = ""
            location    = ""
            date_posted = str(date.today())
            raw_text    = ""

            for script in soup.find_all("script", type="application/ld+json"):
                try:
                    ld = json.loads(script.string or "")
                    if isinstance(ld, dict) and ld.get("@type") == "JobPosting":
                        title   = str(ld.get("title", ""))
                        company = str(
                            ld.get("hiringOrganization", {}).get("name", "")
                            if isinstance(ld.get("hiringOrganization"), dict)
                            else ""
                        )
                        loc_obj = ld.get("jobLocation")
                        if isinstance(loc_obj, list) and loc_obj:
                            loc_obj = loc_obj[0]
                        if isinstance(loc_obj, dict):
                            addr = loc_obj.get("address")
                            if isinstance(addr, dict):
                                location = str(addr.get("addressLocality", ""))
                            elif isinstance(addr, str):
                                location = addr
                        raw_text    = str(ld.get("description", ""))
                        date_posted = (
                            str(ld.get("datePosted", ""))[:10]
                            if ld.get("datePosted")
                            else str(date.today())
                        )
                        break   # found the JobPosting block
                except Exception as exc:
                    logger.debug("[Jobly] JSON-LD parse error on %s: %s", job_url, exc)

            # ── Fallbacks when JSON-LD is absent / incomplete ─────────────────
            if not title:
                h1 = soup.select_one("h1")
                title = h1.get_text(strip=True) if h1 else ""

            if not title:
                logger.warning("[Jobly] No title found for %s — skipping.", job_url)
                skipped += 1
                continue

            if not raw_text:
                desc_tag = soup.select_one(".node__content") or soup.select_one("main article")
                raw_text = desc_tag.get_text(separator="\n", strip=True) if desc_tag else ""

            # Apply link: prefer an explicit external apply button
            apply_tag  = (
                soup.select_one("a[href*='apply-external']")
                or soup.select_one("a.application-link")
            )
            apply_link = (
                urljoin(JOBLY_BASE, apply_tag["href"])
                if apply_tag and apply_tag.get("href")
                else job_url
            )

            card = {
                "title":         title,
                "company":       company,
                "location":      location,
                "jobLink":       job_url,
                "jobapply_link": apply_link,
                "date_posted":   date_posted,
                "description":   "",
                "raw_text":      _sanitise(raw_text),
                "salary":        None,
                "source":        "jobly",
            }

            job = normalise_raw_job(card)
            if jobly_id:
                job["source_id"] = f"jobly-{jobly_id}"

            if is_duplicate and is_duplicate(job, existing_ids, existing_job_ids, existing_title_co, existing_links):
                skipped += 1
                continue

            new_jobs.append(job)
            if add_to_dedup:
                add_to_dedup(job, existing_ids, existing_job_ids, existing_title_co, existing_links)
            logger.info("[Jobly] NEW: %s @ %s", job.get("title"), job.get("company"))

    logger.info(
        "=== [Jobly] Done. Inspected: %d | Skipped: %d | New: %d ===",
        total_found, skipped, len(new_jobs),
    )
    return new_jobs
