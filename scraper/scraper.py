"""
scraper.py — Duunitori.fi job scraper (Step 1 of the pipeline).

Scrapes jobs, normalises them into the concept.txt format, and returns:
  - new_jobs  : jobs NOT yet in jobs.json
  - all_jobs  : full merged list to be saved back to jobs.json

Output job format:
  {
    "id":          "cleaner-helsinki-a1b2c3d4",
    "title":       "Cleaner",
    "company":     "Siivous Oy",
    "description": "...",
    "jobCategory": ["Cleaning"],
    "jobLocation": ["Helsinki"],
    "jobLink":     "https://duunitori.fi/...",
    "date_posted": "2026-03-21"
  }
"""

import hashlib
import logging
import json
import re
import sys
import time
from datetime import date
from urllib.parse import urljoin, urlencode

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

    Usage:
        resp = fetch_with_retry(lambda: requests.get(url, timeout=10))
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
            _log.warning("fetch_with_retry: attempt %d/%d failed: %s. Retrying in %.1fs…",
                         attempt + 1, max_retries, exc, sleep_time)
            time.sleep(sleep_time)
    return None

def _get(url: str, params: dict = None, retries: int = 3) -> requests.Response | None:
    for attempt in range(1, retries + 1):
        try:
            resp = requests.get(
                url, params=params,
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
    loc_slug   = slugify(location.split(",")[0])[:20] if location else "finland"
    url_hash   = hashlib.md5(link.encode("utf-8")).hexdigest()[:8]
    return url_hash, f"{title_slug}-{loc_slug}-{url_hash}"


# ── Category detection ────────────────────────────────────────────────────────

def detect_categories(title: str, description: str) -> list[str]:
    """
    Keyword-based job category detection fallback.
    Returns a non-empty array with exactly ONE category; falls back to ["Other"].
    """
    haystack = (title + " " + description).lower()
    for cat, keywords in config.CATEGORY_KEYWORDS.items():
        if any(kw in haystack for kw in keywords):
            return [cat]
    return ["Other"]


# ── Location normalisation ────────────────────────────────────────────────────

def detect_locations(raw_location: str) -> list[str]:
    """
    Split a Finnish location string into a clean array of city names.
    Examples:
        "Helsinki, Espoo"  → ["Helsinki", "Espoo"]
        "Helsingin seutu"  → ["Helsinki"]
        "Koko Suomi"       → ["Finland"]
    """
    if not raw_location or str(raw_location).lower() in ["none", "", "undetermined", "not specified"]:
        return ["Finland"]

    # Normalise separators
    raw = re.sub(r"[/|;]", ",", raw_location)
    parts = [p.strip() for p in raw.split(",") if p.strip()]

    cities = []
    for part in parts:
        # Match against known cities (case-insensitive stem match)
        matched = False
        for city in config.CITY_KEYWORDS:
            if city.lower() in part.lower() or part.lower() in city.lower():
                if city not in cities:
                    cities.append(city)
                matched = True
                break
        if not matched:
            # Keep the raw part if it's short enough to be a city
            if 2 < len(part) < 40 and not any(c.isdigit() for c in part):
                # Normalize Finnish special chars
                clean = part.replace("ä", "a").replace("ö", "o").replace("å", "a")
                cap = clean.title()
                if cap not in cities:
                    cities.append(cap)

    return cities if cities else ["Finland"]


# ── Page parsing ──────────────────────────────────────────────────────────────

def _text(tag, default: str = "") -> str:
    return tag.get_text(strip=True) if tag else default


def parse_listings_page(html: str) -> list[dict]:
    """Parse a Duunitori search results page. Returns raw (untranslated) job cards."""
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
            apply_link   = urljoin(config.BASE_URL, relative_url) if relative_url else None
            company      = hover.get("data-company", "").strip()

            title_tag    = box.select_one("h3.job-box__title")
            title        = _text(title_tag)

            location_tag = box.select_one("span.job-box__job-location")
            location     = _text(location_tag).rstrip("– ").strip()

            salary_tag   = box.select_one("span.tag--salary")
            salary       = _text(salary_tag) or None

            date_tag     = box.select_one("span.job-box__job-posted")
            date_posted  = _text(date_tag).removeprefix("Julkaistu ").strip() or None

            if not apply_link or not title:
                continue

            jobs.append({
                "title":       title,
                "company":     company,
                "location":    location,
                "salary":      salary,
                "jobLink":     apply_link,
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

    # Try specific description container first
    desc_tag = (
        soup.select_one(".job-description")
        or soup.select_one("[class*='description']")
        or soup.select_one("article .content")
        or soup.select_one("main article")
    )

    if desc_tag:
        return desc_tag.get_text(separator="\n", strip=True)[:8000], job_url

    # Broad fallback - grab the largest div
    divs = soup.find_all("div")
    if divs:
        longest = max(divs, key=lambda d: len(d.get_text(strip=True)), default=None)
        if longest:
            return longest.get_text(separator="\n", strip=True)[:8000], job_url

    return "", job_url


# ── Full content analyser ─────────────────────────────────────────────────────

def analyse_job_content(text: str, title: str = "") -> dict:
    """
    Analyse the full job page text and return a rich structured dict.
    Extracts: salary, employment_type, positions, responsibilities,
    language_requirements, what_we_expect, what_we_offer, who_is_this_for, description.
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]

    # ── Salary ──────────────────────────────────────────────────────────────
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

    # ── Employment type ──────────────────────────────────────────────────────
    work_time = "Full-time"  # default
    continuity_of_work = "Permanent"  # default
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

    # ── Language requirements ────────────────────────────────────────────────
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

    # ── Positions / roles ────────────────────────────────────────────────────
    positions = []
    # Only split on clear role separators: & or / (NOT commas, which are often locations)
    if title:
        if '&' in title or '/' in title:
            parts = re.split(r'[&/]', title)
            for p in parts:
                p = p.strip().title()
                if len(p) > 3 and p not in positions:
                    positions.append(p)
    if not positions and title:
        positions = [title.strip()]

    # ── Section detection ────────────────────────────────────────────────────
    # Look for header-like lines to separate sections — includes Finnish keywords
    section_keywords = {
        "responsibilities": [
            "responsibilities", "your tasks", "what you'll do", "duties", "tasks", "what is the job",
            # Finnish
            "tehtäviin kuuluu", "tehtäväsi", "työnkuva", "vastuut", "mitä teet", "mitä työ pitää",
        ],
        "requirements": [
            "requirements", "what we expect", "what you need", "we expect", "qualifications", "skills required",
            # Finnish
            "mitä odotamme", "odotamme sinulta", "edellytämme", "vaatimukset", "toivomme sinulta",
            "mitä edellytät", "millainen olet", "etsimme", "mitä haemme",
        ],
        "benefits": [
            "we offer", "what we offer", "we promise", "benefits", "you will receive", "our offer", "perks",
            # Finnish
            "tarjoamme", "lupaamme", "mitä tarjoamme", "meillä saat", "saat meiltä", "edut",
            "mitä me tarjoamme", "työsuhde-edut",
        ],
        "who_for": [
            "who is this for", "are you", "this job is for", "ideal candidate", "who we're looking for",
            # Finnish
            "kenelle", "sopii sinulle", "kaipaatko", "haluatko",
        ],
    }

    current_section = None
    sections = {k: [] for k in section_keywords}
    bullet_re = re.compile(r'^[-•*✓✔🎯🤝🔑💰🌟🚗⭐👇🏆⏱️]+\s*')

    for ln in lines:
        ln_low = ln.lower()
        # Detect section header
        for sec_key, sec_kws in section_keywords.items():
            if any(kw in ln_low for kw in sec_kws) and len(ln) < 80:
                current_section = sec_key
                break
        else:
            # Add line to current section if it looks like a bullet point or short sentence
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
    what_we_offer  = _merge_colon_lines(sections["benefits"])[:12]
    responsibilities = _merge_colon_lines(sections["responsibilities"])[:15]
    who_is_this_for  = _merge_colon_lines(sections["who_for"])[:8]

    # Flatten responsibilities for simplicity
    job_responsibilities = responsibilities



    # ── Clean description (3-paragraph summary) ──────────────────────────────
    # Paragraph 1: company + role overview (first meaningful sentences)
    overview_lines = [ln for ln in lines if len(ln) > 30 and len(ln) < 300][:5]
    para1 = " ".join(overview_lines[:2]).strip()

    # Paragraph 2: responsibilities summary
    if responsibilities:
        para2 = "Responsibilities include: " + "; ".join(responsibilities[:4]) + "."
    else:
        para2 = ""

    # Paragraph 3: what they offer
    if what_we_offer:
        para3 = "The company offers: " + "; ".join(what_we_offer[:4]) + "."
    else:
        para3 = ""

    description = "\n\n".join(p for p in [para1, para2, para3] if p)[:800]

    return {
        "salary_range":           salary_range,
        "work_time":              work_time,
        "continuity_of_work":     continuity_of_work,
        "positions":              positions,
        "language_requirements":  language_requirements,
        "job_responsibilities":   job_responsibilities,
        "what_we_expect":         what_we_expect,
        "what_we_offer":          what_we_offer,
        "who_is_this_for":        who_is_this_for,
        "description":            description,
    }


def has_next_page(html: str, current_page: int) -> bool:
    soup = BeautifulSoup(html, "html.parser")
    next_num = str(current_page + 1)
    numbered = soup.select_one(f'a.pagination__pagenum[href*="sivu={next_num}"]')
    arrow    = soup.select_one('a.pagination__page-round[rel="next"], a[rel="next"]')
    return bool(numbered or arrow)


# ── Unified AI Processor ──────────────────────────────────────────────────────

def unified_ai_processor(text: str, fallback_category: str = "Other") -> dict:
    """
    Use local Ollama (Mistral) to extract categories and format details as clean HTML.
    Returns a dict with category, and formatted HTML strings.
    """
    default_res = {
        "category": [fallback_category],
        "description_html": "",
        "what_we_expect_html": "",
        "responsibilities_html": "",
        "what_we_offer_html": "",
        "who_is_this_for_html": "",
    }
    
    if not text or len(text) < 50:
        default_res["description_html"] = f"<p>{text}</p>" if text else ""
        return default_res

    url = "http://localhost:11434/api/generate"
    prompt = (
        "You are an expert HR assistant. Analyze the following job description. "
        "Extract the following information and return ONLY a valid JSON object without any markdown code blocks or extra text.\n"
        "Required JSON format:\n"
        "{\n"
        '  "category": "Choose exactly one from: Cleaning, Restaurant, Caregiver, Driver, Logistics, Security, IT, Sales, Construction, Hospitality, Other",\n'
        '  "description_html": "HTML formatted job overview using <p> and <ul>",\n'
        '  "what_we_expect_html": "HTML formatted expectations",\n'
        '  "responsibilities_html": "HTML formatted job responsibilities",\n'
        '  "what_we_offer_html": "HTML formatted benefits/offers",\n'
        '  "who_is_this_for_html": "HTML formatted ideal candidate description"\n'
        "}\n\n"
        "Input Text:\n"
        f"{text[:5000]}"
    )
    
    payload = {
        "model": "mistral",
        "prompt": prompt,
        "stream": False,
        "format": "json"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=60)
        if response.status_code == 200:
            content = response.json().get("response", "").strip()
            
            # Cleanup markdown block if present
            if content.startswith("```json"): content = content[7:]
            if content.startswith("```"): content = content[3:]
            if content.endswith("```"): content = content[:-3]
                
            try:
                parsed = json.loads(content.strip())
                # Ensure the category is valid
                valid_cats = list(config.CATEGORY_KEYWORDS.keys()) + ["Other"]
                cat = parsed.get("category", fallback_category)
                if cat not in valid_cats:
                    cat = fallback_category
                
                # Merge into default
                parsed_res = {
                    "category": [cat],
                    "description_html": parsed.get("description_html") or "",
                    "what_we_expect_html": parsed.get("what_we_expect_html") or "",
                    "responsibilities_html": parsed.get("responsibilities_html") or "",
                    "what_we_offer_html": parsed.get("what_we_offer_html") or "",
                    "who_is_this_for_html": parsed.get("who_is_this_for_html") or ""
                }
                
                # Use fallback description if empty
                if not parsed_res["description_html"]:
                    paras = [f"<p>{p.strip()}</p>" for p in text.split("\n\n") if p.strip()]
                    parsed_res["description_html"] = "".join(paras)
                    
                return parsed_res
            except json.JSONDecodeError as exc:
                logger.warning("JSON Decode failed from Ollama content: %s... - %s", content[:50], exc)
    except Exception as exc:
        logger.warning("Ollama API failed: %s. Falling back to defaults.", exc)
    
    # Fallback
    paras = [f"<p>{p.strip()}</p>" for p in text.split("\n\n") if p.strip()]
    default_res["description_html"] = "".join(paras)
    return default_res


# ── Normalise (Phase 1 — no AI) ───────────────────────────────────────────────

def normalise_raw_job(raw: dict) -> dict:
    """
    Convert a raw scraped card into a lightweight raw job dict for rawjobs.json.
    NO Ollama calls here — just structural extraction.
    AI formatting happens in Phase 2 (ai_processor.py).
    """
    from datetime import datetime, timedelta

    title    = (raw.get("title") or "").strip()
    if title.isupper() or title.islower():
        title = title.capitalize()

    company  = (raw.get("company") or "").strip()
    location = (raw.get("location") or "").strip()
    link     = (raw.get("jobLink") or "").strip()
    apply    = (raw.get("jobapply_link") or link).strip()
    raw_text = (raw.get("raw_text") or raw.get("description") or "").strip()

    # Standardise date_posted to YYYY-MM-DD
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

    posted  = posted_dt.strftime("%Y-%m-%d")
    expires = raw.get("date_expires")
    if not expires:
        expires = (posted_dt + timedelta(days=30)).strftime("%Y-%m-%d")

    url_hash, full_slug = make_job_id(title, location, link)
    locs   = detect_locations(location)

    # Lightweight section extraction (salary, employment type, language — no AI)
    analysed = analyse_job_content(raw_text, title=title)

    salary = analysed["salary_range"] or raw.get("salary") or ""

    return {
        # ── Identity ──────────────────────────────────────────────────────────
        "id":                   url_hash,
        "job_id":               full_slug,
        "processed":            False,   # Phase 2 flag
        # ── Basic info ────────────────────────────────────────────────────────
        "title":                title,
        "company":              company,
        "jobLocation":          locs,
        "jobapply_link":        apply,
        "jobLink":              link,
        "job_employer_email":   raw.get("job_employer_email") or "",
        "job_employer_name":    raw.get("job_employer_name") or "",
        "job_employer_phone_no": raw.get("job_employer_phone_no") or "",
        "date_posted":          posted,
        "date_expires":         expires,
        "scraped_at":           datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        # ── Open positions ────────────────────────────────────────────────────
        "open_positions":       int(raw.get("open_positions") or 1),
        # ── Structured fields (lightweight, no AI) ────────────────────────────
        "salary_range":         salary,
        "workTime":             raw.get("workTime") or analysed["work_time"],
        "continuityOfWork":     raw.get("continuityOfWork") or analysed["continuity_of_work"],
        "language_requirements": raw.get("language_requirements") or analysed["language_requirements"],
        "what_we_expect":       raw.get("what_we_expect") or analysed["what_we_expect"],
        "job_responsibilities": raw.get("job_responsibilities") or analysed["job_responsibilities"],
        "what_we_offer":        raw.get("what_we_offer") or analysed["what_we_offer"],
        "who_is_this_for":      raw.get("who_is_this_for") or analysed["who_is_this_for"],
        # ── Raw content for AI Phase 2 ────────────────────────────────────────
        "jobcontent":           raw_text,
    }


# ── HTML escaping ─────────────────────────────────────────────────────────────

def _sanitise(text: str) -> str:
    """Remove script tags and unsafe HTML from scraped content."""
    if not text:
        return ""
    # Strip script/style blocks
    text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style[^>]*>.*?</style>",  "", text, flags=re.IGNORECASE | re.DOTALL)
    # Strip remaining HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    return text.strip()


# ── Main scraper ──────────────────────────────────────────────────────────────

def scrape_jobs(existing_ids: set[str], dry_run: bool = False) -> list[dict]:
    """
    Paginate Duunitori, fetch details, translate, and return ONLY new jobs
    (those whose ID is not in existing_ids).

    Args:
        existing_ids: set of job IDs already stored in jobs.json
        dry_run:      if True, skip translation and just print cards (faster)

    Returns:
        List of normalised NEW job dicts.
    """
    logger.info("=== Scrape started (dry_run=%s) ===", dry_run)
    new_jobs = []
    skipped  = 0

    for page_num in range(1, config.MAX_PAGES + 1):
        params = {**config.SEARCH_PARAMS, "sivu": page_num}
        logger.info("Fetching page %d → %s?%s", page_num, config.SEARCH_URL, urlencode(params))

        response = _get(config.SEARCH_URL, params=params)
        if not response:
            logger.warning("No response for page %d — stopping.", page_num)
            break

        html  = response.text
        cards = parse_listings_page(html)

        if not cards:
            logger.info("No cards on page %d — end of results.", page_num)
            break

        for card in cards:
            link = card["jobLink"]

            # Quick pre-check: can we reject this job before fetching the detail page?
            url_hash, _ = make_job_id(card["title"], card["location"], link)
            if url_hash in existing_ids:
                logger.debug("SKIP (exists): %s", url_hash)
                skipped += 1
                continue

            logger.info("[+] PROCESSING: %s", card["title"])

            # Fetch full raw text (keep original for analysis before translation)
            raw_text, apply_url = fetch_job_detail(link)
            raw_text = _sanitise(raw_text)
            card["raw_text"] = raw_text
            card["jobapply_link"] = apply_url or link

            # Normalise to raw job format (no AI — Phase 1 only)
            job = normalise_raw_job(card)

            # Final duplicate check (ID may have shifted after translation)
            if job["id"] in existing_ids:
                skipped += 1
                continue

            new_jobs.append(job)
            existing_ids.add(job["id"])   # prevent intra-run duplicates

        time.sleep(config.REQUEST_DELAY_SECONDS)

        if not has_next_page(html, page_num):
            logger.info("No next page after page %d.", page_num)
            break

    logger.info(
        "=== Scrape complete — %d new, %d skipped ===",
        len(new_jobs), skipped,
    )
    return new_jobs
