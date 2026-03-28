"""
ai_processor.py — Phase 2: AI Formatting Queue Processor.

to format all fields into clean HTML and assign the correct job category.
Writes formatted results to jobs.json and marks rawjobs as processed.

Processes jobs in configurable batch sizes to avoid CPU/RAM overload.
"""

import json
import logging
import re
import requests
import random
from datetime import datetime

import config
import jobs_store
import rawjobs_store
import scraper as _scraper

logger = logging.getLogger("ai_processor")

OLLAMA_URL   = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "mistral"
BATCH_SIZE   = 10   # jobs processed per run
TIMEOUT_SECS = 300  # per-job Ollama timeout (needs 300s+ for full translation on some hardware)


# ── Ollama call ───────────────────────────────────────────────────────────────

def _call_ollama(text: str, raw_job: dict = None, fallback_category: str = "Other") -> dict:
    """
    Ask Ollama to analyse a job description and return structured JSON.
    Returns a dict with all formatted fields, falling back gracefully on failure.
    """
    valid_categories = config.VALID_CATEGORIES + ["Other"]
    cats_str = ", ".join(valid_categories)

    # Prepare context from raw fields if available
    raw_context = ""
    if raw_job:
        raw_context = "\n--- RAW DATA CONTEXT ---\n"
        if raw_job.get("what_we_expect"):
            raw_context += f"RAW EXPECTATIONS: {raw_job['what_we_expect']}\n"
        if raw_job.get("job_responsibilities"):
            raw_context += f"RAW RESPONSIBILITIES: {raw_job['job_responsibilities']}\n"
        if raw_job.get("experience"):
            raw_context += f"RAW EXPERIENCE: {raw_job['experience']}\n"
        if raw_job.get("what_we_offer"):
            raw_context += f"RAW OFFERS: {raw_job['what_we_offer']}\n"

    prompt = (
        "You are a professional Finnish-to-English translator and HR assistant. "
        "Your task is to TRANSLATE and FORMAT the following Finnish job description into ENGLISH. "
        "Extract the information into ONLY a valid JSON object. "
        "DO NOT use markdown code blocks.\n\n"
        "Required JSON format:\n"
        "{\n"
        '  "title": "Exact job title TRANSLATED TO ENGLISH (e.g. Sales Representative, Cleaner, DO NOT leave in Finnish)",\n'
        '  "company": "Company name",\n'
        f'  "job_category": "Choose exactly one from the following list: {cats_str} (Use hyphens - instead of underscores _ if needed)",\n'
        '  "meta_description": "A concise 1-2 sentence SEO summary of the job, max 155 characters, suitable for a meta description tag",\n'
        '  "description": "A detailed 2-3 paragraph description of the job in English. Each paragraph should be 3-5 sentences. Cover what the role involves, what kind of person fits it, and what the company offers. Make it engaging, thorough and informative.",\n'
        '  "experience": ["List 3-4 key experience requirements or qualifications in English"],\n'
        '  "salary_range": "Salary information in English if found",\n'
        '  "employment_type": ["List of types: e.g. Full-time, Part-time, Contract"],\n'
        '  "language_requirements": ["List of languages required"],\n'
        '  "what_we_expect": ["List of requirements/expectations in English"],\n'
        '  "job_responsibilities": ["List of main tasks in English"],\n'
        '  "what_we_offer": ["List of benefits/offers in English"],\n'
        '  "who_is_this_for": ["List of ideal candidate qualities in English"],\n'
        '  "job_location": "Exact city or municipality in Finland if found in the text (e.g. Helsinki, Tampere, Rovaniemi). Use \'Finland\' only if no specific city is mentioned.",\n'
        '  "search_keywords": "A space-separated string of 8-12 search keywords in English for this job. Include the job title, role synonyms, industry, location (Finland), and common search phrases someone would use to find this role. Example: sales representative customer service jobs Finland sales jobs in Finland outbound sales commission based"\n'
        "}\n\n"
        "CRITICAL: The output MUST be 100% in English. "
        "Translate everything accurately from the Finnish input.\n"
        "CATEGORIZATION GUIDANCE: "
        "Analyze the job role deeply. Do NOT use 'caregiver' for business or sales roles even if they are in the healthcare sector. "
        "Prioritize 'sales-and-marketing' or 'customer-service-support' for interaction-based roles.\n"
        "RECOVERY RULE: If any of the array fields (experience, what_we_expect, job_responsibilities, what_we_offer) are NOT provided in the RAW DATA CONTEXT, "
        "you MUST infer and generate 3-5 high-quality, relevant items for those fields based on the description text. Do not leave them empty if the information is implied in the description.\n"
        "EXTRACTION RULES: "
        "- For arrays like 'experience', 'what_we_expect', 'job_responsibilities', and 'what_we_offer', do NOT include application deadlines, "
        "dates (e.g., 'Apply by 30.04'), email addresses, phone numbers, or external URLs. "
        "- These fields must ONLY contain actual qualifications, tasks, or benefits.\n"
        "LOCATION EXTRACTION: "
        "- Carefully extract the exact work location (city/municipality) from the Finnish description. "
        "- Common cities: Helsinki, Espoo, Vantaa, Tampere, Turku, Oulu, Jyväskylä, Lahti, Kuopio, Pori, etc. "
        "- Translate the city name to English if applicable (e.g., 'Helsingfors' -> 'Helsinki', 'Tammerfors' -> 'Tampere').\n"
        f"{raw_context}\n"
        f"Input Finnish Job Description:\n{text[:6000]}"
    )

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
    }

    default = {
        "title": "",
        "company": "",
        "job_category": fallback_category,
        "meta_description": "",
        "description": "",
        "experience": [],
        "salary_range": "",
        "employment_type": [],
        "language_requirements": [],
        "what_we_expect": [],
        "job_responsibilities": [],
        "what_we_offer":    [],
        "who_is_this_for":  [],
        "search_keywords":  "",
    }

    try:
        resp = requests.post(OLLAMA_URL, json=payload, timeout=TIMEOUT_SECS)
        if resp.status_code != 200:
            logger.warning("Ollama returned %d", resp.status_code)
            return default, False, "error", f"HTTP {resp.status_code}"

        content = resp.json().get("response", "").strip()
        # Strip potential markdown code blocks
        content = re.sub(r"^```(?:json)?", "", content).strip()
        content = re.sub(r"```$", "", content).strip()

        parsed = json.loads(content)
        cat = parsed.get("job_category", fallback_category)
        if cat not in valid_categories:
            cat = fallback_category

        ai_results = {
            "title":                 parsed.get("title") or "",
            "company":               parsed.get("company") or "",
            "job_category":          cat,
            "meta_description":      parsed.get("meta_description") or "",
            "description":           parsed.get("description") or "",
            "experience":            parsed.get("experience") or [],
            "salary_range":          parsed.get("salary_range") or "",
            "employment_type":       parsed.get("employment_type") or [],
            "language_requirements": parsed.get("language_requirements") or [],
            "what_we_expect":        parsed.get("what_we_expect") or [],
            "job_responsibilities":  parsed.get("job_responsibilities") or [],
            "what_we_offer":         parsed.get("what_we_offer") or [],
            "who_is_this_for":       parsed.get("who_is_this_for") or [],
            "search_keywords":       parsed.get("search_keywords") or "",
        }
        return ai_results, True, "success", ""

    except json.JSONDecodeError as exc:
        logger.warning("JSON decode error from Ollama: %s", exc)
        return default, False, "error", "JSON decode error"
    except Exception as exc:
        status = "error"
        error_msg = str(exc)
        if "timeout" in error_msg.lower():
            status = "timeout"
        logger.warning("Ollama call failed (%s): %s", status, error_msg)
        return default, False, status, error_msg


def _simple_html(text: str) -> str:
    """Simple fallback: convert double-newline paragraphs to <p> tags."""
    paras = [f"<p>{p.strip()}</p>" for p in text.split("\n\n") if p.strip()]
    return "".join(paras) or f"<p>{text.strip()}</p>"


# ── Build final job from raw + AI output ─────────────────────────────────────

def _build_formatted_job(raw_job: dict, ai_data: dict) -> dict:
    """
    Merge a raw job from rawjobs.json with AI-formatted fields to produce
    a final job entry for jobs.json.
    """
    category  = ai_data.get("job_category") or "Other"
    cat_slug  = config.slugify_category(category)
    hash_id   = raw_job["id"]
    
    # Generate an English slug from the translated title and original location
    eng_title = ai_data.get("title") or raw_job.get("title", "")
    title_slug = _scraper.slugify(eng_title)[:100]
    loc_slug   = _scraper.slugify(raw_job.get("jobLocation", ["Finland"])[0])[:50]
    english_job_id = f"{title_slug}-{loc_slug}-{hash_id}"
    
    job_path  = f"/jobs/{cat_slug}/{english_job_id}"

    # 3. Final mapping
    # Description comes back as a multi-paragraph string; handle list fallback.
    desc = ai_data.get("description", "")
    if isinstance(desc, list):
        desc = "\n\n".join(desc)

    # meta_description: short SEO summary (~155 chars)
    meta_desc = ai_data.get("meta_description", "")
    if isinstance(meta_desc, list):
        meta_desc = " ".join(meta_desc)
    # Fallback: truncate description if meta_description is missing
    if not meta_desc and desc:
        meta_desc = desc[:152].rsplit(" ", 1)[0] + "…"

    # Experience is now a list
    exp = ai_data.get("experience", [])
    if isinstance(exp, str):
        exp = [exp]

    # STICKY COMPANY: Prefer raw company if it exists and isn't generic
    final_company = raw_job.get("company", "").strip()
    ai_company = ai_data.get("company", "").strip()
    
    # If raw is empty or just "Unspecified", use AI suggestion
    if not final_company or final_company.lower() in ["unspecified", "not specified"]:
        final_company = ai_company
    
    # 4. Smart Location Handling
    raw_location = raw_job.get("jobLocation", [])
    if isinstance(raw_location, str):
        raw_location = [raw_location]
    
    # Use AI-extracted location if the raw one is generic ("Finland", empty, or missing)
    is_generic = (
        not raw_location 
        or all(loc.strip().lower() in ["finland", "suomi", "none", "unspecified"] for loc in raw_location)
    )
    
    final_location = raw_location
    if is_generic:
        ai_loc = ai_data.get("job_location", "").strip()
        if ai_loc and ai_loc.lower() not in ["none", "unspecified"]:
            final_location = [ai_loc]
        else:
            final_location = ["Finland"] # final fallback
    
    img_folder = config.slugify_category(category)
    random_num = random.randint(1, 30)
    image_url = f"{config.GITHUB_PAGES_BASE_URL}/images/jobs/{img_folder}/{random_num}.png"
    
    job = {
        "id":                   raw_job["id"],
        "job_id":               english_job_id,
        "processed":            True,
        "title":                ai_data.get("title") or raw_job.get("title", ""),
        "company":              final_company,
        "job_category":         category,
        "jobLocation":          final_location,
        "jobapply_link":        raw_job.get("jobapply_link", raw_job.get("jobLink", "")),
        "jobLink":              raw_job.get("jobLink", ""),
        "job_employer_email":   raw_job.get("job_employer_email", ""),
        "jobUrl":               f"{config.GITHUB_PAGES_BASE_URL}{job_path}",
        "date_posted":          raw_job.get("date_posted", ""),
        "date_expires":         raw_job.get("date_expires", ""),
        "scraped_at":           raw_job.get("scraped_at", ""),
        
        "salary_range":         ai_data.get("salary_range") or raw_job.get("salary_range") or "",
        "employment_type":      ai_data.get("employment_type") or raw_job.get("employment_type") or [],
        "language_requirements": ai_data.get("language_requirements") or raw_job.get("language_requirements") or [],
        
        "meta_description":     meta_desc,
        "description":          desc,
        "experience":           exp or raw_job.get("experience") or [],
        "what_we_expect":       ai_data.get("what_we_expect") or raw_job.get("what_we_expect") or [],
        "job_responsibilities": ai_data.get("job_responsibilities") or raw_job.get("job_responsibilities") or [],
        "what_we_offer":        ai_data.get("what_we_offer") or raw_job.get("what_we_offer") or [],
        "who_is_this_for":      ai_data.get("who_is_this_for") or raw_job.get("who_is_this_for") or [],
        "search_keywords":      ai_data.get("search_keywords", ""),
        "display_mode":         raw_job.get("display_mode", "fallback"),
        "image_url":            "", # Will be set by apply_manual_fixes
    }

    return apply_manual_fixes(job)


def apply_manual_fixes(job: dict) -> dict:
    """
    Apply hardcoded fixes for titles and categories,
    rebuild the job_id slug using full-length limits (self-heals truncated slugs),
    and ensure URLs/images are synced accordingly.
    Runs on every scrape for all jobs.
    """
    title = job.get("title", "")
    category = job.get("job_category", "Other")

    # 1. Title Patches (Finnish to English overrides)
    title_patches = {
        "Kattomyyjä & Asiakashankkija": "Roofing Sales Representative & Customer Acquisition Specialist",
        "Haussa myyjiä Helsinkiin, Tampereelle ja Turkuun": "Sales Representatives for Helsinki, Tampere and Turku",
        "Myyjä / Myyntiedustaja": "Sales Representative / Sales Advisor",
    }
    for fin, eng in title_patches.items():
        if fin in title:
            job["title"] = eng
            break

    # 2. Category Overrides
    title_low = job["title"].lower()
    if any(kw in title_low for kw in ["physician", "doctor", "dentist", "surgeon", "lääkäri"]):
        job["job_category"] = "healthcare"
    elif any(kw in title_low for kw in ["cleaner", "housekeep", "siivooja"]):
        job["job_category"] = "cleaning"
    elif any(kw in title_low for kw in ["sales", "myynti"]):
        if job["job_category"] == "Other":
            job["job_category"] = "sales_&_marketing"

    # 3. Rebuild job_id slug from full title (100/50 char limits, self-heals old truncated slugs)
    hash_id   = job["id"]
    location  = job.get("jobLocation", ["Finland"])[0]
    title_slug = _scraper.slugify(job["title"])[:100]
    loc_slug   = _scraper.slugify(location)[:50]
    job["job_id"] = f"{title_slug}-{loc_slug}-{hash_id}"

    # 4. Final URL & Image Sync
    new_cat  = job["job_category"]
    cat_slug = config.slugify_category(new_cat)
    job["jobUrl"] = f"{config.GITHUB_PAGES_BASE_URL}/jobs/{cat_slug}/{job['job_id']}"

    # Sync image_url — keep existing if it already references the correct category folder
    safe_slug = config.get_safe_category_slug(new_cat)
    if "images/jobs/" not in job.get("image_url", "") or safe_slug not in job.get("image_url", ""):
        num = random.randint(1, 30)
        job["image_url"] = f"{config.GITHUB_PAGES_BASE_URL}/images/jobs/{safe_slug}/{num}.png"
    
    return job


# ── Main processor ────────────────────────────────────────────────────────────

def process_raw_jobs(
    raw_jobs: list[dict],
    batch_size: int = BATCH_SIZE,
) -> tuple[list[dict], list[dict]]:
    """
    Process unprocessed raw jobs through Ollama in batches.
    Automatically retries failed jobs within the same run until they succeed
    or exhaust max_retries. Saves rawjobs.json between retry rounds.

    Returns:
        (newly_formatted_jobs, updated_raw_jobs)
    """
    def _process_one(raw: dict) -> tuple[dict, bool, str, str]:
        """Helper: build text, call Ollama, return (formatted, success, status, err)."""
        title = raw.get("title", raw["id"])
        metadata = ""
        if raw.get("company"):
            metadata += f"COMPANY: {raw['company']}\n"
        if raw.get("salary_range"):
            metadata += f"SALARY: {raw['salary_range']}\n"
        if raw.get("language_requirements"):
            langs = raw["language_requirements"]
            metadata += f"LANGUAGES: {', '.join(langs) if isinstance(langs, list) else langs}\n"
        text     = f"TITLE: {title}\n{metadata}BODY:\n" + (raw.get("raw_text") or "")
        fallback = _scraper.detect_categories(title, text)[0]
        ai_data, success, status, err = _call_ollama(text, raw_job=raw, fallback_category=fallback)
        formatted = _build_formatted_job(raw, ai_data)
        return formatted, success, status, err

    def _upsert(formatted_list: list[dict], new_job: dict) -> list[dict]:
        """Replace existing entry with same id, or append."""
        return [f for f in formatted_list if f["id"] != new_job["id"]] + [new_job]

    # ── Initial batch ─────────────────────────────────────────────────────────
    pending = rawjobs_store.get_unprocessed_jobs(raw_jobs)
    pending.sort(key=lambda j: j.get("retry_count", 0))  # new jobs first
    batch   = pending[:batch_size]

    if not batch:
        logger.info("No unprocessed jobs in queue (including retries).")
        return [], raw_jobs

    logger.info("AI processing %d/%d unprocessed jobs (batch size=%d)",
                len(batch), len(pending), batch_size)

    newly_formatted: list[dict] = []

    for i, raw in enumerate(batch, 1):
        title = raw.get("title", raw["id"])
        logger.info("[%d/%d] AI formatting: %s", i, len(batch), title)

        formatted, success, status, err = _process_one(raw)
        newly_formatted = _upsert(newly_formatted, formatted)
        rawjobs_store.update_ai_status(raw_jobs, raw["id"], success=success, status=status, error=err)

        if success:
            logger.info("  ✓ %s → category=%s", title, formatted.get("job_category"))
        else:
            logger.warning("  ✗ %s → %s (retry_count=%d)", title, status, raw.get("retry_count", 1))

    # ── AUTO-RETRY LOOP ───────────────────────────────────────────────────────
    # After the initial batch, keep retrying any jobs that failed until they
    # succeed or exhaust max_retries. Saves rawjobs.json between rounds.
    retry_round = 0
    while True:
        # Only retry jobs that have been attempted before (retry_count > 0)
        still_failing = [
            j for j in rawjobs_store.get_unprocessed_jobs(raw_jobs)
            if j.get("retry_count", 0) > 0
        ]

        if not still_failing:
            logger.info("All jobs processed successfully. No retries needed.")
            break

        retry_round += 1
        logger.info("── Auto-retry round %d: %d job(s) still failing ──",
                    retry_round, len(still_failing))

        # Save progress before each retry round so nothing is lost
        rawjobs_store.save_raw_jobs(raw_jobs)

        for raw in still_failing:
            title   = raw.get("title", raw["id"])
            retry_n = raw.get("retry_count", 1)
            max_r   = raw.get("max_retries", 3)
            logger.info("  [retry %d/%d] %s", retry_n, max_r, title)

            formatted, success, status, err = _process_one(raw)
            newly_formatted = _upsert(newly_formatted, formatted)
            rawjobs_store.update_ai_status(raw_jobs, raw["id"], success=success, status=status, error=err)

            if success:
                logger.info("    ✓ %s → SUCCESS on retry %d", title, retry_n)
            else:
                logger.warning("    ✗ %s → still failing (%s), retry_count now %d",
                               title, status, raw.get("retry_count", 0))

    logger.info("AI processing complete. %d jobs formatted.", len(newly_formatted))
    return newly_formatted, raw_jobs


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")
    
    # 1. Load raw jobs
    raw_list = rawjobs_store.load_raw_jobs()
    
    # 2. Process unprocessed ones
    new_jobs, updated_raw = process_raw_jobs(raw_list, batch_size=5)
    
    if new_jobs:
        # 3. Load existing formatted jobs
        existing_formatted = jobs_store.load_jobs()
        # 4. Merge and save
        merged, actually_new = jobs_store.merge_new_jobs(existing_formatted, new_jobs)
        jobs_store.save_jobs(merged)
        # 5. Save updated raw list (with processed flags)
        rawjobs_store.save_raw_jobs(updated_raw)
        logger.info("Saved %d new jobs to jobs.json", len(new_jobs))
    else:
        logger.info("No new jobs to save.")
