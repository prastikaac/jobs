"""
scraper.py — Shared scraping utilities and raw-job normalization.

Phase 1 responsibilities:
- fetch listing/detail pages
- sanitize raw content
- normalize source-specific cards into rawjobs.json shape

Important:
- No AI formatting here
- No city-keyword matching here
- jobLocation should prefer municipality codes when the source provides them
"""

import hashlib
import logging
import re
import sys
import time
from datetime import date
from urllib.parse import urlencode

# ── Fix Windows console Unicode ───────────────────────────────────────────────
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import requests
from bs4 import BeautifulSoup

import config

logger = logging.getLogger("scraper")


# ── HTTP ──────────────────────────────────────────────────────────────────────

def fetch_with_retry(func, *args, max_retries: int = 3, base_delay: float = 2.0, **kwargs):
    """
    Executes a network-calling callable with exponential backoff on failure.
    Returns the result of the callable, or None if all retries are exhausted.
    """
    _log = logging.getLogger("scraper.retry")
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as exc:
            if attempt == max_retries - 1:
                _log.error("fetch_with_retry: all %d attempts failed — %s", max_retries, exc)
                return None
            sleep_time = base_delay * (2 ** attempt)
            _log.warning(
                "fetch_with_retry: attempt %d/%d failed: %s. Retrying in %.1fs…",
                attempt + 1,
                max_retries,
                exc,
                sleep_time,
            )
            time.sleep(sleep_time)
    return None


def _get(url: str, params: dict = None, retries: int = 3) -> requests.Response | None:
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(
                url,
                params=params,
                headers=config.REQUEST_HEADERS,
                timeout=15,
            )
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            logger.warning("GET failed (attempt %d/%d): %s — %s", attempt, retries, url, exc)
            if attempt < retries:
                time.sleep(config.REQUEST_DELAY_SECONDS * attempt)
    logger.error("All %d attempts failed: %s", retries, url)
    return None


# ── Slug & ID ─────────────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    """Convert text to a URL-safe slug."""
    text = str(text).lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")[:60]


def make_job_id(title: str, location: str, link: str) -> tuple[str, str]:
    """
    Create a deterministic, human-readable job ID.
    Returns: (8-char-hash, full-slug)
    Example: (a1b2c3d4, cleaner-helsinki-a1b2c3d4)
    """
    title_slug = slugify(title)[:30]
    loc_slug = slugify(location.split(",")[0])[:20] if location else "finland"
    url_hash = hashlib.md5(link.encode("utf-8")).hexdigest()[:8]
    return url_hash, f"{title_slug}-{loc_slug}-{url_hash}"


# ── Category fallback ─────────────────────────────────────────────────────────

def detect_categories(title: str, description: str) -> list[str]:
    """
    Very light keyword-based category fallback.
    Returns a non-empty array with exactly one category.
    """
    haystack = (title + " " + description).lower()
    for cat, keywords in config.CATEGORY_KEYWORDS.items():
        if any(kw in haystack for kw in keywords):
            return [cat]
    return ["other"]


# ── Location normalization ────────────────────────────────────────────────────

def normalize_job_locations(raw_location) -> list[str]:
    """
    Preserve location values without guessing from text.

    Preferred raw format:
      - municipality codes: ["091", "092"]
    Accepts:
      - list[str]
      - semicolon/comma-separated str
      - empty -> ["Finland"]

    This function does NOT try to map city names or regions here.
    Mapping happens later via municipalities_codes.json in Job_formatter.py.
    """
    if raw_location is None:
        return ["Finland"]

    if isinstance(raw_location, list):
        cleaned = [str(x).strip() for x in raw_location if str(x).strip()]
        return cleaned if cleaned else ["Finland"]

    if isinstance(raw_location, str):
        raw = raw_location.strip()
        if not raw or raw.lower() in {"none", "undetermined", "not specified", "koko suomi"}:
            return ["Finland"]

        # Allow comma or semicolon separated tokens
        parts = [p.strip() for p in re.split(r"[,;]", raw) if p.strip()]
        return parts if parts else ["Finland"]

    return ["Finland"]


# ── Page parsing ──────────────────────────────────────────────────────────────

def _text(tag, default: str = "") -> str:
    return tag.get_text(strip=True) if tag else default


def parse_listings_page(html: str) -> list[dict]:
    """Parse a Duunitori search results page. Returns raw job cards."""
    soup = BeautifulSoup(html, "html.parser")
    job_boxes = soup.select("div.job-box")
    logger.info("Found %d job cards on page", len(job_boxes))

    jobs = []
    for box in job_boxes:
        try:
            hover = box.select_one("a.job-box__hover")
            if not hover:
                continue

            relative_url = hover.get("href", "")
            apply_link = config.BASE_URL + relative_url if relative_url.startswith("/") else relative_url
            company = hover.get("data-company", "").strip()

            title_tag = box.select_one("h3.job-box__title")
            title = _text(title_tag)

            location_tag = box.select_one("span.job-box__job-location")
            location = _text(location_tag).rstrip("– ").strip()

            salary_tag = box.select_one("span.tag--salary")
            salary = _text(salary_tag) or None

            date_tag = box.select_one("span.job-box__job-posted")
            date_posted = _text(date_tag).removeprefix("Julkaistu ").strip() or None

            if not apply_link or not title:
                continue

            jobs.append({
                "title": title,
                "company": company,
                "location": location,
                "salary": salary,
                "jobLink": apply_link,
                "date_posted": date_posted or str(date.today()),
                "description": "",
            })
        except Exception as exc:
            logger.warning("Error parsing job card: %s", exc)

    return jobs


def fetch_job_detail(job_url: str) -> tuple[str, str]:
    """Fetch full raw text from the job detail page."""
    response = _get(job_url)
    if not response:
        return "", job_url

    soup = BeautifulSoup(response.text, "html.parser")

    desc_tag = (
        soup.select_one(".job-description")
        or soup.select_one("[class*='description']")
        or soup.select_one("article .content")
        or soup.select_one("main article")
    )

    if desc_tag:
        return desc_tag.get_text(separator="\n", strip=True)[:8000], job_url

    divs = soup.find_all("div")
    if divs:
        longest = max(divs, key=lambda d: len(d.get_text(strip=True)), default=None)
        if longest:
            return longest.get_text(separator="\n", strip=True)[:8000], job_url

    return "", job_url


# ── Full content analyzer ─────────────────────────────────────────────────────

def analyse_job_content(text: str, title: str = "") -> dict:
    """
    Analyze raw job text and extract lightweight structured fields.
    No AI here.
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    salary_range = ""
    salary_patterns = [
        r'[€$£]\s?[\d\s,]+[–\-]{1,2}[€$£]?\s?[\d\s,]+\s?(?:/|per)?\s?(?:month|hour|year|kk|h|v)',
        r'[\d\s,]+[–\-][\d\s,]+\s?€\s?(?:/|per)?\s?(?:month|hour|year|kk|h|v)',
        r'[€$£]\s?[\d][\d\s,.]*(?:/|per)\s?(?:month|hour|year|kk|h|v)',
        r'palkka[:\s]+[€$£]?\s?[\d][\d\s,.–\-]+',
        r'pay[:\s]+[€$£]?\s?[\d][\d\s,.–\-]+',
        r'salary[:\s]+[€$£]?\s?[\d][\d\s,.–\-]+',
    ]
    for ln in lines:
        for pat in salary_patterns:
            m = re.search(pat, ln, re.IGNORECASE)
            if m:
                salary_range = ln.strip()
                break
        if salary_range:
            break

    work_time = "Full-time"
    continuity_of_work = "Permanent"
    haystack_low = text.lower()
    if any(k in haystack_low for k in ["part-time", "part time", "osa-aikainen", "osa-aika"]):
        work_time = "Part-time"
    if any(k in haystack_low for k in ["summer job", "kesätyö", "kesatyö"]):
        continuity_of_work = "Summer job"
    elif any(k in haystack_low for k in ["seasonal", "kausityö", "kausityöntekijä"]):
        continuity_of_work = "Seasonal work"
    elif any(k in haystack_low for k in ["temporary", "määräaikainen", "fixed-term"]):
        continuity_of_work = "Temporary"
    elif any(k in haystack_low for k in ["permanent", "pysyvä", "toistaiseksi voimassa"]):
        continuity_of_work = "Permanent"

    language_requirements = []
    lang_map = {
        "Finnish": ["finnish", "suomi", "suomen kielen", "suomenkielinen"],
        "English": ["english", "englannin", "englanti"],
        "Swedish": ["swedish", "ruotsi", "ruotsinkielinen"],
    }
    for lang, keywords in lang_map.items():
        if any(k in haystack_low for k in keywords):
            language_requirements.append(lang)
    if not language_requirements:
        language_requirements = ["Finnish"]

    positions = []
    if title:
        if '&' in title or '/' in title:
            parts = re.split(r'[&/]', title)
            for p in parts:
                p = p.strip().title()
                if len(p) > 3 and p not in positions:
                    positions.append(p)
    if not positions and title:
        positions = [title.strip()]

    section_keywords = {
        "responsibilities": [
            "responsibilities", "your tasks", "what you'll do", "duties", "tasks", "what is the job",
            "tehtäviin kuuluu", "tehtäväsi", "työnkuva", "vastuut", "mitä teet",
        ],
        "requirements": [
            "requirements", "what we expect", "what you need", "we expect", "qualifications", "skills required",
            "mitä odotamme", "odotamme sinulta", "edellytämme", "vaatimukset", "toivomme sinulta",
            "millainen olet", "etsimme", "mitä haemme",
        ],
        "benefits": [
            "we offer", "what we offer", "we promise", "benefits", "you will receive", "our offer", "perks",
            "tarjoamme", "lupaamme", "mitä tarjoamme", "meillä saat", "saat meiltä", "edut",
            "mitä me tarjoamme", "työsuhde-edut",
        ],
    }

    current_section = None
    sections = {k: [] for k in section_keywords}
    bullet_re = re.compile(r'^[-•*✓✔🎯🤝🔑💰🌟🚗⭐👇🏆⏱️]+\s*')

    for ln in lines:
        ln_low = ln.lower()
        matched_header = None
        for sec_key, sec_kws in section_keywords.items():
            if any(kw in ln_low for kw in sec_kws) and len(ln) < 80:
                matched_header = sec_key
                break

        if matched_header:
            current_section = matched_header
            continue

        if current_section and len(ln) > 5 and len(ln) < 250:
            clean = bullet_re.sub("", ln).strip()
            if clean and clean not in sections[current_section]:
                sections[current_section].append(clean)

    def _merge_colon_lines(lst):
        merged = []
        for line in lst:
            if merged and merged[-1].strip().endswith(':'):
                merged[-1] = merged[-1] + " " + line
            else:
                merged.append(line)
        return merged

    what_we_expect = _merge_colon_lines(sections["requirements"])[:12]
    what_we_offer = _merge_colon_lines(sections["benefits"])[:12]
    responsibilities = _merge_colon_lines(sections["responsibilities"])[:15]

    overview_lines = [ln for ln in lines if len(ln) > 30 and len(ln) < 300][:5]
    para1 = " ".join(overview_lines[:2]).strip()

    if responsibilities:
        para2 = "Responsibilities include: " + "; ".join(responsibilities[:4]) + "."
    else:
        para2 = ""

    if what_we_offer:
        para3 = "The company offers: " + "; ".join(what_we_offer[:4]) + "."
    else:
        para3 = ""

    description = "\n\n".join(p for p in [para1, para2, para3] if p)[:800]

    return {
        "salary_range": salary_range,
        "work_time": work_time,
        "continuity_of_work": continuity_of_work,
        "positions": positions,
        "language_requirements": language_requirements,
        "job_responsibilities": responsibilities,
        "what_we_expect": what_we_expect,
        "what_we_offer": what_we_offer,
        "description": description,
    }


def has_next_page(html: str, current_page: int) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    next_num = str(current_page + 1)
    numbered = soup.select_one(f'a.pagination__pagenum[href*="sivu={next_num}"]')
    arrow = soup.select_one('a.pagination__page-round[rel="next"], a[rel="next"]')
    return bool(numbered or arrow)


# ── Raw-job normalization ─────────────────────────────────────────────────────

def normalise_raw_job(raw: dict) -> dict:
    """
    Convert a source card into a raw job dict for rawjobs.json.
    No AI here.
    Municipality codes should be preserved in jobLocation when available.
    """
    from datetime import datetime, timedelta

    title = (raw.get("title") or "").strip()
    if title.isupper() or title.islower():
        title = title.capitalize()

    company = (raw.get("company") or "").strip()
    raw_location = raw.get("jobLocation", raw.get("location", ""))
    link = (raw.get("jobLink") or "").strip()
    apply = (raw.get("jobapply_link") or link).strip()
    raw_text = (raw.get("jobcontent") or raw.get("raw_text") or raw.get("description") or "").strip()

    raw_posted = str(raw.get("date_posted") or date.today()).strip()
    posted_dt = None
    try:
        if re.match(r"^\d{1,2}\.\d{1,2}\.(\d{4})?$", raw_posted):
            parts = raw_posted.rstrip(".").split(".")
            day, month = int(parts[0]), int(parts[1])
            year = int(parts[2]) if len(parts) > 2 and parts[2] else date.today().year
            posted_dt = datetime(year, month, day)
        else:
            posted_dt = datetime.strptime(raw_posted[:10], "%Y-%m-%d")
    except Exception:
        posted_dt = datetime.now()

    posted = posted_dt.strftime("%Y-%m-%d")
    expires = raw.get("date_expires")
    if not expires:
        expires = (posted_dt + timedelta(days=30)).strftime("%Y-%m-%d")

    # Keep municipality codes if source gives them; otherwise keep raw location tokens
    locs = normalize_job_locations(raw_location)
    location_for_id = locs[0] if locs else "Finland"

    url_hash, full_slug = make_job_id(title, location_for_id, link)

    analysed = analyse_job_content(raw_text, title=title)
    salary = analysed["salary_range"] or raw.get("salary") or ""

    return {
        "id": url_hash,
        "job_id": full_slug,
        "processed": False,

        "title": title,
        "company": company,
        "jobLocation": locs,
        "jobapply_link": apply,
        "jobLink": link,
        "job_employer_email": raw.get("job_employer_email") or "",
        "job_employer_name": raw.get("job_employer_name") or "",
        "job_employer_phone_no": raw.get("job_employer_phone_no") or "",
        "date_posted": posted,
        "date_expires": expires,
        "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),

        "open_positions": int(raw.get("open_positions") or 1),

        "salary_range": salary,
        "workTime": raw.get("workTime") or analysed["work_time"],
        "continuityOfWork": raw.get("continuityOfWork") or analysed["continuity_of_work"],
        "language_requirements": raw.get("language_requirements") or analysed["language_requirements"],
        "what_we_expect": raw.get("what_we_expect") or analysed["what_we_expect"],
        "job_responsibilities": raw.get("job_responsibilities") or analysed["job_responsibilities"],
        "what_we_offer": raw.get("what_we_offer") or analysed["what_we_offer"],

        "jobcategory_keywords": raw.get("jobcategory_keywords"),
        "job_occupations_en": raw.get("job_occupations_en"),

        "jobcontent": raw_text,
    }


# ── HTML sanitising ───────────────────────────────────────────────────────────

def _sanitise(text: str) -> str:
    """Remove script tags and unsafe HTML from scraped content."""
    if not text:
        return ""
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


# ── Main scraper ──────────────────────────────────────────────────────────────

def scrape_jobs(existing_ids: set[str], dry_run: bool = False) -> list[dict]:
    """
    Paginate Duunitori and return only new jobs.
    """
    logger.info("=== Scrape started (dry_run=%s) ===", dry_run)
    new_jobs = []
    skipped = 0

    for page_num in range(1, config.MAX_PAGES + 1):
        params = {**config.SEARCH_PARAMS, "sivu": page_num}
        logger.info("Fetching page %d → %s?%s", page_num, config.SEARCH_URL, urlencode(params))

        response = _get(config.SEARCH_URL, params=params)
        if not response:
            logger.warning("No response for page %d — stopping.", page_num)
            break

        html = response.text
        cards = parse_listings_page(html)

        if not cards:
            logger.info("No cards on page %d — end of results.", page_num)
            break

        for card in cards:
            link = card["jobLink"]
            url_hash, _ = make_job_id(card["title"], card.get("location", ""), link)
            if url_hash in existing_ids:
                logger.debug("SKIP (exists): %s", url_hash)
                skipped += 1
                continue

            logger.info("[+] PROCESSING: %s", card["title"])

            raw_text, apply_url = fetch_job_detail(link)
            raw_text = _sanitise(raw_text)
            card["raw_text"] = raw_text
            card["jobapply_link"] = apply_url or link

            job = normalise_raw_job(card)

            if job["id"] in existing_ids:
                skipped += 1
                continue

            new_jobs.append(job)
            existing_ids.add(job["id"])

        time.sleep(config.REQUEST_DELAY_SECONDS)

        if not has_next_page(html, page_num):
            logger.info("No next page after page %d.", page_num)
            break

    logger.info("=== Scrape complete — %d new, %d skipped ===", len(new_jobs), skipped)
    return new_jobs