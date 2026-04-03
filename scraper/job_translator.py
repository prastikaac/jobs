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

    for raw in raw_jobs:
        out_job = dict(raw)

        # Ensure translated helper fields exist if source fields exist
        for field in [
            "what_we_expect",
            "job_responsibilities",
            "what_we_offer",
            "who_is_this_for",
            "language_requirements",
        ]:
            val = raw.get(field)
            t_key = f"translated_{field}"
            if val and isinstance(val, list) and t_key not in raw:
                raw[t_key] = [translator.translate_fi_to_en(str(v)) for v in val if v]

        for field in ["workTime", "continuityOfWork"]:
            val = raw.get(field)
            t_key = f"translated_{field}"
            if val and isinstance(val, str) and t_key not in raw:
                raw[t_key] = translator.translate_fi_to_en(val)

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
                "who_is_this_for",
                "language_requirements",
                "workTime",
                "continuityOfWork",
            ]:
                t_key = f"translated_{field}"
                if t_key in raw:
                    out_job[field] = raw[t_key]

        # Keep translated_content because Phase 3 reads it
        # Remove transient translated_* helper keys from the phase2 output
        for key in list(out_job.keys()):
            if key.startswith("translated_") and key != "translated_content":
                del out_job[key]

        translated_output.append(out_job)

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

    rawjobs_store.save_raw_jobs(raw_jobs)
    rawjobs_store.save_processing_state(processing_state)

    translated_output = _build_translated_raw_output(raw_jobs)
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