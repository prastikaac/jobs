"""ai_processor.py — Phase 3: AI Generation."""

import json
import logging
import re

import requests

import config
import Job_formatter
import category_post_check
import rawjobs_store

logger = logging.getLogger("ai_processor")

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:1.5b"

BATCH_SIZE = 0
TIMEOUT_SECS = 600
CATEGORY_TIMEOUT_SECS = 120
MAX_RETRIES = 2


def _clean_json_response(content: str) -> str:
    content = (content or "").strip()
    content = re.sub(r"^```(?:json)?", "", content).strip()
    content = re.sub(r"```$", "", content).strip()

    start = content.find("{")
    end = content.rfind("}")
    if start != -1 and end != -1 and end > start:
        content = content[start:end + 1]

    return content.strip()


def _normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip()


def _strip_wrapping_quotes(text: str) -> str:
    text = (text or "").strip()

    # Remove repeated wrapping quotes if the whole output is quoted
    while len(text) >= 2 and (
        (text[0] == '"' and text[-1] == '"') or
        (text[0] == "'" and text[-1] == "'") or
        (text[0] == "“" and text[-1] == "”") or
        (text[0] == "‘" and text[-1] == "’")
    ):
        text = text[1:-1].strip()

    return text


def _clean_leading_punctuation(text: str) -> str:
    text = (text or "").strip()
    text = re.sub(r'^[\s"\'“”‘’:;,\-–—]+', "", text)
    return text.strip()


def _sanitize_plain_output(text: str) -> str:
    text = (text or "").strip()
    text = re.sub(r"^```(?:text)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()
    text = _normalize_whitespace(text)
    text = _strip_wrapping_quotes(text)
    text = _clean_leading_punctuation(text)
    text = text.replace("*", "")
    return _normalize_whitespace(text)


def _clean_meta_text(text: str) -> str:
    text = _sanitize_plain_output(text)

    # Remove accidental escaped quotes at the beginning/end
    text = re.sub(r'^\\"+', "", text).strip()
    text = re.sub(r'\\"+$', "", text).strip()

    # Remove any remaining leading quote-like characters again
    text = re.sub(r'^[\'"“”‘’]+', "", text).strip()
    text = re.sub(r'[\'"“”‘’]+$', "", text).strip()

    return _normalize_whitespace(text)


def _trim_to_sentence_boundary(text: str, min_len: int = 150, max_len: int = 160) -> str:
    text = _clean_meta_text(text)

    if not text:
        return ""

    if len(text) <= max_len:
        return text

    truncated = text[:max_len]

    # Prefer ending at the last full sentence within the limit
    sentence_endings = [truncated.rfind("."), truncated.rfind("!"), truncated.rfind("?")]
    last_punct = max(sentence_endings)

    if last_punct >= 0 and (last_punct + 1) >= min_len:
        return truncated[: last_punct + 1].strip()

    # Otherwise, trim at the last safe space so words are not cut in half
    last_space = truncated.rfind(" ")
    if last_space > 0:
        trimmed = truncated[:last_space].rstrip(" ,;:-")
        if len(trimmed) >= min_len:
            return trimmed

    # Final fallback
    return truncated.rstrip(" ,;:-").strip()


def _trim_description_safely(text: str, max_len: int = 800) -> str:
    text = _sanitize_plain_output(text)

    if not text:
        return ""

    if len(text) <= max_len:
        return text

    truncated = text[:max_len]

    # Prefer full sentence ending
    sentence_endings = [truncated.rfind("."), truncated.rfind("!"), truncated.rfind("?")]
    last_punct = max(sentence_endings)

    # Keep reasonably sized full sentence if found
    if last_punct >= int(max_len * 0.6):
        return truncated[: last_punct + 1].strip()

    # Fallback: trim at last safe space, no mid-word cut
    last_space = truncated.rfind(" ")
    if last_space > 0:
        return truncated[:last_space].rstrip(" ,;:-").strip()

    return truncated.rstrip(" ,;:-").strip()


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
    - search_keywords

    AI also generates separately:
    - formatted_description
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
        "2. Do not invent duties, requirements, benefits, or candidate traits. Instead of making them up, just leave the list empty [] or the string empty ''.\n"
        "3. Do not include dates, deadlines, phone numbers, email addresses, or application instructions.\n"
        "4. Keep list items short, factual, and directly supported by the text. Extract up to 3-6 strong items per array when clearly supported by the text. If a field is not clearly stated, return [].\n"
        "5. If title is unclear, return an empty string.\n"
        "6. search_keywords must be 5-8 relevant English keywords separated by spaces only.\n"
        "7. Remove markdown formatting and section labels from extracted values.\n\n"

        f"Category: {ai_category}\n\n"
        f"JOBCONTENT:\n{translated_text}\n\n"

        "Return ONLY this JSON:\n"
        "{\n"
        '  "title": "clean English job title",\n'
        '  "job_responsibilities": ["duty 1", "duty 2"],\n'
        '  "what_we_expect": ["requirement 1", "requirement 2"],\n'
        '  "what_we_offer": ["benefit 1", "benefit 2"],\n'
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
        "format": "https://findjobsinfinland.fi/json",
        "options": {
            "temperature": 0,
            "num_predict": 520,
            "num_ctx": 4096,
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
            logger.warning("https://findjobsinfinland.fi/jsON decode error from Ollama: %s", exc)
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


def _build_description_prompt(raw_job: dict) -> str:
    title = Job_formatter._clean_text(raw_job.get("title", ""))
    company = Job_formatter._clean_text(raw_job.get("company", ""))
    location = Job_formatter._clean_text(", ".join(raw_job.get("jobLocation", [])))
    work_time = Job_formatter._clean_text(raw_job.get("workTime", ""))
    continuity = Job_formatter._clean_text(raw_job.get("continuityOfWork", ""))
    salary = Job_formatter._clean_text(raw_job.get("salary_range", ""))
    languages = Job_formatter._clean_text(", ".join(raw_job.get("language_requirements", [])))
    expectations = Job_formatter._clean_text(", ".join(raw_job.get("what_we_expect", [])))
    responsibilities = Job_formatter._clean_text(", ".join(raw_job.get("job_responsibilities", [])))
    offers = Job_formatter._clean_text(", ".join(raw_job.get("what_we_offer", [])))
    content = Job_formatter._clean_text(raw_job.get("translated_content") or raw_job.get("jobcontent", ""))

    return (
        "You are rewriting a job post into one clean, professional, natural English paragraph for a Finland jobs website.\n\n"
        "Your task:\n"
        "- Write ONLY one single paragraph.\n"
        "- Make it read smoothly and professionally, like a polished job summary.\n"
        "- Keep it concise but informative.\n"
        "- Maximum length: 800 characters.\n"
        "- End with a complete sentence.\n"
        "- Do not cut off the paragraph mid-sentence.\n"
        "- Do not use bullet points.\n"
        "- Do not use headings.\n"
        "- Do not use HTML.\n"
        "- Do not use markdown.\n"
        "- Do not wrap the result in quotes.\n"
        "- Do not start with punctuation, quotation marks, or a colon.\n"
        "- Do not copy broken links, raw URLs, mailto text, duplicate lines, or messy formatting.\n"
        "- Do not invent facts that are not present.\n"
        "- Preserve important details such as role, duties, requirements, benefits, salary if available, and start timing if available.\n"
        "- Use clear, human-sounding English.\n"
        '- Start naturally, for example with phrases like "We are looking for..." when appropriate.\n'
        "- Output ONLY the final paragraph and nothing else.\n\n"
        f"Job Title: {title}\n"
        f"Company: {company}\n"
        f"Location: {location}\n"
        f"Work Time: {work_time}\n"
        f"Continuity of Work: {continuity}\n"
        f"Salary: {salary}\n"
        f"Language Requirements: {languages}\n"
        f"What We Expect: {expectations}\n"
        f"Job Responsibilities: {responsibilities}\n"
        f"What We Offer: {offers}\n\n"
        f'Raw Job Content:\n"""\n{content}\n"""'
    )


def _call_ollama_plain_text(prompt: str, timeout_secs: int = TIMEOUT_SECS, num_predict: int = 220) -> tuple[str, bool, str]:
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_predict": num_predict,
            "num_ctx": 4096,
        },
    }

    for attempt in range(1, MAX_RETRIES + 2):
        try:
            resp = requests.post(OLLAMA_URL, json=payload, timeout=timeout_secs)

            if resp.status_code != 200:
                return "", False, f"HTTP {resp.status_code}"

            output = _sanitize_plain_output(resp.json().get("response", ""))
            return output, True, ""

        except (requests.Timeout, requests.ConnectionError) as exc:
            if attempt <= MAX_RETRIES:
                logger.warning(
                    "Plain Ollama timeout/connection error (attempt %d/%d): %s",
                    attempt,
                    MAX_RETRIES + 1,
                    exc,
                )
            else:
                return "", False, str(exc)

        except Exception as exc:
            return "", False, str(exc)

    return "", False, "unknown error"


def _generate_description_and_meta(raw_job: dict) -> tuple[str, str]:
    translated_text = raw_job.get("translated_content") or raw_job.get("jobcontent", "")
    fallback_description = _trim_description_safely(_normalize_whitespace(translated_text), 800)

    desc_prompt = _build_description_prompt(raw_job)
    formatted_description, desc_ok, desc_err = _call_ollama_plain_text(
        desc_prompt,
        timeout_secs=TIMEOUT_SECS,
        num_predict=320,
    )

    if not desc_ok or not formatted_description:
        logger.warning(
            "Description AI failed for '%s': %s",
            raw_job.get("title", raw_job.get("id")),
            desc_err,
        )
        formatted_description = fallback_description
    else:
        formatted_description = _trim_description_safely(formatted_description, 800)

    # Meta description: always use a template (no Ollama call)
    meta_description = Job_formatter.generate_meta_from_template(raw_job)

    return formatted_description, meta_description


def format_translated_jobs(
    raw_jobs: list[dict],
    batch_size: int = BATCH_SIZE,
    category_checker=None,
) -> tuple[list[dict], list[dict]]:
    """
    Phase 3: Format pre-translated jobs using AI for extraction,
    description generation, and meta description generation.

    Args:
        raw_jobs:         list of translated raw job dicts
        batch_size:       max jobs to process (0 = all)
        category_checker: optional BatchChecker instance from category_post_check.
                          If provided, checker.submit(job) is called immediately
                          after each job finishes AI processing so the background
                          worker can verify the category concurrently.

    Returns:
        (newly_formatted_jobs, updated_raw_jobs)
    """

    def _format_one(raw: dict) -> tuple[dict, bool, str, str]:
        title = raw.get("title", raw["id"])
        translated_text = raw.get("translated_content") or raw.get("jobcontent", "")
        occupations = raw.get("jobcategory_keywords") or raw.get("job_occupations_en", [])

        top_cat, top_score = Job_formatter.detect_category_by_keywords(
            title,
            translated_text,
            occupations=occupations,
        )

        found_category = top_cat if top_cat in config.VALID_CATEGORIES else "other"
        logger.info("  Category (scoring): %s → %s (score=%d)", title, found_category, top_score)

        # Persist the detected category immediately — non-blocking fire-and-forget.
        # This writes to scraper/data/category_check.json in a daemon thread so
        # the record is on disk before (and while) the Ollama AI call runs.
        category_post_check.save_to_category_check(raw, found_category)

        ai_data, success, status, err = _call_ollama_for_content(
            translated_text,
            raw_job=raw,
            ai_category=found_category,
        )

        if success:
            formatted_description, meta_description = _generate_description_and_meta(raw)
        else:
            fallback_description = _trim_description_safely(_normalize_whitespace(translated_text), 800)
            formatted_description = fallback_description
            meta_description = Job_formatter.generate_meta_from_template(raw)

        ai_data["formatted_description"] = formatted_description
        ai_data["meta_description"] = meta_description
        ai_data["job_category"] = found_category

        raw["ai_data"] = ai_data
        raw["ai_status"] = "success" if success else status

        logger.info("  Description (%d chars): %s", len(formatted_description), formatted_description[:220])
        logger.info("  Meta (%d chars): %s", len(meta_description), meta_description)

        return raw, success, status, err

    def _upsert(formatted_list: list[dict], new_job: dict) -> list[dict]:
        return [f for f in formatted_list if f["id"] != new_job["id"]] + [new_job]

    pending = rawjobs_store.get_unprocessed_jobs(raw_jobs)
    pending.sort(key=lambda j: j.get("retry_count", 0))
    batch = pending if batch_size == 0 else pending[:batch_size]

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
            # Submit to background category checker as soon as this job is ready
            if category_checker is not None:
                # Build a lightweight dict the checker can use without waiting
                # for Job_formatter.format_jobs() (which runs in Phase 4).
                # The checker only needs: title, company, job_category,
                # job_id, formatted_description.  job_id is set by Phase 4
                # so we pass whatever we have now; the checker skips if missing.
                submit_job = {
                    "title":               title,
                    "company":             raw_processed.get("company", ""),
                    "job_category":        raw_processed.get("ai_data", {}).get("job_category", "other"),
                    "job_id":              raw_processed.get("job_id", ""),
                    "formatted_description": raw_processed.get("ai_data", {}).get("formatted_description", ""),
                    "image_url":           raw_processed.get("image_url", ""),
                    # keep reference so checker can update job_category in-place
                    "_raw_ref":            raw_processed,
                }
                category_checker.submit(submit_job)
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