"""
job_translator.py — Phase 2: Offline GPU Translation (FI/SV→EN).

Translates raw Finnish or Swedish job content to English using local GPU models
(Meta NLLB-200-1.3B primary, Helsinki-NLP Opus-MT fallback).
Saves:
- rawjobs.json (raw jobs with translated_content cache)
- translated_jobs.json (Phase 2 output only — pure English)
"""


import logging
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

import config
import jobs_store
import rawjobs_store
import translator

logger = logging.getLogger("job_translator")

# Number of jobs to translate in parallel on GPU.
# Set to 1 to dedicate GPU VRAM and compute without thread contention.
def _get_workers() -> int:
    return 1



def _clean_multiline_text(text: str) -> str:
    text = (text or "").replace("\r", "")
    while "\n\n\n" in text:
        text = text.replace("\n\n\n", "\n\n")
    return text.strip()


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
    Phase 2: Translate all untranslated raw jobs from Finnish/Swedish to English.
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

    logger.info("Translating %d raw jobs (FI/SV->EN)...", len(untranslated))

    def _translate_one(args):
        idx, raw = args
        title = raw.get("title", raw.get("id", ""))
        jobcontent = _clean_multiline_text(raw.get("jobcontent") or "")

        # ── FIX: translate title and body SEPARATELY ────────────────────────────
        # Previously the title was concatenated with the body as one string:
        #   raw_text = f"{title}\n\n{jobcontent}"
        # The NLLB tokenizer truncates at 400 tokens, so a long job body would
        # push the title into a corrupted/truncated context, causing the model to
        # hallucinate mistranslations of compound Finnish words (e.g. "bittiviidakon"
        # → "the Bitch" instead of "digital jungle").
        # Translating them separately gives the model clean, unambiguous context
        # for each piece, and lets us sanitize the title independently.
        trans_title = translator.translate_fi_to_en(title) if title else ""
        trans_title = translator.post_process_translation(trans_title)  # sanitize immediately
        backend = translator.get_last_backend()

        trans_body = translator.translate_fi_to_en(jobcontent) if jobcontent else ""
        # Reassemble in the same format _split_translated_title_and_content expects
        translated = f"{trans_title}\n\n{trans_body}".strip() if trans_body else trans_title
        raw_text = f"{title}\n\n{jobcontent}".strip()  # keep for logging only
        return idx, raw, title, raw_text, translated, backend

    completed = 0
    workers = _get_workers()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_translate_one, (i, raw)): i for i, raw in enumerate(untranslated, 1)}
        for future in as_completed(futures):
            try:
                idx, raw, title, raw_text, translated, backend = future.result()
                raw["jobcontent"] = _clean_multiline_text(raw.get("jobcontent") or "")
                raw["translated_content"] = translated
                raw["translated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                rawjobs_store.mark_translation_status(
                    raw_jobs, raw.get("id", ""), translated=True,
                    processing_state=processing_state,
                )
                completed += 1
                clean_title = title.split(" - ")[0].strip()
                if len(clean_title) > 50:
                    clean_title = clean_title[:47] + "..."
                logger.info(
                    "[%d/%d] Translated: %s (%s chars) via [%s]",
                    completed, len(untranslated), clean_title, f"{len(raw_text):,}", backend,
                )
                sys.stdout.flush()
            except Exception as exc:
                logger.error("  Translation worker failed: %s", exc)

    logger.info("Translation complete. %d jobs translated.", len(untranslated))
    return raw_jobs


def _build_translated_raw_output(
    raw_jobs: list[dict],
    processing_state: dict[str, dict],
) -> list[dict]:
    """
    Build translated_jobs.json as a clean Phase 2 output with pure English.

    For every job:
    - title and jobcontent are replaced with the English translated_content version.
    - Supplementary fields (what_we_expect, job_responsibilities, what_we_offer,
      language_requirements, workTime, continuityOfWork) are bulk-translated via
      the Google Translate API ONLY when processing_state[job_id]["bulk_translated"]
      is False.  Once translated, the flag is flipped to True so future runs skip it.
    """
    total = len(raw_jobs)
    bulk_calls = 0
    skipped = sum(
        1 for raw in raw_jobs
        if processing_state.get(raw.get("id", ""), {}).get("bulk_translated", False)
    )

    logger.info(
        "Building translated output for %d jobs (%d already bulk-translated, %d need API call)...",
        total, skipped, total - skipped,
    )

    # _build_one runs in a thread — returns (index, out_job, n_api_calls, job_id_to_mark)
    def _build_one(args):
        i, raw = args
        jid = raw.get("id", "")
        ps  = processing_state.get(jid, {})
        out_job = dict(raw)

        # ── Fast path: supplementary fields already translated in a prior run ──
        if ps.get("bulk_translated", False):
            # Still apply title/content split from translated_content
            translated_text = raw.get("translated_content", "")
            if translated_text:
                fallback_title = out_job.get("title", "")
                trans_title, trans_content = _split_translated_title_and_content(translated_text, fallback_title)
                out_job["title"] = trans_title
                out_job["jobcontent"] = trans_content
            for key in list(out_job.keys()):
                if key.startswith("translated_") and key != "translated_content":
                    del out_job[key]
            return i, out_job, 0, None  # 0 API calls, nothing to mark

        # ── Slow path: bulk-translate supplementary fields ─────────────────────
        texts_to_translate = []
        map_back = []  # (field, is_list)

        for field in ["what_we_expect", "job_responsibilities", "what_we_offer", "language_requirements"]:
            val = raw.get(field)
            if val and isinstance(val, list):
                for v in val:
                    s_val = str(v).strip()
                    if s_val:
                        texts_to_translate.append(s_val)
                        map_back.append((field, True))

        for field in ["workTime", "continuityOfWork"]:
            val = raw.get(field)
            if val and isinstance(val, str) and val.strip():
                texts_to_translate.append(val.strip())
                map_back.append((field, False))

        n_calls = 0
        if texts_to_translate:
            # Use translate_batch: all texts in ONE batch call
            translated_parts = translator.translate_batch(texts_to_translate)
            n_calls = 1
            parsed = {}
            for txt_translated, (field, is_list) in zip(translated_parts, map_back):
                if field not in parsed:
                    parsed[field] = [] if is_list else ""
                if is_list:
                    parsed[field].append(txt_translated)
                else:
                    parsed[field] = txt_translated
            for field, val in parsed.items():
                out_job[field] = val

        translated_text = raw.get("translated_content", "")
        if translated_text:
            fallback_title = raw.get("english_title_hint") or out_job.get("title", "")
            trans_title, trans_content = _split_translated_title_and_content(translated_text, fallback_title)
            # Fall back to english_title_hint for known hallucination patterns
            # "linear car" is a known NLLB hallucination for bus/tram driver titles.
            # "[removed]" indicates post_process_translation flagged a profanity artefact.
            if raw.get("english_title_hint"):
                if "linear car" in trans_title.lower() or "[removed]" in trans_title:
                    trans_title = raw["english_title_hint"]
            trans_title = translator.post_process_translation(trans_title)
            trans_content = translator.post_process_translation(trans_content)
            out_job["title"] = trans_title
            out_job["jobcontent"] = trans_content


        for key in list(out_job.keys()):
            if key.startswith("translated_") and key != "translated_content":
                del out_job[key]

        # Signal to the main thread that this job_id should now be marked bulk_translated
        return i, out_job, n_calls, jid

    results = [None] * total
    workers = _get_workers()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_build_one, (i, raw)): i for i, raw in enumerate(raw_jobs)}
        for future in as_completed(futures):
            try:
                i, out_job, n_calls, mark_jid = future.result()
                results[i] = out_job
                bulk_calls += n_calls
                # Mark in processing_state (main thread only — no race conditions)
                if mark_jid:
                    rawjobs_store.mark_bulk_translated(mark_jid, processing_state)
                if (i + 1) % 50 == 0 or (i + 1) == total:
                    logger.info("  [%d/%d] fields processed (%d bulk API calls so far)", i + 1, total, bulk_calls)
            except Exception as exc:
                logger.error("  Field-build worker failed for job %d: %s", futures[future], exc)

    translated_output = [r for r in results if r is not None]

    logger.info("Translated output built. %d jobs, %d bulk translation calls.", total, bulk_calls)
    return translated_output


def run_phase2(raw_jobs: list[dict]) -> list[dict]:
    """
    Full Phase 2 execution:
    - translate raw jobs (title + jobcontent) for those not yet translated
    - build supplementary-field translations, skipping jobs where
      processing_state[id]["bulk_translated"] is already True
    - save rawjobs.json, translated_jobs.json, processing_state.json
    """
    processing_state = rawjobs_store.ensure_processing_state(
        raw_jobs,
        rawjobs_store.load_processing_state(),
    )

    raw_jobs = translate_raw_jobs(raw_jobs, processing_state=processing_state)

    # Compile the output; processing_state is updated in-place with bulk_translated flags.
    translated_output = _build_translated_raw_output(raw_jobs, processing_state=processing_state)

    # Save AFTER building output so processing_state carries fresh bulk_translated flags.
    rawjobs_store.save_raw_jobs(raw_jobs)
    rawjobs_store.save_processing_state(processing_state)
    jobs_store.save_translated_jobs(translated_output)

    logger.info("Phase 2 saved to rawjobs.json + translated_jobs.json.")
    translator.unload_models()
    return raw_jobs


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

    raw_list = rawjobs_store.load_raw_jobs()
    raw_list = run_phase2(raw_list)
    logger.info("Phase 2 standalone run complete. %d jobs in store.", len(raw_list))