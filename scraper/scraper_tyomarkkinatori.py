"""
scraper_tyomarkkinatori.py — Scraper for Työmarkkinatori (tyomarkkinatori.fi).

Uses the public JSON REST API to search listings (POST) and fetch job details (GET).
Returns normalised raw job dicts ready for rawjobs_store.
"""

import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta

import requests

import config
from scraper import fetch_with_retry, normalise_raw_job

logger = logging.getLogger("scraper.tyomarkkinatori")

# ── Constants ─────────────────────────────────────────────────────────────────

TYOMARKKINATORI_API            = "https://tyomarkkinatori.fi/api/jobpostingfulltext/search/v2/search"
TYOMARKKINATORI_BASE           = "https://tyomarkkinatori.fi"
TYOMARKKINATORI_DETAIL_PATTERN = "/en/personal-customers/vacancies/{job_id}/en"
TYOMARKKINATORI_DETAIL_API     = "https://tyomarkkinatori.fi/api/jobposting-new/v1/public/jobpostings/"


# ── Private helpers ───────────────────────────────────────────────────────────

def _tyo_fetch_detail(job_id: str) -> dict | None:
    """Fetch full job JSON from the Työmarkkinatori public detail API."""
    url = f"{TYOMARKKINATORI_DETAIL_API}{job_id}"
    headers = {
        "Accept": "application/json",
        "Origin": "https://tyomarkkinatori.fi",
        "Referer": f"https://tyomarkkinatori.fi/en/personal-customers/vacancies/{job_id}/en",
    }
    def _fetch():
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        return resp.json()
    return fetch_with_retry(_fetch)


def _tyo_post(page: int = 0, size: int = 100) -> dict | None:
    """POST to Työmarkkinatori search API and return parsed JSON response."""
    payload = {
        "query": "",
        "filters": {},
        "paging": {"pageNumber": page, "pageSize": size},
        "sorting": "LATEST",
    }
    headers = {
        **config.REQUEST_HEADERS,
        "Content-Type": "application/json",
        "Accept": "*/*",
        "Origin": "https://tyomarkkinatori.fi",
        "Referer": "https://tyomarkkinatori.fi/",
    }

    def _post():
        resp = requests.post(
            TYOMARKKINATORI_API,
            json=payload,
            headers=headers,
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()

    try:
        return fetch_with_retry(_post)
    except Exception as exc:
        logger.error("API error (page=%d): %s", page, exc)
        return None


def _extract_lang_string(data, preferred: str = "en") -> str:
    """
    Extract a single string from Työmarkkinatori language dicts.
    Handles:
      - "string"
      - {"fi": "...", "en": "..."}
      - {"values": {"fi": "...", "en": "..."}}
    """
    if not data:
        return ""
    if isinstance(data, str):
        return data.strip()
    if isinstance(data, dict):
        if "values" in data and isinstance(data["values"], dict):
            data = data["values"]
        res = data.get(preferred) or data.get("en") or data.get("fi") or data.get("sv")
        if not res and data:
            for v in data.values():
                if v:
                    res = v
                    break
        return str(res or "").strip()
    return str(data).strip()


def _tyo_parse_job(item: dict, detail: dict = None) -> dict | None:
    """
    Convert a Työmarkkinatori API item to a raw job card dict ready for
    normalise_raw_job(). If 'detail' is provided, extracts rich fields
    (description, company, languages, employment type, etc.).
    """
    try:
        job_id_raw = str(item.get("id") or item.get("jobPostingId") or "").strip()
        if not job_id_raw:
            return None

        # Title / Label
        title_raw = item.get("jobPostingTitle") or item.get("title") or item.get("label")
        if detail:
            pos = detail.get("position") or {}
            title_raw = pos.get("title") or detail.get("title") or detail.get("jobTitle") or title_raw
        title = _extract_lang_string(title_raw)
        if not title:
            return None

        # Employer / company
        company = ""
        if detail:
            owner = detail.get("owner") or {}
            company = (
                _extract_lang_string(owner.get("officeName"))
                or _extract_lang_string(owner.get("company"))
            )
        if not company:
            employer = item.get("employer") or {}
            if isinstance(employer, dict):
                company = (
                    _extract_lang_string(employer.get("name"))
                    or _extract_lang_string(employer.get("ownerName"))
                )
            else:
                company = str(employer).strip()

        # Location
        loc_data = item.get("location") or item.get("municipality") or {}
        if detail and "location" in detail:
            loc_data = detail["location"]

        if isinstance(loc_data, dict):
            raw_location = _extract_lang_string(loc_data.get("name") or loc_data.get("municipality"))
        elif isinstance(loc_data, list):
            raw_location = ", ".join(_extract_lang_string(x) for x in loc_data)
        else:
            raw_location = str(loc_data).strip()

        if not raw_location and isinstance(loc_data, dict) and "municipalities" in loc_data:
            munis = loc_data["municipalities"]
            if isinstance(munis, list) and munis:
                m = munis[0]
                if isinstance(m, dict) and "label" in m:
                    raw_location = _extract_lang_string(m["label"])

        # Dates
        published_raw = str(item.get("publishedAt") or item.get("publicationDate") or date.today())
        if detail and detail.get("application", {}).get("published"):
            published_raw = detail["application"]["published"]
        try:
            posted_dt = datetime.fromisoformat(published_raw[:10].replace("Z", ""))
        except Exception:
            posted_dt = datetime.now()
        posted = posted_dt.strftime("%Y-%m-%d")

        expires_raw = item.get("applicationDeadline") or item.get("expiresAt") or ""
        if detail and detail.get("application", {}).get("expires"):
            expires_raw = detail["application"]["expires"]
        if expires_raw:
            try:
                expires = datetime.fromisoformat(str(expires_raw)[:10].replace("Z", "")).strftime("%Y-%m-%d")
            except Exception:
                expires = (posted_dt + timedelta(days=30)).strftime("%Y-%m-%d")
        else:
            expires = (posted_dt + timedelta(days=30)).strftime("%Y-%m-%d")

        # Links
        detail_path = TYOMARKKINATORI_DETAIL_PATTERN.format(job_id=job_id_raw)
        job_link    = str(TYOMARKKINATORI_BASE + detail_path)

        # 1. Determine Direct Application URL (from detail or search result)
        direct_apply_url = ""
        if detail:
            apply_raw = detail.get("application", {}).get("url")
            direct_apply_url = _extract_lang_string(apply_raw)
        
        if not direct_apply_url:
            apply_raw = item.get("applicationUrl") or item.get("applyUrl")
            direct_apply_url = _extract_lang_string(apply_raw)

        # Description / Content
        description = ""
        salary = ""
        langs: list = []
        what_we_expect: list = []
        job_responsibilities: list = []
        what_we_offer: list = []
        employment_type: list = []
        raw_text = ""

        if detail:
            pos        = detail.get("position") or {}
            desc_text  = _extract_lang_string(pos.get("jobDescription"), "fi")
            wage_info  = _extract_lang_string(pos.get("wagePrincipleInfo"), "fi")
            marketing  = _extract_lang_string(pos.get("marketingDescription"), "fi")
            help_raw   = detail.get("application", {}).get("helpText")
            help_text  = _extract_lang_string(help_raw, "fi")

            description = desc_text or ""
            raw_text    = "\n\n".join(filter(None, [desc_text, marketing, help_text]))
            salary      = wage_info or ""

            # ESCO Skills → what_we_expect
            for s in pos.get("skills", []):
                s_label = _extract_lang_string(s.get("prefLabel"), "fi")
                if s_label and s_label not in what_we_expect:
                    what_we_expect.append(s_label)

            # ESCO Occupations → job_responsibilities
            for o in pos.get("occupations", []):
                o_label = _extract_lang_string(o.get("prefLabel"), "fi")
                if o_label and o_label not in job_responsibilities:
                    job_responsibilities.append(o_label)

            # Language requirements
            work_langs = pos.get("workLanguages") or []
            if isinstance(work_langs, list):
                cmap  = {"fi": "Finnish", "en": "English", "sv": "Swedish"}
                langs = [cmap.get(l, l.capitalize()) for l in work_langs if l]

            # Employment type (workTime + continuityOfWork)
            wt = str(pos.get("workTime") or "").strip()
            wt_label = {"01": "Full-time", "02": "Part-time"}.get(wt)
            if wt_label:
                employment_type.append(wt_label)

            cont_map = {"01": "Permanent", "02": "Temporary"}
            continuity = pos.get("continuityOfWork") or []
            if isinstance(continuity, list):
                for code in continuity:
                    lbl = cont_map.get(str(code).strip())
                    if lbl and lbl not in employment_type:
                        employment_type.append(lbl)
            elif isinstance(continuity, str):
                lbl = cont_map.get(continuity.strip())
                if lbl:
                    employment_type.append(lbl)

            if not employment_type:
                employment_type = ["Full-time"]

            # Markdown section parser — fills gaps not covered by ESCO
            if desc_text:
                _sec_kw = {
                    "responsibilities": [
                        "your tasks", "your role", "tehtäväsi", "tehtäviin kuuluu",
                        "työnkuva", "vastuut", "mitä teet", "what is the job", "duties",
                    ],
                    "requirements": [
                        "we expect", "what we expect", "odotamme", "edellytämme",
                        "vaatimukset", "toivomme", "etsimme", "qualifications",
                        "requirements", "skills required",
                    ],
                    "offers": [
                        "we offer", "what we offer", "tarjoamme", "meillä saat",
                        "lupaamme", "benefits", "you will receive",
                    ],
                }
                current_sec = None
                _parsed: dict = {k: [] for k in _sec_kw}
                bullet_re    = re.compile(r'^[-•*#>]+\s*')

                for line in desc_text.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    line_low = line.lower()
                    matched = None
                    for sec, kws in _sec_kw.items():
                        if any(kw in line_low for kw in kws) and len(line) < 120:
                            matched = sec
                            break
                    if matched:
                        current_sec = matched
                        continue
                    if current_sec and 5 < len(line) < 300:
                        # Skip if it looks like a deadline, email, or URL to keep lists clean
                        if any(x in line_low for x in ["@", "http", ".fi", ".com", " mennessä", "viim."]):
                            continue
                        # If a date like 30.4. or 2024 is in the line, skip it for experience/requirements
                        if re.search(r'\d{1,2}\.\d{1,2}\.', line) or re.search(r'202[4-6]', line):
                            continue

                        clean = bullet_re.sub("", line).strip()
                        if clean and clean not in _parsed[current_sec]:
                            _parsed[current_sec].append(clean)

                if not job_responsibilities and _parsed["responsibilities"]:
                    job_responsibilities = _parsed["responsibilities"][:12]
                if not what_we_expect and _parsed["requirements"]:
                    what_we_expect = _parsed["requirements"][:10]
                if _parsed["offers"]:
                    what_we_offer = _parsed["offers"][:10]

        # Fallback description from search result
        if not description:
            desc_raw = (
                item.get("jobDescription")
                or item.get("description")
                or item.get("jobPostingDescription")
            )
            description = _extract_lang_string(desc_raw, "fi")
            raw_text    = description

        # Employer email from helpText
        employer_email = ""
        if detail:
            help_raw  = detail.get("application", {}).get("helpText")
            help_text = _extract_lang_string(help_raw, "fi")
            if help_text:
                m = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', help_text)
                if m:
                    employer_email = m.group(0)

        # FINAL APPLY LINK LOGIC
        # 1. If we have a direct application URL, use it
        if direct_apply_url and direct_apply_url.lower() not in ["", "none"]:
            apply_link = direct_apply_url
        # 2. Otherwise, if we have an employer email, use a mailto link
        elif employer_email:
            subject = f"Application for the Job - {title}"
            apply_link = f"mailto:{employer_email}?subject={subject}"
        # 3. Last resort: Link to the job listing page itself
        else:
            apply_link = job_link

        return {
            "title":                 title,
            "company":               company,
            "location":              raw_location,
            "jobLink":               job_link,
            "jobapply_link":         apply_link,
            "job_employer_email":    employer_email,
            "date_posted":           posted,
            "date_expires":          expires,
            "description":           description,
            "jobcontent":            raw_text,
            "salary":                salary,
            "employment_type":       employment_type,
            "language_requirements": langs,
            "what_we_expect":        what_we_expect,
            "job_responsibilities":  job_responsibilities,
            "what_we_offer":         what_we_offer,
            "source":                "tyomarkkinatori",
            "id":                    job_id_raw,
        }
    except Exception as exc:
        logger.warning("Failed to parse item (id=%s): %s", item.get("id"), exc)
        return None


# ── Public scraper entrypoint ─────────────────────────────────────────────────

def scrape_tyomarkkinatori(
    existing_ids: set,
    existing_job_ids: set,
    existing_title_co: set,
    existing_links: set,
    limit: int = 0,
    is_duplicate=None,
    add_to_dedup=None,
) -> list[dict]:
    """
    Scrape Työmarkkinatori using the JSON API (POST search + GET detail).

    Args:
        existing_ids / existing_job_ids / existing_title_co / existing_links:
            Dedup sets maintained by the main runner.
        limit: Stop after this many NEW jobs (0 = no limit).
        is_duplicate: callable(job, ids, job_ids, title_co, links) → bool
        add_to_dedup: callable(job, ids, job_ids, title_co, links) → None

    Returns:
        List of normalised raw job dicts (new jobs only).
    """
    logger.info("=== [Työmarkkinatori] Scrape started ===")
    new_jobs: list[dict] = []
    skipped    = 0
    total_found = 0

    size     = 30
    page     = 0
    max_pages = (config.MAX_PAGES * 100) // size

    while page < max_pages:
        if limit > 0 and len(new_jobs) >= limit:
            break

        logger.info("[Työmarkkinatori] Fetching page=%d size=%d", page, size)
        data = _tyo_post(page=page, size=size)

        if not data:
            logger.warning("[Työmarkkinatori] No data returned for page %d — stopping.", page)
            break

        hits = data.get("content") if isinstance(data, dict) else []
        if not hits:
            logger.info("[Työmarkkinatori] Empty page %d — end of results.", page)
            break

        total_found += len(hits)

        # Quick pre-filter: skip items that are already duplicates at the card level
        candidates = []
        for item in hits:
            card = _tyo_parse_job(item)
            if not card:
                skipped += 1
                continue
            job = normalise_raw_job(card)
            if is_duplicate and is_duplicate(job, existing_ids, existing_job_ids, existing_title_co, existing_links):
                skipped += 1
                continue
            candidates.append(item)

        if not candidates:
            if len(hits) < size:
                break
            page += 1
            continue

        # Fetch detail pages in parallel for new candidates
        logger.info("[Työmarkkinatori] Fetching details for %d candidates …", len(candidates))
        with ThreadPoolExecutor(max_workers=5) as executor:
            future_map = {executor.submit(_tyo_fetch_detail, i.get("id")): i for i in candidates}
            for future in as_completed(future_map):
                item = future_map[future]
                try:
                    detail = future.result()
                    card   = _tyo_parse_job(item, detail=detail)
                    if not card:
                        skipped += 1
                        continue

                    job = normalise_raw_job(card)
                    job["source"] = "tyomarkkinatori"
                    if card.get("language_requirements"):
                        job["language_requirements"] = card["language_requirements"]

                    if is_duplicate and is_duplicate(job, existing_ids, existing_job_ids, existing_title_co, existing_links):
                        skipped += 1
                        continue

                    new_jobs.append(job)
                    if add_to_dedup:
                        add_to_dedup(job, existing_ids, existing_job_ids, existing_title_co, existing_links)
                    logger.info("[Työ] NEW: %s @ %s", job.get("title"), job.get("company"))

                    if limit > 0 and len(new_jobs) >= limit:
                        executor.shutdown(wait=False, cancel_futures=True)
                        break
                except Exception as exc:
                    logger.warning("[Työmarkkinatori] Detail error for %s: %s", item.get("id"), exc)
                    skipped += 1

        if len(hits) < size:
            break
        page += 1
        time.sleep(config.REQUEST_DELAY_SECONDS)

    logger.info(
        "=== [Työmarkkinatori] Done. Found: %d | Skipped: %d | New: %d ===",
        total_found, skipped, len(new_jobs),
    )
    return new_jobs
