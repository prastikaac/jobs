"""Job_formatter.py - Assembles structured job data."""

import json
import logging
import os
import random
import re
from html import unescape

import config
import patch_salary
import translator
import scraper as _scraper

logger = logging.getLogger("Job_formatter")

# ── Municipality code lookup (loaded once) ────────────────────────────────────
_MUNI_CODES_PATH = os.path.join(os.path.dirname(__file__), "municipalities_codes.json")
_MUNICIPALITY_CODES: dict = {}
if os.path.exists(_MUNI_CODES_PATH):
    try:
        with open(_MUNI_CODES_PATH, "r", encoding="utf-8-sig") as _f:
            _MUNICIPALITY_CODES = json.load(_f)
    except Exception as _e:
        logger.warning("Failed to load municipalities_codes.json: %s", _e)

MAX_DESCRIPTION_CHARS = 9999  # No hard limit on description length
MAX_META_DESCRIPTION_CHARS = 160

PLACEHOLDER_PATTERNS = [
    "2-4 short items", "2–4 short items", "3-5 items",
    "list of", "short items", "english job title", "company name",
    "salary information", "exact city or municipality",
    "5-8 english keywords", "translated english title",
    "real translated or inferred item", "one short english seo sentence",
    "one english paragraph", "real translated item",
]


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
    """Truncate text at a word or sentence boundary if it exceeds max_chars."""
    text = _clean_text(text)
    if len(text) <= max_chars:
        return text

    truncated = text[:max_chars]
    
    # Check for sentence boundaries
    last_punct = max(truncated.rfind(". "), truncated.rfind("! "), truncated.rfind("? "))
    if last_punct == -1:
        last_punct = max(truncated.rfind("."), truncated.rfind("!"), truncated.rfind("?"))
        
    if last_punct > max_chars * 0.5: # only use sentence boundary if it doesn't crop too much
        return truncated[:last_punct + 1].strip()

    # Fallback to nearest word
    last_space = truncated.rfind(" ")
    if last_space > 0:
        return truncated[:last_space].rstrip(" ,.-") + suffix
    return truncated.rstrip(" ,.-") + suffix


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
        "ohjaaja", "hoitaja", "esimies", "päällikkö", "johtaja", "avustaja",
        "työntekijä", "palvelu", "huolto", "asentaja", "kuljettaja", "myynti",
        "asiakaspalvelu", "lastenhoitaja", "hammas", "fysioterapeutti",
        "insinööri", "suunnittelija", "kehittäjä", "tutkija", "projektipäällikkö",
        "tehtävä", "haku", "avoinna", "haemme", "etsimme", "tarjoamme",
        "kokemus", "koulutus", "osaaminen", "edellytämme", "toivomme",
        "työsuhde", "palkka", "lisätieto", "yhteystiedot",
        "ämme", "äinen", "öinti", "öissä", "ässä", "ään", "ältä", "änä",
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


def _apply_grammar_rules(text: str) -> str:
    if not text:
        return text
    text = str(text).strip()

    if text.isupper():
        text = text.lower()

    if not text:
        return text

    text = text[0].upper() + text[1:]
    text = re.sub(r"(?<=\. )[a-zåäö]", lambda m: m.group(0).upper(), text)
    return text


def _clean_list_field(items, max_items: int = 8) -> list[str]:
    cleaned = []
    
    skip_headers = {
        "job duties", "requirements", "we require", "job description", 
        "what we expect", "what we offer", "we offer", "advantages", 
        "responsibilities", "tasks", "duties", "qualifications", "who is this for"
    }
    
    for item in _ensure_list(items):
        item = _apply_grammar_rules(_clean_text(item))
        item = re.sub(r"[*:]+$", "", item).strip()
        item = item.replace("**", "").strip()
        
        if not item:
            continue
        if _contains_placeholder(item):
            continue
        if item.lower() in skip_headers:
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


def _extract_field_items_from_raw_text(jobcontent: str, field_name: str, max_items: int = 6) -> list[str]:
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




    # ── Helper: lowercase first char for mid-sentence usage ───────────────────
    def _lc(text: str) -> str:
        if not text:
            return text
        if len(text) > 1 and text[0].isupper() and text[1:2].isupper():
            return text
        return text[0].lower() + text[1:]

    # ── Gather material ────────────────────────────────────────────────────────
    responsibilities = [_clean_text(r) for r in (d.get("job_responsibilities") or []) if _clean_text(r)]
    what_we_offer    = [_clean_text(o) for o in (d.get("what_we_offer")        or []) if _clean_text(o)]

    loc_str      = location if location and location.lower() != "finland" else "Finland"
    work_time    = _clean_text(d.get("workTime") or "Full-time")
    work_env     = f"{loc_str}, {work_time}" if work_time else loc_str

    variables = {
        "job_title": title or "this position",
        "location": loc_str,
        "key_benefit_1": _lc(what_we_offer[0]) if len(what_we_offer) > 0 else "competitive salary",
        "key_benefit_2": _lc(what_we_offer[1]) if len(what_we_offer) > 1 else "career growth",
        "benefits_list": _lc(_join_list(what_we_offer, 2, "competitive benefits")),
        "key_responsibility_1": _lc(responsibilities[0]) if len(responsibilities) > 0 else "supporting daily operations",
        "key_responsibility_2": _lc(responsibilities[1]) if len(responsibilities) > 1 else "contributing to team goals",
        "main_purpose_of_role": _lc(_join_list(responsibilities, 2, "delivering quality service")),
        "work_environment": work_env
    }

    # ── Pick template randomly ──────────────────────────────────────────────
    template = random.choice(templates)
    try:
        meta = template.format_map(variables)
    except KeyError as e:
        logger.warning("Missing meta template variable %s, using fallback", e)
        class _SafeDict(dict):
            def __missing__(self, key):
                return "{" + key + "}"
        meta = template.format_map(_SafeDict(variables))

    meta = _clean_text(meta)
    return _truncate_safely(meta, MAX_META_DESCRIPTION_CHARS, suffix="")








# Soft skills and generic terms that should not contribute to category scoring
_NOISE_KEYWORDS = {
    "teamwork", "communication", "motivated", "reliable", "flexible", "responsible",
    "proactive", "problem solving", "initiative", "organized", "punctual",
    "hardworking", "self-starter", "enthusiastic", "detail-oriented", "passionate",
    "team player", "dynamic", "fast-paced", "can-do attitude", "multitasking",
}

_MIN_KEYWORD_MATCHES = 2
_CONFIDENCE_GAP = 8


def detect_category_by_keywords(
    title: str,
    text: str,
    occupations: list[str] | None = None,
) -> tuple[str, int, bool]:
    """Score every category and return (best_category, best_score, needs_ai_tiebreaker).

    Scoring priority (highest to lowest):
      +50  ESCO occupation label exactly matches a category keyword entry
      +35  ESCO occupation label fully contains (or is contained by) a category keyword
      +15  A meaningful word from an ESCO occupation label matches a category keyword
      +12  Job title exactly matches a category keyword
      +8   Job title contains a category keyword
      +3x  Keyword appears in job text (capped at 3 occurrences)
    """
    title_low = _clean_text(title).lower()
    text_low = _clean_text(text).lower()
    occupations_low = [_clean_text(o).lower() for o in (occupations or [])]

    scores: dict[str, int] = {}

    # ── Pass 1: ESCO occupation label scoring (highest priority) ─────────────
    # jobcategory_keywords are authoritative ESCO prefLabel/altLabel strings.
    # Score them directly against job_categories.json to produce strong signals.
    if occupations_low:
        _occ_stop = {
            "and", "or", "of", "the", "a", "an", "in", "for", "to",
            "workers", "worker", "staff", "specialist", "person",
        }

        for category, keywords in config.CATEGORY_KEYWORDS.items():
            if not keywords:
                continue

            kws_low = [_clean_text(kw).lower() for kw in keywords if _clean_text(kw)]
            occ_score = 0

            for occ in occupations_low:
                if not occ:
                    continue

                # Exact match — occupation label is a listed keyword
                if occ in kws_low:
                    occ_score += 50
                    continue

                # Substring containment match
                # e.g. keyword "carpenter" inside "carpenters and joiners"
                matched_sub = False
                for kw_low in kws_low:
                    if kw_low in occ or occ in kw_low:
                        occ_score += 35
                        matched_sub = True
                        break

                if matched_sub:
                    continue

                # Word-level match: score each meaningful word of the occupation
                occ_words = [
                    w for w in occ.split()
                    if len(w) >= 4 and w not in _occ_stop
                ]
                for word in occ_words:
                    for kw_low in kws_low:
                        if word in kw_low or kw_low in word:
                            occ_score += 15
                            break  # count each occ_word once per category

            if occ_score > 0:
                scores[category] = scores.get(category, 0) + occ_score

    # ── Pass 2: Standard title / text keyword scoring ────────────────────────
    for category, keywords in config.CATEGORY_KEYWORDS.items():
        if not keywords:
            continue

        score = 0
        distinct_hits = 0

        for kw in keywords:
            kw_low = _clean_text(kw).lower()
            if not kw_low or kw_low in _NOISE_KEYWORDS:
                continue

            hit_this_kw = False

            if kw_low == title_low:
                score += 12
                hit_this_kw = True
            elif kw_low in title_low:
                score += 8
                hit_this_kw = True

            if kw_low in text_low:
                occurrences = min(text_low.count(kw_low), 3)
                score += occurrences * 3
                hit_this_kw = True

            if len(kw_low.split()) == 1 and hit_this_kw:
                score += 1

            if hit_this_kw:
                distinct_hits += 1

        if distinct_hits == 1 and score <= 4:
            score -= 8

        if distinct_hits >= _MIN_KEYWORD_MATCHES or score >= 8:
            scores[category] = scores.get(category, 0) + score

    if not scores:
        return "other", 0, False

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_cat, top_score = ranked[0]
    second_score = ranked[1][1] if len(ranked) > 1 else 0

    needs_ai = (top_score - second_score) < _CONFIDENCE_GAP

    if top_score <= 0:
        return "other", 0, False

    return top_cat, top_score, needs_ai


def _translate_title_direct(raw_title: str) -> str:
    title = _clean_text(raw_title)
    if not title:
        return ""
    return translator.translate_fi_to_en(title)


def _translate_text_direct(text: str) -> str:
    cleaned = _clean_text(text)
    if not cleaned:
        return ""
    return translator.translate_fi_to_en(cleaned)


def _translate_list_direct(items: list[str]) -> list[str]:
    return [_translate_text_direct(item) for item in items if item]


def _extract_company_from_python(raw_job: dict) -> str:
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


def _resolve_municipality_codes(raw_list: list[str]) -> list[str]:
    """
    Convert raw municipality codes (e.g. ["564", "091"]) to municipality names.
    Non-numeric tokens are preserved.
    """
    resolved = []
    for token in raw_list:
        token = _clean_text(token)
        if not token:
            continue

        if token.isdigit() or (len(token) == 3 and token.lstrip("0").isdigit()):
            entry = _MUNICIPALITY_CODES.get(token)
            if entry and "KUNTANIMIFI" in entry:
                resolved.append(entry["KUNTANIMIFI"])
            else:
                resolved.append(token)
        else:
            resolved.append(token)

    return _dedupe_preserve_order(resolved)


def _resolve_regions_from_municipality_codes(raw_list: list[str]) -> list[str]:
    """
    Convert raw municipality codes to region names using MAAKUNTANIMIFI.
    """
    resolved = []
    for token in raw_list:
        token = _clean_text(token)
        if not token:
            continue

        if token.isdigit() or (len(token) == 3 and token.lstrip("0").isdigit()):
            entry = _MUNICIPALITY_CODES.get(token)
            if entry and entry.get("MAAKUNTANIMIFI"):
                resolved.append(entry["MAAKUNTANIMIFI"])

    return _dedupe_preserve_order([_clean_text(x) for x in resolved if _clean_text(x)])


def _normalize_raw_location_tokens(raw_location) -> list[str]:
    if isinstance(raw_location, str):
        return [p.strip() for p in re.split(r"[,;]", raw_location) if p.strip()]
    if isinstance(raw_location, list):
        return [_clean_text(x) for x in raw_location if _clean_text(x)]
    return []


def _extract_location_from_python(raw_job: dict) -> list[str]:
    """
    Municipality-code-first location extraction.
    No CITY_KEYWORDS fallback.
    """
    raw_location = _normalize_raw_location_tokens(raw_job.get("jobLocation", []))
    if raw_location:
        resolved = _resolve_municipality_codes(raw_location)
        cleaned = [_clean_text(x) for x in resolved if _clean_text(x)]
        if cleaned:
            return cleaned

    return ["Finland"]


def _extract_regions_from_python(raw_job: dict) -> list[str]:
    """
    Extract regions from municipality codes via MAAKUNTANIMIFI.
    """
    raw_location = _normalize_raw_location_tokens(raw_job.get("jobLocation", []))
    if raw_location:
        regions = _resolve_regions_from_municipality_codes(raw_location)
        if regions:
            return regions

    return []


def is_irrelevant_ai_output(ai_data: dict, jobcontent: str, raw_title: str) -> bool:
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


def sanitize_ai_output(parsed: dict, raw_job: dict, ai_category: str, valid_categories: list[str]) -> dict:
    raw_title = _clean_text(raw_job.get("title", ""))
    jobcontent = raw_job.get("translated_content") or raw_job.get("jobcontent", "")

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
    regions_list = _extract_regions_from_python(raw_job)
    location = _clean_text(location_list[0] if location_list else "Finland")
    salary_range = patch_salary.extract_salary_from_text(raw_job)

    def _sanitize_and_translate_list(ai_list, raw_list, field_name, min_items: int = 3):
        cleaned = _clean_list_field(ai_list, max_items=6)
        if not cleaned or any(_looks_finnish(x) for x in cleaned):
            fallback = _clean_list_field(raw_list, max_items=6)
            if not fallback:
                fallback = _extract_field_items_from_raw_text(jobcontent, field_name)
            cleaned = _translate_list_direct(fallback)
            
        if len(cleaned) < min_items:
            extra = _extract_field_items_from_raw_text(jobcontent, field_name, max_items=6)
            extra_translated = _translate_list_direct(extra)
            seen = {x.lower() for x in cleaned}
            for item in extra_translated:
                if len(cleaned) >= min_items:
                    break
                if item.lower() not in seen:
                    cleaned.append(item)
                    seen.add(item.lower())
                    
        # Force minimum 3 items if still lacking
        if len(cleaned) < min_items:
            fallbacks = {
                "what_we_expect": ["Positive attitude and reliability", "Ability to work effectively", "Willingness to learn"],
                "job_responsibilities": ["Daily operational tasks", "Supporting the team", "Ensuring quality service"],
                "what_we_offer": ["Professional work environment", "Supportive team", "Valuable experience"],
            }
            needed = min_items - len(cleaned)
            for f_item in fallbacks.get(field_name, [])[:needed]:
                cleaned.append(f_item)
                
        return cleaned

    what_we_expect = _sanitize_and_translate_list(
        parsed.get("what_we_expect"),
        raw_job.get("what_we_expect"),
        "what_we_expect"
    )
    job_responsibilities = _sanitize_and_translate_list(
        parsed.get("job_responsibilities"),
        raw_job.get("job_responsibilities"),
        "job_responsibilities"
    )
    what_we_offer = _sanitize_and_translate_list(
        parsed.get("what_we_offer"),
        raw_job.get("what_we_offer"),
        "what_we_offer"
    )

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
        "meta_description": "",
        "formatted_description": "",
        "salary_range": salary_range,
        "workTime": work_time,
        "continuityOfWork": continuity_of_work,
        "language_requirements": language_requirements[:4],
        "what_we_expect": what_we_expect[:6],
        "job_responsibilities": job_responsibilities[:6],
        "what_we_offer": what_we_offer[:6],
        "search_keywords": search_keywords,
        "job_location": location or "Finland",
        "job_regions": regions_list,
    }


def build_fallback_ai_data(raw_job: dict, fallback_category: str, valid_categories: list[str]) -> dict:
    raw_title = _clean_text(raw_job.get("title", ""))
    jobcontent = raw_job.get("translated_content") or raw_job.get("jobcontent", "")

    title = _translate_title_direct(raw_title) or raw_title
    category = fallback_category if fallback_category in valid_categories else "other"
    company = _extract_company_from_python(raw_job)
    location_list = _extract_location_from_python(raw_job)
    location = _clean_text(location_list[0] if location_list else "Finland")

    data = {
        "title": title,
        "company": company,
        "job_category": category,
        "meta_description": "",
        "formatted_description": _clean_text(jobcontent),
        "salary_range": patch_salary.extract_salary_from_text(raw_job),
        "workTime": _translate_text_direct(_clean_text(raw_job.get("workTime") or "Full-time")),
        "continuityOfWork": _translate_text_direct(_clean_text(raw_job.get("continuityOfWork") or "Permanent")),
        "language_requirements": _translate_list_direct(_clean_list_field(raw_job.get("language_requirements", []), max_items=4)),
        "what_we_expect": _translate_list_direct(_clean_list_field(raw_job.get("what_we_expect", []), max_items=6) or _extract_field_items_from_raw_text(jobcontent, "what_we_expect")),
        "job_responsibilities": _translate_list_direct(_clean_list_field(raw_job.get("job_responsibilities", []), max_items=6) or _extract_field_items_from_raw_text(jobcontent, "job_responsibilities")),
        "what_we_offer": _translate_list_direct(_clean_list_field(raw_job.get("what_we_offer", []), max_items=6) or _extract_field_items_from_raw_text(jobcontent, "what_we_offer")),
        "search_keywords": _clean_text(f"{title} {company} {location} {category}"),
        "job_location": location or "Finland",
        "job_regions": _extract_regions_from_python(raw_job),
    }

    return sanitize_ai_output(data, raw_job, category, valid_categories)


def _build_formatted_job(raw_job: dict, ai_data: dict) -> dict:
    category = ai_data.get("job_category") or "other"
    if category not in config.VALID_CATEGORIES:
        category = "other"

    cat_slug = config.slugify_category(category)
    hash_id = raw_job["id"]

    eng_title = _apply_grammar_rules(
        ai_data.get("title") or _translate_title_direct(raw_job.get("title", "")) or raw_job.get("title", "")
    )
    title_slug = _scraper.slugify(eng_title)[:100]

    final_location = _extract_location_from_python(raw_job)
    final_regions = _extract_regions_from_python(raw_job)
    loc_base = final_location[0] if final_location else "Finland"
    loc_slug = _scraper.slugify(loc_base)[:50]

    english_job_id = f"{title_slug}-{loc_slug}-{hash_id}"
    job_path = f"/jobs/{cat_slug}/{english_job_id}"

    desc = ai_data.get("formatted_description") or ai_data.get("description", "")
    if isinstance(desc, list):
        desc = " ".join(str(x) for x in desc if str(x).strip())
    desc = str(desc).replace("**", "").replace("*", "")

    meta_desc = ai_data.get("meta_description", "")
    if isinstance(meta_desc, list):
        meta_desc = " ".join(str(x) for x in meta_desc if str(x).strip())
    meta_desc = str(meta_desc).replace("**", "").replace("*", "")
    meta_desc = _truncate_safely(meta_desc, MAX_META_DESCRIPTION_CHARS)
    safe_slug = config.get_safe_category_slug(category)
    random_num = random.randint(1, 30)
    image_url = f"{config.GITHUB_PAGES_BASE_URL}/images/jobs/{safe_slug}/{random_num}.png"

    raw_apply = raw_job.get("jobapply_link", raw_job.get("jobLink", ""))
    employer_email = raw_job.get("job_employer_email", "")

    is_email_apply = raw_apply.startswith("mailto:")
    import urllib.parse

    if is_email_apply and not employer_email:
        extracted = raw_apply[7:].split("?")[0]
        employer_email = urllib.parse.unquote(extracted).strip()

    if not is_email_apply and employer_email and (not raw_apply or "tyomarkkinatori.fi" in raw_apply):
        is_email_apply = True

    if is_email_apply and employer_email:
        subject_raw = f"Application for the Job - {eng_title}"
        body_raw = (
            f"Dear Hiring Manager,\n\n"
            f"I hope this message finds you well.\n\n"
            f"I am writing to express my interest in the {eng_title}. "
            f"I am motivated, reliable, and eager to contribute my skills and experience to your team.\n\n"
            f"I have experience in relevant tasks and a strong ability to adapt quickly to new environments. "
            f"I take pride in being hardworking, detail-oriented, and maintaining a positive attitude at work. "
            f"I am confident that I can add value to your organization.\n\n"
            f"Please find my CV & Cover Letter attached for your review. "
            f"I would welcome the opportunity to discuss how my skills and experience align with your needs.\n\n"
            f"Thank you for your time and consideration. I look forward to hearing from you.\n\n"
            f"Kind regards,\nYOUR_NAME"
        )

        subject_encoded = urllib.parse.quote(subject_raw)
        body_encoded = urllib.parse.quote(body_raw)
        final_jobapply_link = f"mailto:{employer_email}?subject={subject_encoded}&body={body_encoded}"
    else:
        final_jobapply_link = raw_apply

    job = {
        "id": raw_job["id"],
        "job_id": english_job_id,
        "processed": True,
        "title": eng_title,
        "company": _extract_company_from_python(raw_job),
        "job_category": category,
        "jobLocation": final_location,
        "jobRegions": final_regions,
        "jobapply_link": final_jobapply_link,
        "jobLink": raw_job.get("jobLink", ""),
        "job_employer_email": raw_job.get("job_employer_email", ""),
        "job_employer_name": raw_job.get("job_employer_name", ""),
        "job_employer_phone_no": raw_job.get("job_employer_phone_no", ""),
        "jobUrl": f"{config.GITHUB_PAGES_BASE_URL}{job_path}",
        "date_posted": raw_job.get("date_posted", ""),
        "date_expires": raw_job.get("date_expires", ""),
        "scraped_at": raw_job.get("scraped_at", ""),
        "open_positions": int(raw_job.get("open_positions") or 1),

        "salary_range": patch_salary.extract_salary_from_text(raw_job),
        "workTime": _clean_text(raw_job.get("workTime") or "Full-time"),
        "continuityOfWork": _clean_text(raw_job.get("continuityOfWork") or "Permanent"),
        "language_requirements": _clean_list_field(raw_job.get("language_requirements") or [], max_items=4),

        "meta_description": meta_desc,
        "description": desc,

        "what_we_expect": _clean_list_field(ai_data.get("what_we_expect", []), max_items=6),
        "job_responsibilities": _clean_list_field(ai_data.get("job_responsibilities", []), max_items=6),
        "what_we_offer": _clean_list_field(ai_data.get("what_we_offer", []), max_items=6),
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

    def _capitalize_sentences(s: str) -> str:
        s = str(s or "").strip()
        if not s:
            return s
        if s.isupper():
            s = s.lower()
        return re.sub(r"(^|[.!?]\s+)([^\W_])", lambda m: m.group(1) + m.group(2).upper(), s)

    if isinstance(job.get("title"), str) and job["title"].isupper():
        job["title"] = job["title"].title()
    if isinstance(job.get("company"), str) and job["company"].isupper():
        job["company"] = job["company"].title()

    job["meta_description"] = _truncate_safely(job.get("meta_description", ""), MAX_META_DESCRIPTION_CHARS)

    for field in ["what_we_expect", "job_responsibilities", "what_we_offer"]:
        job[field] = [_capitalize_sentences(item) for item in _clean_list_field(job.get(field, []), max_items=6)]

    existing_salary = _clean_text(job.get("salary_range", ""))
    if existing_salary and patch_salary.is_tes(existing_salary):
        job["salary_range"] = patch_salary.CLEAN_SALARY

    job = _sweep_finnish_from_job(job)
    return job


def _sweep_finnish_from_job(job: dict) -> dict:
    text_fields = ["title", "description", "meta_description", "salary_range", "search_keywords",
                   "workTime", "continuityOfWork"]
    for field in text_fields:
        value = job.get(field, "")
        if value and isinstance(value, str) and _looks_finnish(value):
            translated = translator.translate_fi_to_en(value)
            if translated and translated.strip():
                logger.debug("Finnish detected in '%s', translated: %s → %s", field, value[:50], translated[:50])
                job[field] = translated

    list_fields = ["what_we_expect", "job_responsibilities", "what_we_offer",
                   "language_requirements", "jobRegions", "jobLocation"]
    for field in list_fields:
        items = job.get(field, [])
        if not isinstance(items, list):
            continue
        new_items = []
        for item in items:
            if item and isinstance(item, str) and _looks_finnish(item) and field not in {"jobRegions", "jobLocation"}:
                translated = translator.translate_fi_to_en(item)
                new_items.append(translated if translated and translated.strip() else item)
            else:
                new_items.append(item)
        job[field] = new_items

    return job


def format_jobs(raw_jobs: list[dict]) -> list[dict]:
    formatted_jobs = []
    for raw in raw_jobs:
        if "ai_data" in raw:
            final_job = _build_formatted_job(raw, raw["ai_data"])
            formatted_jobs.append(final_job)
        else:
            fallback_title = _translate_title_direct(raw.get("title", "")) or raw.get("title", "")
            fallback_location_list = _extract_location_from_python(raw)
            fallback_location = fallback_location_list[0] if fallback_location_list else "Finland"
            fallback_company = _extract_company_from_python(raw)
            translated_content = raw.get("translated_content") or raw.get("jobcontent", "")

            fallback_data = {
                "title": fallback_title,
                "description": _clean_text(translated_content),
                "formatted_description": _clean_text(translated_content),
                "meta_description": "",
                "job_category": "other",
                "job_regions": _extract_regions_from_python(raw),
            }
            final_job = _build_formatted_job(raw, fallback_data)
            formatted_jobs.append(final_job)

    return formatted_jobs