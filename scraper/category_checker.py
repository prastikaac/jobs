"""
category_checker.py — Optimized version

Key Improvements:
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
_SENTINEL = object()

# ── Prompt (SIMPLIFIED) ───────────────────────────
_PROMPT_TMPL = """\
Is "{current_category}" the correct category for the job title "{title}"?

If correct, output: correct
If incorrect, output ONLY the best matching category from this list:

{cat_list}

Rules:
- Output only one word
- No explanation
- No punctuation

Answer:
"""

# ── LM Studio helpers ─────────────────────────────
def _detect_best_model():
    return "Qwen2.5-1.5B-Instruct"

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
        "max_tokens": 16,
        "stream": False,
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{LM_STUDIO_BASE_URL}/v1/chat/completions",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            data = json.loads(resp.read())
        raw = data["choices"][0]["message"]["content"].strip().lower()
        raw = re.sub(r"[^a-z0-9\-]", "", raw)
    except Exception as e:
        logger.warning(f"LM Studio error: {e}")
        return None

    if raw == "correct":
        return current_category

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

def determine_category(raw_job: dict) -> str:
    title = raw_job.get("title", raw_job.get("id", ""))
    translated_text = raw_job.get("translated_content") or raw_job.get("jobcontent", "")
    occupations = raw_job.get("jobcategory_keywords") or raw_job.get("job_occupations_en", [])

    # 1. Point-wise scoring
    top_cat, top_score = detect_category_by_keywords(
        title,
        translated_text,
        occupations=occupations,
    )
    found_category = top_cat if top_cat in config.VALID_CATEGORIES else "other"
    logger.info("  Category (scoring): %s → %s (score=%d)", title, found_category, top_score)

    # 2. AI check
    model = _detect_best_model()
    valid_cats = list(config.VALID_CATEGORIES)
    if "other" not in valid_cats:
        valid_cats.append("other")
        
    ai_suggested = _ask_lmstudio(model, title, found_category, valid_cats)
    
    final_category = found_category
    if ai_suggested and ai_suggested in valid_cats:
        final_category = ai_suggested
        if ai_suggested != found_category:
            logger.info("  Category (AI override): %s → %s", found_category, final_category)
        else:
            logger.info("  Category (AI confirmed): %s", final_category)

    return final_category