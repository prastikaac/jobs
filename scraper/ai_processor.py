"""ai_processor.py — Phase 3: AI Generation."""

import json
import logging
import re

import requests

import config
import Job_formatter
import rawjobs_store

logger = logging.getLogger("ai_processor")

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:1.5b"

BATCH_SIZE = 10
TIMEOUT_SECS = 300
CATEGORY_TIMEOUT_SECS = 60
MAX_RETRIES = 2
MAX_INPUT_CHARS = 1100


def _clean_json_response(content: str) -> str:
    content = (content or "").strip()
    content = re.sub(r"^```(?:json)?", "", content).strip()
    content = re.sub(r"```$", "", content).strip()

    start = content.find("{")
    end = content.rfind("}")
    if start != -1 and end != -1 and end > start:
        content = content[start:end + 1]

    return content.strip()


def _extract_top_candidate_categories(title: str, text: str, top_n: int | None = None) -> list[str]:
    title_low = Job_formatter._clean_text(title).lower()
    text_low = Job_formatter._clean_text(text).lower()
    top_n = top_n or config.AI_CATEGORY_CANDIDATE_COUNT

    candidate_scores: dict[str, int] = {}
    for cat, kws in config.CATEGORY_KEYWORDS.items():
        if not kws:
            continue

        score = 0
        for kw in kws:
            kw_low = Job_formatter._clean_text(kw).lower()
            if not kw_low:
                continue
            if kw_low in title_low:
                score += 3
            if kw_low in text_low:
                score += 1

        if score > 0:
            candidate_scores[cat] = score

    ranked = sorted(candidate_scores.items(), key=lambda x: x[1], reverse=True)
    top_candidates = [cat for cat, _ in ranked[:top_n]]

    return top_candidates if top_candidates else list(config.VALID_CATEGORIES)


def _should_use_ai_category_tiebreak(top_cat: str, top_score: int, needs_ai: bool, top_candidates: list[str]) -> bool:
    """
    Be careful with AI category fallback:
    - use only if scoring is weak/ambiguous
    - shortlist only
    - do not use if title/rule signal already looks strong enough
    """
    if top_cat == "other":
        return True
    if not needs_ai:
        return False
    if top_score >= 16:
        return False
    if len(top_candidates) < 2:
        return False
    return True


def _call_ollama_for_category(job: dict, candidate_categories: list[str] | None = None) -> tuple[str, bool, str]:
    valid_categories = list(config.VALID_CATEGORIES)
    if "other" not in valid_categories:
        valid_categories.append("other")

    cats_to_use = list(candidate_categories) if candidate_categories else list(valid_categories)
    if "other" not in cats_to_use:
        cats_to_use.append("other")

    cats_str = ", ".join(cats_to_use)

    title = job.get("title", "")
    text = job.get("jobcontent", "")
    occupations = ", ".join(job.get("job_occupations_en", []))

    context_str = f"Job Title: {title}\n"
    if occupations:
        context_str += f"Official Occupations: {occupations}\n"
    context_str += f"Job content:\n{text[:MAX_INPUT_CHARS]}"

    prompt = (
        "Choose the single best matching category from the allowed category list.\n"
        "Return ONLY the exact category string.\n"
        "Do not explain.\n"
        "Do not return multiple categories.\n"
        "Do not invent a category.\n\n"
        f"Allowed categories:\n{cats_str}\n\n"
        f"{context_str}"
    )

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0,
            "num_predict": 64,
            "num_ctx": 1024,
        },
    }

    for attempt in range(1, MAX_RETRIES + 2):
        try:
            resp = requests.post(OLLAMA_URL, json=payload, timeout=CATEGORY_TIMEOUT_SECS)

            if resp.status_code != 200:
                return "other", False, f"HTTP {resp.status_code}"

            category_resp = Job_formatter._clean_text(resp.json().get("response", ""))
            sorted_categories = sorted(valid_categories, key=len, reverse=True)

            matched_category = None
            for vc in sorted_categories:
                if vc.lower() in category_resp.lower():
                    matched_category = vc
                    break

            if not matched_category:
                return "other", False, f"invalid category: {category_resp[:80]}"

            return matched_category, True, ""

        except (requests.Timeout, requests.ConnectionError) as exc:
            if attempt <= MAX_RETRIES:
                logger.warning(
                    "Category Ollama timeout/connection error (attempt %d/%d): %s",
                    attempt,
                    MAX_RETRIES + 1,
                    exc,
                )
            else:
                logger.warning("Category Ollama failed after retries: %s", exc)
                return "other", False, str(exc)

        except Exception as exc:
            logger.warning("Category Ollama failed: %s", exc)
            return "other", False, str(exc)

    return "other", False, "unknown category error"


def _call_ollama_for_content(
    translated_text: str,
    raw_job: dict | None = None,
    ai_category: str = "other",
) -> tuple[dict, bool, str, str]:
    """
    AI is used mainly for:
    - title
    - job_responsibilities
    - what_we_expect
    - what_we_offer
    - who_is_this_for
    - search_keywords

    Python remains the final authority for:
    - company
    - location
    - regions
    - salary
    - description
    - meta_description
    """
    raw_job = raw_job or {}
    valid_categories = list(config.VALID_CATEGORIES)
    if "other" not in valid_categories:
        valid_categories.append("other")

    prompt = (
        "You are a job data extractor.\n"
        "Use ONLY the provided ENGLISH jobcontent.\n"
        "Do NOT invent, assume, or add missing information.\n"
        "If a field is not clearly stated, return [] or ''.\n"
        "Return ONLY valid JSON.\n\n"

        "IMPORTANT RULES:\n"
        "1. Use only the JOBCONTENT text below.\n"
        "2. Do not invent duties, requirements, benefits, or candidate traits. Instead of making them up, just leave the list empty [].\n"
        "3. Do not include dates, deadlines, phone numbers, email addresses, or application instructions.\n"
        "4. Keep list items short, factual, and directly supported by the text. You MUST extract at least 3 items for every array. If necessary, split longer points into smaller factual points to reach the required minimum. REMOVE markdown formatting and section headers (e.g. 'Job Duties**') from lists.\n"
        "5. If title is unclear, return an empty string.\n"
        "6. search_keywords must be 5-8 relevant English keywords separated by spaces only.\n"
        "7. For who_is_this_for, extract ONLY candidate qualities/traits (e.g. 'independent', 'team player'). Do not include duties or requirements.\n\n"

        f"Category: {ai_category}\n\n"
        f"JOBCONTENT:\n{translated_text[:MAX_INPUT_CHARS]}\n\n"

        "Return ONLY this JSON:\n"
        "{\n"
        '  "title": "clean English job title",\n'
        '  "job_responsibilities": ["duty 1", "duty 2", "duty 3"],\n'
        '  "what_we_expect": ["requirement 1", "requirement 2", "requirement 3"],\n'
        '  "what_we_offer": ["benefit 1", "benefit 2", "benefit 3"],\n'
        '  "who_is_this_for": ["trait 1", "trait 2", "trait 3"],\n'
        '  "search_keywords": "keyword1 keyword2 keyword3 keyword4 keyword5"\n'
        "}"
    )

    payload = {
        "model": OLLAMA_MODEL,
        "system": (
            "You extract structured job information from provided job text only. "
            "You never invent facts. "
            "All output must be valid English JSON."
        ),
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0,
            "num_predict": 560,
            "num_ctx": 1536,
        },
    }

    content = ""
    last_exc: Exception | None = None

    for attempt in range(1, MAX_RETRIES + 2):
        try:
            resp = requests.post(OLLAMA_URL, json=payload, timeout=TIMEOUT_SECS)

            if resp.status_code != 200:
                logger.warning("Ollama returned HTTP %d", resp.status_code)
                fallback = Job_formatter.build_fallback_ai_data(raw_job, ai_category, valid_categories)
                return fallback, False, "error", f"HTTP {resp.status_code}"

            content = _clean_json_response(resp.json().get("response", ""))
            parsed = json.loads(content)

            ai_results = Job_formatter.sanitize_ai_output(parsed, raw_job, ai_category, valid_categories)

            if Job_formatter.is_irrelevant_ai_output(
                ai_results,
                raw_job.get("translated_content") or raw_job.get("jobcontent", ""),
                raw_job.get("title", ""),
            ):
                logger.warning("AI output rejected due to irrelevance")
                fallback = Job_formatter.build_fallback_ai_data(raw_job, ai_category, valid_categories)
                return fallback, False, "irrelevant", "AI hallucination detected"

            return ai_results, True, "success", ""

        except json.JSONDecodeError as exc:
            logger.warning("JSON decode error from Ollama: %s", exc)
            logger.warning("Raw Ollama content preview: %s", content[:1000] if content else "N/A")
            last_exc = exc
            break

        except (requests.Timeout, requests.ConnectionError) as exc:
            last_exc = exc
            if attempt <= MAX_RETRIES:
                logger.warning(
                    "Ollama timeout/connection error (attempt %d/%d): %s",
                    attempt,
                    MAX_RETRIES + 1,
                    exc,
                )
            else:
                logger.warning("Ollama failed after retries: %s", exc)

        except Exception as exc:
            logger.warning("Ollama failed: %s", exc)
            last_exc = exc
            break

    fallback = Job_formatter.build_fallback_ai_data(raw_job, ai_category, valid_categories)
    err_str = str(last_exc) if last_exc else "unknown error"
    status = "timeout" if isinstance(last_exc, (requests.Timeout, requests.ConnectionError)) else "error"
    return fallback, False, status, err_str


def format_translated_jobs(
    raw_jobs: list[dict],
    batch_size: int = BATCH_SIZE,
) -> tuple[list[dict], list[dict]]:
    """
    Phase 3: Format pre-translated jobs using AI for extraction
    and Python for factual/final summary fields.

    Returns:
        (newly_formatted_jobs, updated_raw_jobs)
    """

    def _format_one(raw: dict) -> tuple[dict, bool, str, str]:
        title = raw.get("title", raw["id"])
        translated_text = raw.get("translated_content") or raw.get("jobcontent", "")
        occupations = raw.get("job_occupations_en", [])

        top_cat, top_score, needs_ai = Job_formatter.detect_category_by_keywords(
            title,
            translated_text,
            occupations=occupations,
        )

        found_category = top_cat if top_cat in config.VALID_CATEGORIES else "other"

        top_candidates = _extract_top_candidate_categories(
            title,
            translated_text,
            top_n=config.AI_CATEGORY_CANDIDATE_COUNT,
        )

        if _should_use_ai_category_tiebreak(top_cat, top_score, needs_ai, top_candidates):
            cat_context = {
                "title": title,
                "jobcontent": translated_text,
                "job_occupations_en": occupations,
            }

            ai_category, cat_ok, cat_err = _call_ollama_for_category(
                cat_context,
                candidate_categories=top_candidates,
            )

            if cat_ok and ai_category in config.VALID_CATEGORIES:
                found_category = ai_category
                logger.info("  Category (AI tie-break): %s → %s", title, found_category)
            elif not cat_ok:
                logger.warning("  Category AI failed for '%s': %s", title, cat_err)
                if top_cat != "other":
                    found_category = top_cat
        else:
            logger.info("  Category (scoring): %s → %s (score=%d)", title, found_category, top_score)

        ai_data, success, status, err = _call_ollama_for_content(
            translated_text,
            raw_job=raw,
            ai_category=found_category,
        )

        ai_data["job_category"] = found_category
        raw["ai_data"] = ai_data
        raw["ai_status"] = "success" if success else status

        return raw, success, status, err

    def _upsert(formatted_list: list[dict], new_job: dict) -> list[dict]:
        return [f for f in formatted_list if f["id"] != new_job["id"]] + [new_job]

    pending = rawjobs_store.get_unprocessed_jobs(raw_jobs)
    pending.sort(key=lambda j: j.get("retry_count", 0))
    batch = pending[:batch_size]

    if not batch:
        logger.info("Phase 3: No unprocessed jobs to format.")
        return [], raw_jobs

    logger.info(
        "Phase 3: AI formatting %d/%d unprocessed jobs (batch size=%d)",
        len(batch),
        len(pending),
        batch_size,
    )

    newly_formatted: list[dict] = []
    success_count = 0
    failure_count = 0

    for i, raw in enumerate(batch, 1):
        title = raw.get("title", raw["id"])
        logger.info("[%d/%d] Formatting: %s", i, len(batch), title)

        raw_processed, success, status, err = _format_one(raw)
        newly_formatted = _upsert(newly_formatted, raw_processed)

        rawjobs_store.update_ai_status(
            raw_jobs,
            raw["id"],
            success=success,
            status=status,
            error=err,
        )

        if success:
            success_count += 1
            logger.info(
                "  ✓ %s → category=%s",
                title,
                raw_processed.get("ai_data", {}).get("job_category"),
            )
        else:
            failure_count += 1
            logger.warning("  ✗ %s → %s", title, status)

    logger.info(
        "Phase 3: AI generation complete. Attempted=%d, succeeded=%d, failed=%d",
        len(batch),
        success_count,
        failure_count,
    )

    return newly_formatted, raw_jobs