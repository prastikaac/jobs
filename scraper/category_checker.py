"""
category_checker.py — Optimized version

Key Improvements:
- AI formats the job title first (using jobcontent) before any category check
- AI evaluates the point-wise determined category (correct vs incorrect)
- Faster inference (max_tokens=16, timeout=45)
- Removed artificial delay
- Uses Qwen2.5-1.5B recommended model
"""

import datetime
import json
import logging
import threading
import queue
import re
import urllib.request
from pathlib import Path
import config
from Job_formatter import _clean_text

# ── Setup ─────────────────────────────────────────
_SENTINEL = object()
_SCRAPER_DIR = Path(__file__).parent
_LOG_FILE = _SCRAPER_DIR / "category_checker.log"

logger = logging.getLogger("cat_checker")
if not logger.handlers:
    logger.setLevel(logging.INFO)
    fh = logging.FileHandler(_LOG_FILE, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(fh)
    logger.propagate = False

LM_STUDIO_BASE_URL = "http://localhost:1234"
LM_STUDIO_MODEL = "qwen2.5-3b-instruct"
_SENTINEL = object()

# ── Prompt ────────────────────────────────────────
_PROMPT_TMPL = """\
Keyword scoring determined this job belongs to: "{current_category}"
Job title: "{title}"

Confirm or correct the category.
- If "{current_category}" is correct or you are unsure, output: {current_category}
- If a different category CLEARLY fits better, output that category instead.

Valid categories:
{cat_list}

Rules:
- Output ONLY one exact category name from the list above
- No explanation, no punctuation, no extra words

Answer:"""

# ── Title formatter prompt ───────────────────────
_TITLE_FORMAT_PROMPT = """\
You are a professional job title formatter.
Your task: read the job posting content below and return a clean, concise, professional English job title.

Rules:
- Output ONLY the job title — nothing else. No explanation, no punctuation at the end.
- The title must be in English. Translate or infer from the content if needed.
- Keep it short and specific (2–6 words ideally).
- Use standard title case (e.g. "Senior Software Engineer", "Cleaning Specialist", "Warehouse Worker").
- Do NOT include company name, location, salary, or any other detail.
- Do NOT add any commentary or extra text.

Job posting content:
\"\"\"{jobcontent}\"\"\"

Job title:"""

# ── LM Studio helpers ─────────────────────────────

def _ask_lmstudio(model, title, current_category, valid_cats):
    cat_list = "\n".join(f"- {c}" for c in valid_cats)

    prompt = _PROMPT_TMPL.format(
        title=title,
        current_category=current_category,
        cat_list=cat_list
    )

    payload = json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant that strictly follows instructions."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.0,
        "max_tokens": 24,
        "stream": False,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{LM_STUDIO_BASE_URL}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
        raw = data["choices"][0]["message"]["content"].strip().lower()
        raw = re.sub(r"[^a-z0-9\-]", "", raw)
    except Exception as e:
        logger.warning("LM Studio error: %s", e)
        return None

    return raw

# Soft skills and generic terms that should not contribute to category scoring
_NOISE_KEYWORDS = {
    "teamwork", "communication", "motivated", "reliable", "flexible", "responsible",
    "proactive", "problem solving", "initiative", "organized", "punctual",
    "hardworking", "self-starter", "enthusiastic", "detail-oriented", "passionate",
    "team player", "dynamic", "fast-paced", "can-do attitude", "multitasking",
}

_MIN_KEYWORD_MATCHES = 2

def detect_category_by_keywords(
    title: str,
    text: str,
    occupations: list[str] | None = None,
) -> tuple[str, int]:
    """Score every category and return (best_category, best_score)."""
    title_low = _clean_text(title).lower()
    text_low = _clean_text(text).lower()
    occupations_low = [_clean_text(o).lower() for o in (occupations or [])]

    scores: dict[str, int] = {}

    if occupations_low:
        _occ_stop = {
            "and", "or", "of", "the", "a", "an", "in", "for", "to",
            "workers", "worker", "staff", "specialist", "person",
            # Generic job-title words that appear in keywords of many categories —
            # word-matching on these alone causes false cross-category hits
            "manager", "expert", "senior", "junior", "lead", "head",
            "assistant", "associate", "coordinator", "officer", "director",
            "supervisor", "executive", "consultant", "analyst", "advisor",
            "engineer", "technician", "operator", "professional",
        }

        for category, keywords in config.CATEGORY_KEYWORDS.items():
            if not keywords:
                continue

            kws_low = [_clean_text(kw).lower() for kw in keywords if _clean_text(kw)]
            occ_score = 0

            for occ in occupations_low:
                if not occ:
                    continue

                if occ in kws_low:
                    occ_score += 50
                    continue

                matched_sub = False
                for kw_low in kws_low:
                    if kw_low in occ or occ in kw_low:
                        occ_score += 35
                        matched_sub = True
                        break

                if matched_sub:
                    continue

                occ_words = [
                    w for w in occ.split()
                    if len(w) >= 4 and w not in _occ_stop
                ]
                for word in occ_words:
                    for kw_low in kws_low:
                        if word in kw_low or kw_low in word:
                            occ_score += 15
                            break

            if occ_score > 0:
                scores[category] = scores.get(category, 0) + occ_score

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
        return "other", 0

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_cat, top_score = ranked[0]

    if top_score <= 0:
        return "other", 0

    return top_cat, top_score

def format_job_title_with_ai(raw_job: dict) -> str:
    """
    Call LM Studio to produce a clean English job title from the job's content.
    Returns the formatted title string, or the original title if the AI call fails.
    The result is also written back into raw_job["title"] so all downstream
    steps automatically use the improved title.
    """
    original_title = _clean_text(raw_job.get("title", raw_job.get("id", "")))
    # Prefer translated content; fall back to raw jobcontent
    jobcontent = _clean_text(
        raw_job.get("translated_content") or raw_job.get("jobcontent", "")
    )

    if not jobcontent:
        logger.info("  Title formatter: no content available, keeping original title '%s'", original_title)
        return original_title

    # Truncate to avoid exceeding model context limits
    content_snippet = jobcontent[:2000]

    prompt = _TITLE_FORMAT_PROMPT.format(jobcontent=content_snippet)

    payload = json.dumps({
        "model": LM_STUDIO_MODEL,
        "messages": [
            {"role": "system", "content": "You are a professional job title formatter. Output only the job title."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.0,
        "max_tokens": 24,
        "stream": False,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{LM_STUDIO_BASE_URL}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = json.loads(resp.read())
        raw_title = data["choices"][0]["message"]["content"].strip()
        # Strip surrounding quotes, markdown, or extra punctuation
        raw_title = re.sub(r'^[\s"\'`]+|[\s"\'`]+$', '', raw_title).strip()
        raw_title = re.sub(r'\s+', ' ', raw_title)

        if raw_title and len(raw_title) >= 3:
            logger.info(
                "  Title formatter: '%s' → '%s'",
                original_title,
                raw_title,
            )
            raw_job["title"] = raw_title
            return raw_title
        else:
            logger.warning(
                "  Title formatter: AI returned empty/short title for '%s', keeping original",
                original_title,
            )
    except Exception as exc:
        logger.warning("  Title formatter: LM Studio error for '%s': %s", original_title, exc)

    return original_title


def determine_category(raw_job: dict) -> str:
    # ── Step 0: AI title formatting (always runs first) ───────────────────
    format_job_title_with_ai(raw_job)

    title = raw_job.get("title", raw_job.get("id", ""))
    translated_text = raw_job.get("translated_content") or raw_job.get("jobcontent", "")
    occupations = raw_job.get("jobcategory_keywords") or raw_job.get("job_occupations_en", [])

    # ── Step 1: Point-wise keyword scoring ────────────────────────────────
    top_cat, top_score = detect_category_by_keywords(
        title,
        translated_text,
        occupations=occupations,
    )
    found_category = top_cat if top_cat in config.VALID_CATEGORIES else "other"
    logger.info("  Category (scoring): %s → %s (score=%d)", title, found_category, top_score)

    # ── Step 2: AI category check ─────────────────────────────────────────
    valid_cats = list(config.VALID_CATEGORIES)
    if "other" not in valid_cats:
        valid_cats.append("other")

    ai_suggested = _ask_lmstudio(LM_STUDIO_MODEL, title, found_category, valid_cats)

    final_category = found_category
    if ai_suggested and ai_suggested in valid_cats:
        if ai_suggested != found_category:
            final_category = ai_suggested
            logger.info("  Category (AI override): %s → %s", found_category, final_category)
        else:
            logger.info("  Category (AI confirmed): %s", final_category)

    return final_category