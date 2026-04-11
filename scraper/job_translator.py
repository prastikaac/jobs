"""
job_translator.py — Phase 2: Offline Translation (Argos FI→EN).

Translates raw Finnish job content to English using ArgosTranslate.
Saves:
- rawjobs.json (raw jobs with translated_content cache)
- translated_raw_jobs.json (Phase 2 output only)

This module runs entirely offline — no network calls, no AI models.
"""

import logging
import re
from datetime import datetime

import config
import jobs_store
import rawjobs_store
import translator

logger = logging.getLogger("job_translator")


def _clean_multiline_text(text: str) -> str:
    text = (text or "").replace("\r", "")
    text = re.sub(r"\n{2,}", "\n\n", text).strip()
    return text


def _split_translated_title_and_content(translated_text: str, fallback_title: str) -> tuple[str, str]:
    translated_text = (translated_text or "").strip()
    if not translated_text:
        return fallback_title, ""

    parts = translated_text.split("\n\n", 1)
    if parts:
        trans_title = parts[0].strip() or fallback_title
        trans_content = parts[1].strip() if len(parts) > 1 else ""
        if trans_content:
            return trans_title, trans_content

    if "\n" in translated_text:
        lines = translated_text.split("\n", 1)
        trans_title = lines[0].strip() or fallback_title
        trans_content = lines[1].strip()
        return trans_title, trans_content

    return fallback_title, translated_text


def translate_raw_jobs(raw_jobs: list[dict], processing_state: dict[str, dict] | None = None) -> list[dict]:
    """
    Phase 2: Translate all untranslated raw jobs from Finnish to English using Argos.
    Stores the translated text in `translated_content` on raw jobs and marks
    translation status in processing_state.

    Returns:
        updated raw_jobs list
    """
    processing_state = processing_state or {}

    untranslated = []
    for raw in raw_jobs:
        jid = raw.get("id")
        ps = processing_state.get(jid, {})
        already_translated = bool(raw.get("translated_content")) or bool(ps.get("translated"))
        if not already_translated:
            untranslated.append(raw)

    if not untranslated:
        logger.info("All raw jobs already translated.")
        return raw_jobs

    logger.info("Translating %d raw jobs (Argos FI→EN)…", len(untranslated))

    for i, raw in enumerate(untranslated, 1):
        title = raw.get("title", raw.get("id", ""))
        jobcontent = _clean_multiline_text(raw.get("jobcontent") or "")
        raw["jobcontent"] = jobcontent

        raw_text = f"{title}\n\n{jobcontent}".strip()
        translated = translator.translate_fi_to_en(raw_text)

        raw["translated_content"] = translated
        raw["translated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        rawjobs_store.mark_translation_status(
            raw_jobs,
            raw.get("id", ""),
            translated=True,
            processing_state=processing_state,
        )

        logger.info(
            "  [%d/%d] Translated: %s (%d→%d chars)",
            i,
            len(untranslated),
            title[:50],
            len(raw_text),
            len(translated),
        )

    logger.info("Translation complete. %d jobs translated.", len(untranslated))
    return raw_jobs


def _build_translated_raw_output(raw_jobs: list[dict]) -> list[dict]:
    """
    Build translated_raw_jobs.json as a clean Phase 2 output.
    It keeps raw structure but replaces title/jobcontent with English versions
    when translated_content is available.
    """
    translated_output = []
    total = len(raw_jobs)
    bulk_calls = 0

    logger.info("Building translated output for %d jobs…", total)

    for i, raw in enumerate(raw_jobs):
        out_job = dict(raw)
        
        # Gather small fields that need translation to do them in a single bulk request
        texts_to_translate = []
        map_back = [] # (field, is_list)

        for field in [
            "what_we_expect",
            "job_responsibilities",
            "what_we_offer",
            "language_requirements",
        ]:
            val = raw.get(field)
            t_key = f"translated_{field}"
            if val and isinstance(val, list) and t_key not in raw:
                for v in val:
                    s_val = str(v).strip()
                    if s_val:
                        texts_to_translate.append(s_val)
                        map_back.append((field, True))

        for field in ["workTime", "continuityOfWork"]:
            val = raw.get(field)
            t_key = f"translated_{field}"
            if val and isinstance(val, str) and t_key not in raw:
                if val.strip():
                    texts_to_translate.append(val.strip())
                    map_back.append((field, False))

        # Bulk translate fields to save API requests and prevent rate limits
        if texts_to_translate:
            bulk_text = "\n\n---\n\n".join(texts_to_translate)
            translated_bulk = translator.translate_fi_to_en(bulk_text)
            bulk_calls += 1
            
            # Use regex to safely split around the --- delimiter, even if spaces were added
            import re
            parts = [p.strip() for p in re.split(r'\n*-{2,}\n*', translated_bulk)]
            
            if len(parts) == len(texts_to_translate):
                parsed = {}
                for idx, (field, is_list) in enumerate(map_back):
                    t_key = f"translated_{field}"
                    if t_key not in parsed:
                        parsed[t_key] = [] if is_list else ""
                        
                    if is_list:
                        parsed[t_key].append(parts[idx])
                    else:
                        parsed[t_key] = parts[idx]
                
                raw.update(parsed)

        translated_text = raw.get("translated_content", "")
        if translated_text:
            fallback_title = out_job.get("title", "")
            trans_title, trans_content = _split_translated_title_and_content(translated_text, fallback_title)
            out_job["title"] = trans_title
            out_job["jobcontent"] = trans_content

            for field in [
                "what_we_expect",
                "job_responsibilities",
                "what_we_offer",
                "language_requirements",
                "workTime",
                "continuityOfWork",
            ]:
                t_key = f"translated_{field}"
                if t_key in raw:
                    out_job[field] = raw[t_key]

        # Remove transient translated_* helper keys from the phase2 output
        for key in list(out_job.keys()):
            if key.startswith("translated_") and key != "translated_content":
                del out_job[key]

        translated_output.append(out_job)

        if (i + 1) % 50 == 0 or (i + 1) == total:
            logger.info("  [%d/%d] Supplementary fields processed (%d bulk API calls so far)", i + 1, total, bulk_calls)

    logger.info("Translated output built. %d jobs, %d bulk translation calls.", total, bulk_calls)
    return translated_output


def run_phase2(raw_jobs: list[dict]) -> list[dict]:
    """
    Full Phase 2 execution:
    - translate raw jobs
    - save rawjobs.json
    - save translated_raw_jobs.json
    - save processing_state.json
    """
    processing_state = rawjobs_store.ensure_processing_state(
        raw_jobs,
        rawjobs_store.load_processing_state(),
    )

    raw_jobs = translate_raw_jobs(raw_jobs, processing_state=processing_state)

    # Compile the output FIRST so any dynamic translation appended to `raw_jobs` gets captured.
    translated_output = _build_translated_raw_output(raw_jobs)
    
    # Save AFTER building output, so that translated_* extra fields are saved to cache forever!
    rawjobs_store.save_raw_jobs(raw_jobs)
    rawjobs_store.save_processing_state(processing_state)

    jobs_store.save_translated_raw_jobs(translated_output)

    logger.info("Phase 2 saved to rawjobs.json + translated_raw_jobs.json.")
    return raw_jobs


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    )

    raw_list = rawjobs_store.load_raw_jobs()
    raw_list = run_phase2(raw_list)
    logger.info("Phase 2 standalone run complete. %d jobs in store.", len(raw_list))