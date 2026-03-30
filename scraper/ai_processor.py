"""
ai_processor.py — Phase 2: AI Formatting Queue Processor.

Formats raw jobs into clean structured JSON using Ollama and writes final data
to jobs.json. Marks rawjobs with AI processing status.

Design:
- AI reads the job content and chooses the best category from config.VALID_CATEGORIES
- AI translates title/description/list fields into English
- Python decides and locks critical factual fields:
    company, links, location, salary
- Python rejects obviously irrelevant AI output and falls back safely
"""

import json
import logging
import random
import re
from html import unescape

import requests

import config
import jobs_store
import rawjobs_store
import scraper as _scraper
import translator

logger = logging.getLogger("ai_processor")

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:1.5b"

BATCH_SIZE = 10
TIMEOUT_SECS = 150
TITLE_TIMEOUT_SECS = 45

MAX_INPUT_CHARS = 1800
MAX_DESCRIPTION_CHARS = 500
MAX_META_DESCRIPTION_CHARS = 160

DEFAULT_SALARY_TEXT = "Competitive hourly wage based on Finnish collective agreements and other company and links"

PLACEHOLDER_PATTERNS = [
    "2-4 short items",
    "2–4 short items",
    "3-5 items",
    "list of",
    "short items",
    "english job title",
    "company name",
    "salary information",
    "exact city or municipality",
    "5-8 english keywords",
    "translated english title",
    "real translated or inferred item",
    "one short english seo sentence",
    "one english paragraph",
    "real translated item",
]

FIELD_LABELS = {
    "what_we_expect": "What We Expect",
    "job_responsibilities": "Job Responsibilities",
    "what_we_offer": "What We Offer",
    "who_is_this_for": "Who Is This For",
}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _clean_text(value) -> str:
    """Normalize whitespace in text and safely handle lists/non-strings."""
    if value is None:
        return ""

    if isinstance(value, list):
        value = " ".join(_clean_text(v) for v in value if v is not None)
    elif not isinstance(value, str):
        value = str(value)

    return re.sub(r"\s+", " ", unescape(value)).strip()


def _truncate_safely(text: str, max_chars: int, suffix: str = "...") -> str:
    """Truncate text at a word boundary if it exceeds max_chars."""
    text = _clean_text(text)
    if len(text) <= max_chars:
        return text
    truncated = text[:max_chars].rsplit(" ", 1)[0].rstrip(" ,.-")
    return (truncated or text[:max_chars].rstrip(" ,.-")) + suffix


def _contains_placeholder(text: str) -> bool:
    low = _clean_text(text).lower()
    if not low:
        return False
    return any(p in low for p in PLACEHOLDER_PATTERNS)


def _looks_finnish(text: str) -> bool:
    low = f" {_clean_text(text).lower()} "
    if not low.strip():
        return False

    finnish_markers = [
        " työ", " työn", "tekijä", "myyjä", "siivooja", "kokki", "tarjoilija",
        "asiakas", "ravintola", "kahvila", "sairaanhoitaja", "lähihoitaja",
        "varasto", "toimisto", "suomi", "helsingissä", "tampereella", "turussa",
        " ja ", " sekä ", "osa-aik", "vakituinen", "määräaikainen",
        "päiväkoti", "varhaiskasvatus", "opettaja", "kunta", "parturi", "kampaamo",
        "rakennus", "kirvesmies", "siivoojia", "logistiikka", "työmaalle",
    ]
    return any(marker in low for marker in finnish_markers)


def _ensure_list(value) -> list[str]:
    if isinstance(value, list):
        cleaned = []
        for item in value:
            item = _clean_text(item)
            if item:
                cleaned.append(item)
        return cleaned

    if isinstance(value, str):
        value = _clean_text(value)
        if not value:
            return []

        parts = re.split(r"[•\n\r;|]+", value)
        cleaned = []
        for part in parts:
            part = _clean_text(part.lstrip("-").strip())
            if part:
                cleaned.append(part)
        return cleaned

    return []


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        norm = _clean_text(item).lower()
        if norm and norm not in seen:
            seen.add(norm)
            result.append(_clean_text(item))
    return result


def _clean_list_field(items, max_items: int = 5) -> list[str]:
    cleaned = []
    for item in _ensure_list(items):
        item = _clean_text(item)
        if not item:
            continue
        if _contains_placeholder(item):
            continue
        if len(item) < 3:
            continue
        cleaned.append(item)
    return _dedupe_preserve_order(cleaned)[:max_items]


def _sentence_split(text: str) -> list[str]:
    text = re.sub(r"\s+", " ", (text or "")).strip()
    if not text:
        return []
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [_clean_text(p) for p in parts if _clean_text(p)]


def _extract_bullet_like_lines(text: str) -> list[str]:
    lines = []
    for raw_line in (text or "").splitlines():
        line = _clean_text(raw_line)
        if not line:
            continue
        if len(line) > 180:
            continue
        if re.match(r"^[-•*]", raw_line.strip()) or ":" in line:
            lines.append(line.lstrip("-•* ").strip())
    return _dedupe_preserve_order(lines)


def _extract_field_items_from_raw_text(jobcontent: str, field_name: str, max_items: int = 4) -> list[str]:
    text = jobcontent or ""
    if not text:
        return []

    heading_map = {
        "what_we_expect": [
            "odotamme", "toivomme", "edellytämme", "vaatimukset",
            "we expect", "requirements", "what we expect"
        ],
        "job_responsibilities": [
            "tehtävät", "työtehtävät", "vastuut", "vastuualueet",
            "tasks", "responsibilities", "duties", "your role"
        ],
        "what_we_offer": [
            "tarjoamme", "etu", "edut", "we offer", "benefits", "offer"
        ],
        "who_is_this_for": [
            "sinulle joka", "etsimme", "sopii sinulle", "ideal candidate",
            "who is this for", "you are", "we are looking for"
        ],
    }

    markers = heading_map.get(field_name, [])
    lines = _extract_bullet_like_lines(text)

    scored = []
    for line in lines:
        low = line.lower()
        score = 0
        for marker in markers:
            if marker in low:
                score += 2
        if len(line) <= 120:
            score += 1
        if re.search(r"\b(apply|hakemus|deadline|päivä|date|email|sähköposti|phone|puhelin)\b", low):
            score -= 5
        if score > 0:
            scored.append((score, line))

    scored.sort(key=lambda x: x[0], reverse=True)
    result = [line for _, line in scored[:max_items]]
    if result:
        return _dedupe_preserve_order(result)[:max_items]

    sentences = _sentence_split(text)
    backup = []
    for s in sentences:
        low = s.lower()
        if len(s) > 140:
            continue
        if re.search(r"\b(apply|deadline|date|email|phone|sähköposti|puhelin)\b", low):
            continue
        backup.append(s)

    return _dedupe_preserve_order(backup)[:max_items]


def _build_meta_description(title: str, company: str, location: str, description: str) -> str:
    parts = []
    if title:
        parts.append(title)
    if company:
        parts.append(f"at {company}")
    if location and location.lower() != "finland":
        parts.append(f"in {location}")

    sentence = " ".join(parts).strip()
    if sentence:
        sentence = f"{sentence}. Explore this opportunity in Finland."
    elif description:
        sentence = description

    return _truncate_safely(sentence, MAX_META_DESCRIPTION_CHARS)


def _build_description_from_text(jobcontent: str, title: str, company: str) -> str:
    title = _clean_text(title)
    company = _clean_text(company)
    jobcontent = _clean_text(jobcontent)

    base = ""
    if title and company:
        base = f"{title} position at {company}."
    elif title:
        base = f"{title} position in Finland."
    else:
        base = "Job opportunity in Finland."

    if jobcontent:
        snippet = _truncate_safely(jobcontent, 260)
        return _truncate_safely(f"{base} Source job details: {snippet}", MAX_DESCRIPTION_CHARS)

    return _truncate_safely(base, MAX_DESCRIPTION_CHARS)


def extract_city_from_text(text: str) -> str:
    text_low = _clean_text(text).lower()
    for city in config.CITY_KEYWORDS:
        if city.lower() in text_low:
            return city
    return "Finland"


def detect_category_by_keywords(title: str, text: str) -> tuple[str, int]:
    title_low = _clean_text(title).lower()
    text_low = _clean_text(text).lower()

    best_category = "other"
    best_score = 0

    for category, keywords in config.CATEGORY_KEYWORDS.items():
        score = 0
        for kw in keywords:
            kw_low = _clean_text(kw).lower()
            if not kw_low:
                continue
            if kw_low in title_low:
                score += 3
            if kw_low in text_low:
                score += 1
        if score > best_score:
            best_score = score
            best_category = category

    return best_category, best_score


def _translate_title_direct(raw_title: str) -> str:
    title = _clean_text(raw_title)
    if not title:
        return ""
    # Use offline Argos model instead of Ollama
    return translator.translate_fi_to_en(title)


_COLLECTIVE_AGREEMENT_SALARY = "Competitive hourly wage based on Finnish collective agreements."

# Finnish salary phrases that mean "collective agreement wage" — normalize them immediately
_TES_PHRASES = [
    "tes:", "tes ", " tes", "ovtes", "ov-tes", "tessi", "asfalttialan", "kaupan alan",
    "tyoehtosopimus", "työehtosopimus", "mukaisesti", "perustuva", "palkkausjärjestelmä"
]


def _extract_salary_from_text(raw_job: dict) -> str:
    """
    Decide salary in Python from raw structured fields or jobcontent.
    If not found, return the fixed default text.
    """
    raw_salary = _clean_text(raw_job.get("salary_range", ""))
    text = _clean_text(raw_job.get("jobcontent", ""))

    # Normalize Finnish collective-agreement salary phrases to a clean English string
    if raw_salary:
        raw_salary_low = raw_salary.lower()
        # If it contains "TES" (or related phrases) AND doesn't have clear digits (like EUR amounts)
        # or if it's a very known pattern like "TES:n mukaisesti"
        if any(phrase in raw_salary_low for phrase in _TES_PHRASES):
            # Exception: if it contains actual numbers like "15,50 €/h", keep it for extraction
            if not any(char.isdigit() for char in raw_salary if char not in "0123456789"): 
                # This is a bit too complex, let's simplify: 
                # if it contains EUR or digits in a range pattern, keep it. 
                # Otherwise, if it has 'TES', it's almost certainly collective agreement.
                if "€" not in raw_salary and not re.search(r"\d+[\s.-]+\d+", raw_salary):
                    return _COLLECTIVE_AGREEMENT_SALARY
            # If it's a very short or specific TES-only string
            if len(raw_salary) < 30 and ("tes" in raw_salary_low or "ovtes" in raw_salary_low):
                return _COLLECTIVE_AGREEMENT_SALARY

    # Use existing if numeric, otherwise we might need to translate it
    if raw_salary and any(char.isdigit() for char in raw_salary) and "€" in raw_salary:
        return raw_salary

    salary_patterns = [
        r"(\d{1,3}(?:[.,]\d{1,2})?\s*[-–]\s*\d{1,3}(?:[.,]\d{1,2})?\s*€/h)",
        r"(\d{1,3}(?:[.,]\d{1,2})?\s*€/h)",
        r"(\d{1,5}(?:[.,]\d{1,2})?\s*[-–]\s*\d{1,5}(?:[.,]\d{1,2})?\s*€/kk)",
        r"(\d{1,5}(?:[.,]\d{1,2})?\s*€/kk)",
        r"(palkka[:\s]+[^.]{1,40})",
        r"(salary[:\s]+[^.]{1,40})",
        r"(TES[:\s]+[^.]{1,40})",
        r"(according to collective agreement[^.]{0,40})",
    ]

    matched_salary = ""
    for pattern in salary_patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            matched_salary = _clean_text(match.group(1))
            break

    # If we have a Finnish looking salary or broad text, translate it
    final_salary = matched_salary or raw_salary
    if final_salary:
        # Normalize collective-agreement phrases caught from jobcontent too
        final_salary_low = final_salary.lower()
        if any(phrase in final_salary_low for phrase in _TES_PHRASES):
            return _COLLECTIVE_AGREEMENT_SALARY
        if _looks_finnish(final_salary):
            return translator.translate_fi_to_en(final_salary)
        return final_salary

    return DEFAULT_SALARY_TEXT


def _extract_company_from_python(raw_job: dict) -> str:
    """
    Decide company in Python from raw company first, then job text.
    """
    raw_company = _clean_text(raw_job.get("company", ""))
    if raw_company and raw_company.lower() not in {"unspecified", "not specified", "none"}:
        return raw_company

    text = raw_job.get("jobcontent", "") or ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    company_patterns = [
        r"työnantaja[:\s]+(.+)",
        r"employer[:\s]+(.+)",
        r"company[:\s]+(.+)",
        r"yritys[:\s]+(.+)",
    ]

    for line in lines[:30]:
        for pattern in company_patterns:
            m = re.search(pattern, line, flags=re.IGNORECASE)
            if m:
                value = _clean_text(m.group(1))
                if value and len(value) <= 120:
                    return value

    return ""


def _extract_location_from_python(raw_job: dict) -> list[str]:
    """
    Decide location in Python from structured field first, then city keywords in raw text.
    """
    raw_location = raw_job.get("jobLocation", [])
    if isinstance(raw_location, str):
        raw_location = [raw_location]
    cleaned = [_clean_text(x) for x in raw_location if _clean_text(x)]
    if cleaned:
        return cleaned

    text = raw_job.get("jobcontent", "") or ""
    city = extract_city_from_text(text)
    return [city] if city else ["Finland"]


def _is_irrelevant_ai_output(ai_data: dict, jobcontent: str, raw_title: str) -> bool:
    ai_text = " ".join([
        ai_data.get("title", ""),
        ai_data.get("description", ""),
        " ".join(ai_data.get("job_responsibilities", [])),
        " ".join(ai_data.get("what_we_expect", [])),
    ]).lower()

    jobcontent_low = _clean_text(jobcontent).lower()
    raw_title_low = _clean_text(raw_title).lower()

    if not ai_text:
        return True

    title_tokens = [t for t in re.findall(r"[a-zA-ZåäöÅÄÖ]{4,}", raw_title_low)[:6]]
    overlap = sum(1 for tok in title_tokens if tok in ai_text or tok in jobcontent_low)

    hallucination_words = [
        "automotive", "industrial equipment", "maintenance technician",
        "repair machinery", "heavy equipment", "field technician",
        "software engineer", "data engineer"
    ]
    if any(word in ai_text for word in hallucination_words):
        if not any(word in jobcontent_low for word in hallucination_words):
            return True

    if overlap == 0 and raw_title_low:
        return True

    return False


def _sanitize_ai_output(parsed: dict, raw_job: dict, ai_category: str, valid_categories: list[str]) -> dict:
    raw_title = _clean_text(raw_job.get("title", ""))
    jobcontent = raw_job.get("jobcontent", "")

    ai_title = _clean_text(parsed.get("title", ""))
    if not ai_title or _contains_placeholder(ai_title) or _looks_finnish(ai_title):
        ai_title = _translate_title_direct(raw_title)
    if not ai_title:
        ai_title = raw_title

    category = _clean_text(ai_category)
    if category not in valid_categories:
        category = "other"

    company = _extract_company_from_python(raw_job)
    location_list = _extract_location_from_python(raw_job)
    location = _clean_text(location_list[0] if location_list else "Finland")
    salary_range = _extract_salary_from_text(raw_job)

    description = _clean_text(parsed.get("description", ""))
    if not description or _contains_placeholder(description):
        description = _build_description_from_text(jobcontent, ai_title or raw_title, company)
    if len(description.split()) < 10:
        description = _build_description_from_text(jobcontent, ai_title or raw_title, company)
    description = _truncate_safely(description, MAX_DESCRIPTION_CHARS)

    meta_description = _clean_text(parsed.get("meta_description", ""))
    if not meta_description or _contains_placeholder(meta_description):
        meta_description = _build_meta_description(ai_title or raw_title, company, location, description)
    meta_description = _truncate_safely(meta_description, MAX_META_DESCRIPTION_CHARS)

    what_we_expect = _clean_list_field(parsed.get("what_we_expect"))
    job_responsibilities = _clean_list_field(parsed.get("job_responsibilities"))
    what_we_offer = _clean_list_field(parsed.get("what_we_offer"))
    who_is_this_for = _clean_list_field(parsed.get("who_is_this_for"))

    if not what_we_expect:
        what_we_expect = _clean_list_field(raw_job.get("what_we_expect"))
    if not what_we_expect:
        what_we_expect = _extract_field_items_from_raw_text(jobcontent, "what_we_expect")

    if not job_responsibilities:
        job_responsibilities = _clean_list_field(raw_job.get("job_responsibilities"))
    if not job_responsibilities:
        job_responsibilities = _extract_field_items_from_raw_text(jobcontent, "job_responsibilities")

    if not what_we_offer:
        what_we_offer = _clean_list_field(raw_job.get("what_we_offer"))
    if not what_we_offer:
        what_we_offer = _extract_field_items_from_raw_text(jobcontent, "what_we_offer")

    if not who_is_this_for:
        who_is_this_for = _clean_list_field(raw_job.get("who_is_this_for"))
    if not who_is_this_for:
        who_is_this_for = _extract_field_items_from_raw_text(jobcontent, "who_is_this_for")

    work_time = _clean_text(raw_job.get("workTime") or "Full-time")
    continuity_of_work = _clean_text(raw_job.get("continuityOfWork") or "Permanent")
    language_requirements = _clean_list_field(raw_job.get("language_requirements") or [], max_items=4)

    search_keywords = _clean_text(parsed.get("search_keywords", ""))
    if not search_keywords or _contains_placeholder(search_keywords):
        keyword_parts = [ai_title, company, location, category]
        search_keywords = " ".join(_clean_text(x) for x in keyword_parts if _clean_text(x))

    return {
        "title": ai_title or raw_title,
        "company": company,
        "job_category": category,
        "meta_description": meta_description,
        "description": description,
        "salary_range": salary_range,
        "workTime": work_time,
        "continuityOfWork": continuity_of_work,
        "language_requirements": language_requirements[:4],
        "what_we_expect": what_we_expect[:4],
        "job_responsibilities": job_responsibilities[:4],
        "what_we_offer": what_we_offer[:4],
        "who_is_this_for": who_is_this_for[:4],
        "search_keywords": search_keywords,
        "job_location": location or "Finland",
    }


def _build_fallback_ai_data(raw_job: dict, fallback_category: str, valid_categories: list[str]) -> dict:
    raw_title = _clean_text(raw_job.get("title", ""))
    jobcontent = raw_job.get("jobcontent", "")

    title = _translate_title_direct(raw_title) or raw_title
    category = fallback_category if fallback_category in valid_categories else "other"
    company = _extract_company_from_python(raw_job)
    location_list = _extract_location_from_python(raw_job)
    location = _clean_text(location_list[0] if location_list else "Finland")
    description = _build_description_from_text(jobcontent, title, company)
    meta_description = _build_meta_description(title, company, location, description)

    data = {
        "title": title,
        "company": company,
        "job_category": category,
        "meta_description": meta_description,
        "description": description,
        "salary_range": _extract_salary_from_text(raw_job),
        "workTime": _clean_text(raw_job.get("workTime") or "Full-time"),
        "continuityOfWork": _clean_text(raw_job.get("continuityOfWork") or "Permanent"),
        "language_requirements": _clean_list_field(raw_job.get("language_requirements", []), max_items=4),
        "what_we_expect": _clean_list_field(raw_job.get("what_we_expect", [])) or _extract_field_items_from_raw_text(jobcontent, "what_we_expect"),
        "job_responsibilities": _clean_list_field(raw_job.get("job_responsibilities", [])) or _extract_field_items_from_raw_text(jobcontent, "job_responsibilities"),
        "what_we_offer": _clean_list_field(raw_job.get("what_we_offer", [])) or _extract_field_items_from_raw_text(jobcontent, "what_we_offer"),
        "who_is_this_for": _clean_list_field(raw_job.get("who_is_this_for", [])) or _extract_field_items_from_raw_text(jobcontent, "who_is_this_for"),
        "search_keywords": _clean_text(f"{title} {company} {location} {category}"),
        "job_location": location or "Finland",
    }

    return _sanitize_ai_output(data, raw_job, category, valid_categories)


# ── Ollama calls ──────────────────────────────────────────────────────────────

def _call_ollama_for_category(job: dict) -> tuple[str, bool, str]:
    """
    AI chooses the category from the allowed list by reading the job content.
    """
    valid_categories = config.VALID_CATEGORIES + (["other"] if "other" not in config.VALID_CATEGORIES else [])
    cats_str = ", ".join(valid_categories)

    text = job.get("jobcontent", "")
    title = job.get("title", "")
    occupations = ", ".join(job.get("job_occupations_en", []))
    
    context_str = f"Job Title: {title}\n"
    if occupations:
        context_str += f"Official Occupations: {occupations}\n"
    context_str += f"Job content:\n{text[:MAX_INPUT_CHARS]}"

    prompt = (
        "Read the job information and choose the single best matching category from the allowed category list.\n"
        "Return ONLY the exact category string.\n"
        "Do not explain.\n"
        "Do not return multiple categories.\n"
        "Do not invent a new category.\n\n"
        f"Allowed categories:\n{cats_str}\n\n"
        f"{context_str}"
    )

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0,
            "num_predict": 128,
            "num_ctx": 1024,
        },
    }

    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=TITLE_TIMEOUT_SECS)
        if resp.status_code != 200:
            return "other", False, f"HTTP {resp.status_code}"

        category_resp = _clean_text(resp.json().get("response", ""))
        
        # Sort valid categories by length descending to match longest first
        sorted_categories = sorted(valid_categories, key=len, reverse=True)
        matched_category = None
        for vc in sorted_categories:
            if vc.lower() in category_resp.lower():
                matched_category = vc
                break

        if not matched_category:
            return "other", False, f"invalid category: {category_resp[:50]}"
        return matched_category, True, ""
    except Exception as exc:
        return "other", False, str(exc)


def _call_ollama_for_content(text: str, raw_job: dict | None = None, ai_category: str = "other") -> tuple[dict, bool, str, str]:
    """
    AI extracts translated title + content fields only.
    Python decides company/location/salary/links.
    """
    raw_job = raw_job or {}
    valid_categories = config.VALID_CATEGORIES + (["other"] if "other" not in config.VALID_CATEGORIES else [])

    raw_context_lines = []
    if raw_job.get("title"):
        raw_context_lines.append(f"RAW TITLE: {raw_job['title']}")
    if raw_job.get("company"):
        raw_context_lines.append(f"RAW COMPANY: {raw_job['company']}")
    if raw_job.get("jobLocation"):
        raw_context_lines.append(f"RAW LOCATION: {raw_job['jobLocation']}")
    if raw_job.get("salary_range"):
        raw_context_lines.append(f"RAW SALARY: {raw_job['salary_range']}")
    if raw_job.get("workTime") or raw_job.get("continuityOfWork"):
        wt = raw_job.get("workTime", "Full-time")
        cow = raw_job.get("continuityOfWork", "Permanent")
        raw_context_lines.append(f"RAW JOB TYPE: {wt}, {cow}")
    if raw_job.get("language_requirements"):
        raw_context_lines.append(f"RAW LANGUAGES: {raw_job['language_requirements']}")

    raw_context = ""
    if raw_context_lines:
        raw_context = "--- RAW DATA CONTEXT ---\n" + "\n".join(raw_context_lines) + "\n\n"

    prompt = (
        "You are an expert job information JSON extractor.\n"
        "Process the following English job text and return EXACTLY the requested JSON.\n"
        "Return ONLY valid JSON.\n"
        "Every value must be in English.\n"
        "Use ONLY facts clearly supported by the raw title, raw context, or source job text.\n"
        "NEVER invent salary, company, location, links, benefits, responsibilities, or languages.\n"
        "If information is not clearly present, return an empty string or empty list.\n"
        "Do NOT guess.\n"
        "Do NOT create generic filler job content.\n"
        "Do NOT copy schema placeholders.\n\n"

        "STRICT RULES:\n"
        "- description must be exactly 1 paragraph, max 500 characters.\n"
        "- EVERYTHING must be in English. No Finnish snippets.\n"
        "- Do NOT include prefixes like 'Source job details:', 'Job description:', or 'RAW TITLE:'.\n"
        "- Arrays must contain only specific, supported facts from the source text.\n"
        "- Do not include deadlines, dates, phone numbers, email addresses, or apply instructions in arrays.\n\n"

        f"{raw_context}"
        f"English Source Job Text:\n{text[:MAX_INPUT_CHARS]}\n\n"

        "Return ONLY this JSON object:\n"
        "{\n"
        '  "title": "translated English title",\n'
        '  "meta_description": "short English SEO sentence or empty string",\n'
        '  "description": "one English paragraph, max 500 characters, or empty string",\n'
        '  "what_we_expect": ["supported item"],\n'
        '  "job_responsibilities": ["supported item"],\n'
        '  "what_we_offer": ["supported item"],\n'
        '  "who_is_this_for": ["supported item"],\n'
        '  "search_keywords": "5-8 English keywords or empty string"\n'
        "}"
    )

    payload = {
        "model": OLLAMA_MODEL,
        "system": (
            "Return only valid JSON in English. "
            "Use only source-supported facts. "
            "Never invent missing job information."
        ),
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0,
            "num_predict": 1024,
            "num_ctx": 2048,
        },
    }

    content = ""
    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=TIMEOUT_SECS)
        if resp.status_code != 200:
            logger.warning("Ollama returned %d", resp.status_code)
            fallback = _build_fallback_ai_data(raw_job, ai_category, valid_categories)
            return fallback, False, "error", f"HTTP {resp.status_code}"

        content = resp.json().get("response", "").strip()
        content = re.sub(r"^```(?:json)?", "", content).strip()
        content = re.sub(r"```$", "", content).strip()

        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1 and end > start:
            content = content[start:end + 1]

        parsed = json.loads(content)
        ai_results = _sanitize_ai_output(parsed, raw_job, ai_category, valid_categories)

        if _is_irrelevant_ai_output(ai_results, raw_job.get("jobcontent", ""), raw_job.get("title", "")):
            logger.warning("AI output rejected due to irrelevance")
            fallback = _build_fallback_ai_data(raw_job, ai_category, valid_categories)
            return fallback, False, "irrelevant", "AI hallucination detected"

        return ai_results, True, "success", ""

    except json.JSONDecodeError as exc:
        logger.warning("JSON decode error from Ollama: %s", exc)
        logger.warning("Raw Ollama content preview: %s", content[:1000] if content else "N/A")
        fallback = _build_fallback_ai_data(raw_job, ai_category, valid_categories)
        return fallback, False, "error", "JSON decode error"
    except requests.Timeout as exc:
        logger.warning("Ollama call timed out: %s", exc)
        fallback = _build_fallback_ai_data(raw_job, ai_category, valid_categories)
        return fallback, False, "timeout", str(exc)
    except Exception as exc:
        logger.warning("Ollama call failed (error): %s", exc)
        fallback = _build_fallback_ai_data(raw_job, ai_category, valid_categories)
        return fallback, False, "error", str(exc)


# ── Build final job from raw + AI output ─────────────────────────────────────

def _build_formatted_job(raw_job: dict, ai_data: dict) -> dict:
    category = ai_data.get("job_category") or "other"
    if category not in config.VALID_CATEGORIES:
        category = "other"

    cat_slug = config.slugify_category(category)
    hash_id = raw_job["id"]

    eng_title = ai_data.get("title") or _translate_title_direct(raw_job.get("title", "")) or raw_job.get("title", "")
    title_slug = _scraper.slugify(eng_title)[:100]

    final_location = _extract_location_from_python(raw_job)
    loc_base = final_location[0] if final_location else "Finland"
    loc_slug = _scraper.slugify(loc_base)[:50]

    english_job_id = f"{title_slug}-{loc_slug}-{hash_id}"
    job_path = f"/jobs/{cat_slug}/{english_job_id}"

    desc = ai_data.get("description", "")
    if isinstance(desc, list):
        desc = " ".join(str(x) for x in desc if str(x).strip())
    desc = _truncate_safely(desc, MAX_DESCRIPTION_CHARS)

    meta_desc = ai_data.get("meta_description", "")
    if isinstance(meta_desc, list):
        meta_desc = " ".join(str(x) for x in meta_desc if str(x).strip())
    meta_desc = _truncate_safely(meta_desc, MAX_META_DESCRIPTION_CHARS)
    if not meta_desc and desc:
        meta_desc = _truncate_safely(desc, MAX_META_DESCRIPTION_CHARS)

    safe_slug = config.get_safe_category_slug(category)
    random_num = random.randint(1, 30)
    image_url = f"{config.GITHUB_PAGES_BASE_URL}/images/jobs/{safe_slug}/{random_num}.png"

    job = {
        "id": raw_job["id"],
        "job_id": english_job_id,
        "processed": True,
        "title": eng_title,
        "company": _extract_company_from_python(raw_job),
        "job_category": category,
        "jobLocation": final_location,
        "jobapply_link": raw_job.get("jobapply_link", raw_job.get("jobLink", "")),
        "jobLink": raw_job.get("jobLink", ""),
        "job_employer_email": raw_job.get("job_employer_email", ""),
        "job_employer_name": raw_job.get("job_employer_name", ""),
        "job_employer_phone_no": raw_job.get("job_employer_phone_no", ""),
        "jobUrl": f"{config.GITHUB_PAGES_BASE_URL}{job_path}",
        "date_posted": raw_job.get("date_posted", ""),
        "date_expires": raw_job.get("date_expires", ""),
        "scraped_at": raw_job.get("scraped_at", ""),
        "open_positions": int(raw_job.get("open_positions") or 1),

        "salary_range": _extract_salary_from_text(raw_job),
        "workTime": _clean_text(raw_job.get("workTime") or "Full-time"),
        "continuityOfWork": _clean_text(raw_job.get("continuityOfWork") or "Permanent"),
        "language_requirements": _clean_list_field(raw_job.get("language_requirements") or [], max_items=4),

        "meta_description": meta_desc,
        "description": desc,

        "what_we_expect": _clean_list_field(ai_data.get("what_we_expect", [])) or _clean_list_field(raw_job.get("what_we_expect") or []),
        "job_responsibilities": _clean_list_field(ai_data.get("job_responsibilities", [])) or _clean_list_field(raw_job.get("job_responsibilities") or []),
        "what_we_offer": _clean_list_field(ai_data.get("what_we_offer", [])) or _clean_list_field(raw_job.get("what_we_offer") or []),
        "who_is_this_for": _clean_list_field(ai_data.get("who_is_this_for", [])) or _clean_list_field(raw_job.get("who_is_this_for") or []),
        "search_keywords": ai_data.get("search_keywords", ""),
        "display_mode": raw_job.get("display_mode", "fallback"),
        "image_url": image_url,
    }

    return apply_manual_fixes(job)


def apply_manual_fixes(job: dict) -> dict:
    hash_id = job["id"]
    location = job.get("jobLocation", ["Finland"])[0]
    title_slug = _scraper.slugify(job["title"])[:100]
    loc_slug = _scraper.slugify(location)[:50]
    job["job_id"] = f"{title_slug}-{loc_slug}-{hash_id}"

    new_cat = job.get("job_category", "other")
    if new_cat not in config.VALID_CATEGORIES:
        new_cat = "other"
        job["job_category"] = "other"

    cat_slug = config.slugify_category(new_cat)
    job["jobUrl"] = f"{config.GITHUB_PAGES_BASE_URL}/jobs/{cat_slug}/{job['job_id']}"

    safe_slug = config.get_safe_category_slug(new_cat)
    if "images/jobs/" not in job.get("image_url", "") or safe_slug not in job.get("image_url", ""):
        num = random.randint(1, 30)
        job["image_url"] = f"{config.GITHUB_PAGES_BASE_URL}/images/jobs/{safe_slug}/{num}.png"

    job["description"] = _truncate_safely(job.get("description", ""), MAX_DESCRIPTION_CHARS)
    job["meta_description"] = _truncate_safely(job.get("meta_description", ""), MAX_META_DESCRIPTION_CHARS)

    for field in ["what_we_expect", "job_responsibilities", "what_we_offer", "who_is_this_for"]:
        job[field] = _clean_list_field(job.get(field, []))

    # Fix any existing jobs that still carry raw Finnish collective-agreement salary text
    existing_salary = _clean_text(job.get("salary_range", ""))
    if existing_salary:
        sal_low = existing_salary.lower()
        # Much more aggressive check for manual fixes
        if any(phrase in sal_low for phrase in _TES_PHRASES) or (
            "tes" in sal_low and "€" not in existing_salary
        ):
            job["salary_range"] = _COLLECTIVE_AGREEMENT_SALARY
        elif existing_salary == "TES" or existing_salary == "OVTES":
             job["salary_range"] = _COLLECTIVE_AGREEMENT_SALARY

    return job


# ── Main processor ────────────────────────────────────────────────────────────

def process_raw_jobs(
    raw_jobs: list[dict],
    batch_size: int = BATCH_SIZE,
) -> tuple[list[dict], list[dict]]:
    """
    Process unprocessed raw jobs through Ollama in batches.

    Returns:
        (newly_formatted_jobs, updated_raw_jobs)
    """
    def _process_one(raw: dict) -> tuple[dict, bool, str, str]:
        title = raw.get("title", raw["id"])

        metadata = ""
        if raw.get("company"):
            metadata += f"COMPANY: {raw['company']}\n"
        if raw.get("salary_range"):
            metadata += f"SALARY: {raw['salary_range']}\n"
        if raw.get("language_requirements"):
            langs = raw["language_requirements"]
            metadata += f"LANGUAGES: {', '.join(langs) if isinstance(langs, list) else langs}\n"

        text = f"TITLE: {title}\n{metadata}BODY:\n" + (raw.get("jobcontent") or "")

        # 1. Translate string first using offline Argos model
        translated_text = translator.translate_fi_to_en(text)

        # 2. Extract content from the ALREADY TRANSLATED ENGLISH text
        ai_data, success, status, err = _call_ollama_for_content(translated_text, raw_job=raw, ai_category="none")

        # 3. Extract the structured content as a single string for categorization
        translated_content = " ".join([
            ai_data.get("title", ""),
            ai_data.get("description", ""),
            " ".join(ai_data.get("job_responsibilities", [])),
            " ".join(ai_data.get("what_we_expect", []))
        ]).lower()

        # 3. Search translated_content for any valid category string
        found_category = None
        # Sort by length descending to match longest precise string first (e.g. "software development" before "software")
        sorted_categories = sorted(config.VALID_CATEGORIES, key=len, reverse=True)
        for vc in sorted_categories:
            clean_vc = vc.replace("-", " ") 
            if clean_vc in translated_content:
                found_category = vc
                break

        # 4. If not found, send the TRANSLATED content to the AI to decide
        if not found_category:
            # Create a context object with translated content and official occupations
            cat_context = {
                "title": title,
                "jobcontent": translated_content,
                "job_occupations_en": raw.get("job_occupations_en", [])
            }
            ai_category, cat_ok, cat_err = _call_ollama_for_category(cat_context)
            if not cat_ok:
                logger.warning("AI category selection failed for '%s' (translated text): %s", title, cat_err)
            
            if cat_ok and ai_category in config.VALID_CATEGORIES:
                found_category = ai_category
            else:
                found_category = "other"

        # 5. Patch in the dynamically decided category
        ai_data["job_category"] = found_category
        formatted = _build_formatted_job(raw, ai_data)
        
        return formatted, success, status, err

    def _upsert(formatted_list: list[dict], new_job: dict) -> list[dict]:
        return [f for f in formatted_list if f["id"] != new_job["id"]] + [new_job]

    pending = rawjobs_store.get_unprocessed_jobs(raw_jobs)
    pending.sort(key=lambda j: j.get("retry_count", 0))
    batch = pending[:batch_size]

    if not batch:
        logger.info("No unprocessed jobs in queue.")
        return [], raw_jobs

    logger.info(
        "AI processing %d/%d unprocessed jobs (batch size=%d)",
        len(batch),
        len(pending),
        batch_size,
    )

    newly_formatted: list[dict] = []
    success_count = 0
    failure_count = 0

    for i, raw in enumerate(batch, 1):
        title = raw.get("title", raw["id"])
        logger.info("[%d/%d] AI formatting: %s", i, len(batch), title)

        formatted, success, status, err = _process_one(raw)
        newly_formatted = _upsert(newly_formatted, formatted)

        rawjobs_store.update_ai_status(
            raw_jobs,
            raw["id"],
            success=success,
            status=status,
            error=err,
        )

        if success:
            success_count += 1
            logger.info("  ✓ %s → category=%s", title, formatted.get("job_category"))
        else:
            failure_count += 1
            logger.warning("  ✗ %s → %s", title, status)

    logger.info(
        "AI processing complete. Attempted=%d, succeeded=%d, failed=%d, output_objects=%d",
        len(batch),
        success_count,
        failure_count,
        len(newly_formatted),
    )
    return newly_formatted, raw_jobs


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )

    raw_list = rawjobs_store.load_raw_jobs()
    new_jobs, updated_raw = process_raw_jobs(raw_list, batch_size=5)

    if new_jobs:
        existing_formatted = jobs_store.load_jobs()
        merged, actually_new = jobs_store.merge_new_jobs(existing_formatted, new_jobs)
        jobs_store.save_jobs(merged)
        rawjobs_store.save_raw_jobs(updated_raw)
        logger.info("Saved %d new jobs to jobs.json", len(new_jobs))
    else:
        rawjobs_store.save_raw_jobs(updated_raw)
        logger.info("No new jobs to save.")