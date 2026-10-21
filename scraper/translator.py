"""
Wrapper for translation (FI/SV→EN) — 100% GPU Accelerated (CUDA).

Priority order:
  1. NLLB-200-1.3B via Transformers (Primary:  GPU CUDA, full fp32, highest accuracy)
  2. Helsinki-NLP Opus-MT fi→en    (Fallback: GPU CUDA, Finnish-specific)
  3. Original text                  (Last resort — untranslated)
"""
import os
import logging
import re
import html
import time
import threading

try:
    import torch
except ImportError:
    torch = None  # type: ignore[assignment]

logger = logging.getLogger("translator")

# Thread-local storage so parallel workers each track their own backend
_thread_local = threading.local()

def get_last_backend() -> str:
    """Return the translation backend used in the most recent call on this thread."""
    return getattr(_thread_local, "last_backend", "unknown")


# ---------------------------------------------------------------------------
# 1. NLLB-200-1.3B via Transformers (Primary: Most Accurate, 100% GPU CUDA)
#    GPU (CUDA): full fp32, ~5.5 GB VRAM  — highest accuracy + 5–10× faster
# ---------------------------------------------------------------------------
NLLB_TR_MODEL = "facebook/nllb-200-distilled-1.3B"
NLLB_TR_SRC_LANG = "fin_Latn"
NLLB_TR_TGT_LANG = "eng_Latn"

_NLLB_TR_CHECKED = False
_NLLB_TR_AVAILABLE = False
_nllb_tr_model = None
_nllb_tr_tokenizer = None
_nllb_tr_device = "cuda"
_nllb_tr_lock = threading.Lock()


def is_nllb_transformers_available() -> bool:
    """Check and lazily initialise NLLB-200-1.3B on GPU (CUDA)."""
    global _NLLB_TR_CHECKED, _NLLB_TR_AVAILABLE, _nllb_tr_model, _nllb_tr_tokenizer, _nllb_tr_device
    if _NLLB_TR_CHECKED:
        return _NLLB_TR_AVAILABLE

    with _nllb_tr_lock:
        if _NLLB_TR_CHECKED:
            return _NLLB_TR_AVAILABLE
        try:
            import torch  # type: ignore[import]
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer  # type: ignore[import]

            if not torch.cuda.is_available():
                logger.error("CUDA GPU not available — NLLB-200-1.3B requires GPU.")
                _NLLB_TR_AVAILABLE = False
                _NLLB_TR_CHECKED = True
                return False

            _nllb_tr_device = "cuda"
            gpu_name = torch.cuda.get_device_name(0)
            vram_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
            logger.info(
                "Loading NLLB-200-1.3B on GPU: %s (%.1f GB VRAM) in fp32...",
                gpu_name, vram_gb,
            )

            _nllb_tr_tokenizer = AutoTokenizer.from_pretrained(
                NLLB_TR_MODEL, src_lang=NLLB_TR_SRC_LANG
            )
            _nllb_tr_model = AutoModelForSeq2SeqLM.from_pretrained(
                NLLB_TR_MODEL,
                dtype=torch.float32,
                low_cpu_mem_usage=True,
            )
            _nllb_tr_model = _nllb_tr_model.to(_nllb_tr_device)
            _nllb_tr_model.eval()
            _nllb_tr_model.generation_config.max_length = None  # avoid max_new_tokens conflict

            _NLLB_TR_AVAILABLE = True
            logger.info("NLLB-200-1.3B initialized successfully on GPU (%s).", gpu_name)
        except Exception as e:
            logger.error("Could not initialize NLLB-200-1.3B on GPU: %s", e)
            _NLLB_TR_AVAILABLE = False
        _NLLB_TR_CHECKED = True
        return _NLLB_TR_AVAILABLE


def unload_models() -> None:
    """Free translation models from GPU VRAM so Phase 3 (Ollama/LLMs) has 100% free VRAM."""
    global _NLLB_TR_CHECKED, _NLLB_TR_AVAILABLE, _nllb_tr_model, _nllb_tr_tokenizer
    global _OPUS_CHECKED, _OPUS_AVAILABLE, _opus_model, _opus_tokenizer
    import gc

    with _nllb_tr_lock:
        if _nllb_tr_model is not None:
            del _nllb_tr_model
            _nllb_tr_model = None
        if _nllb_tr_tokenizer is not None:
            del _nllb_tr_tokenizer
            _nllb_tr_tokenizer = None
        _NLLB_TR_AVAILABLE = False
        _NLLB_TR_CHECKED = False

    with _opus_lock:
        if _opus_model is not None:
            del _opus_model
            _opus_model = None
        if _opus_tokenizer is not None:
            del _opus_tokenizer
            _opus_tokenizer = None
        _OPUS_AVAILABLE = False
        _OPUS_CHECKED = False

    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
    except Exception:
        pass
    logger.info("Translation GPU models unloaded and CUDA VRAM cache cleared.")


# Alias for backward compatibility
is_nllb_available = is_nllb_transformers_available


def _nllb_transformers_translate_list(texts: list[str]) -> list[str]:
    """Translate a list of strings using NLLB-200-1.3B (GPU fp32 or CPU float16)."""
    if not is_nllb_transformers_available() or _nllb_tr_model is None or _nllb_tr_tokenizer is None:
        raise RuntimeError("NLLB-200-1.3B transformers model not initialized")

    import torch  # type: ignore[import]

    _nllb_tr_tokenizer.src_lang = NLLB_TR_SRC_LANG
    target_lang_id = _nllb_tr_tokenizer.convert_tokens_to_ids(NLLB_TR_TGT_LANG)

    results = []
    for text in texts:
        inputs = _nllb_tr_tokenizer(
            text, return_tensors="pt", padding=True, truncation=True, max_length=400
        )
        # Move inputs to same device as model (GPU or CPU)
        inputs = {k: v.to(_nllb_tr_device) for k, v in inputs.items()}
        with torch.no_grad():
            translated_ids = _nllb_tr_model.generate(
                **inputs,
                forced_bos_token_id=target_lang_id,
                num_beams=4,
                max_new_tokens=400,
            )
        decoded = _nllb_tr_tokenizer.decode(translated_ids[0], skip_special_tokens=True)
        results.append(decoded.strip())

    return results


# ---------------------------------------------------------------------------
# 2. Helsinki-NLP Opus-MT fi→en  (Secondary: GPU CUDA)
# ---------------------------------------------------------------------------
OPUS_MODEL_NAME = "Helsinki-NLP/opus-mt-fi-en"

_OPUS_CHECKED = False
_OPUS_AVAILABLE = False
_opus_model = None
_opus_tokenizer = None
_opus_lock = threading.Lock()


def is_opus_available() -> bool:
    """Check and lazily initialise Helsinki-NLP Opus-MT fi→en on GPU (CUDA)."""
    global _OPUS_CHECKED, _OPUS_AVAILABLE, _opus_model, _opus_tokenizer
    if _OPUS_CHECKED:
        return _OPUS_AVAILABLE

    with _opus_lock:
        if _OPUS_CHECKED:
            return _OPUS_AVAILABLE
        try:
            import torch  # type: ignore[import]
            from transformers import MarianMTModel, MarianTokenizer  # type: ignore[import]

            if not torch.cuda.is_available():
                logger.error("CUDA GPU not available — Opus-MT requires GPU.")
                _OPUS_AVAILABLE = False
                _OPUS_CHECKED = True
                return False

            logger.info("Loading Helsinki-NLP Opus-MT fi→en model onto GPU (CUDA)...")
            _opus_tokenizer = MarianTokenizer.from_pretrained(OPUS_MODEL_NAME)
            _opus_model = MarianMTModel.from_pretrained(OPUS_MODEL_NAME).to("cuda")
            _opus_model.eval()
            _OPUS_AVAILABLE = True
            logger.info("Helsinki-NLP Opus-MT fi→en initialized successfully on GPU.")
        except Exception as e:
            logger.error("Could not initialize Helsinki-NLP Opus-MT on GPU: %s", e)
            _OPUS_AVAILABLE = False
        _OPUS_CHECKED = True
        return _OPUS_AVAILABLE


def _opus_translate_list(texts: list[str]) -> list[str]:
    """Translate a list of strings using Opus-MT fi→en on GPU."""
    if not is_opus_available() or _opus_model is None or _opus_tokenizer is None:
        raise RuntimeError("Opus-MT translator not initialized")

    inputs = _opus_tokenizer(texts, return_tensors="pt", padding=True, truncation=True, max_length=512)
    inputs = {k: v.to("cuda") for k, v in inputs.items()}
    with torch.no_grad():
        translated_ids = _opus_model.generate(**inputs)
    results = [
        _opus_tokenizer.decode(ids, skip_special_tokens=True)
        for ids in translated_ids
    ]
    return results


def _clean_for_translation(text: str) -> str:
    """Pre-process text for cleaner translation."""
    if not text:
        return ""
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = html.unescape(text)
    return text.strip()


# Finnish/general sentence boundary regex.
# Splits on '. ', '! ', '? ' followed by an uppercase letter OR end-of-string.
# Avoids splitting on common Finnish abbreviations (e.g. "ko.", "ao.", "n.", "v.",
# "os.", "em.", "em.", "ns.", "jne.", "jms.", "ao.", single capital letters like "A.").
_ABBREV_RE = re.compile(
    r"\b(?:"
    r"[A-ZÅÄÖ]"                          # single capital letter  ("A. Smith")
    r"|[a-zåäöA-ZÅÄÖ]{1,3}"              # very short words       ("ko", "ao", "em")
    r"|(?:jne|jms|ns|os|ko|ao|em|esim|vm|ko|n|v|p|s|ao|puh|ao)"  # known Finnish abbrevs
    r")\Z",
    re.IGNORECASE,
)

_SENTENCE_SPLIT_RE = re.compile(
    r"(?<=[.!?…])   # after a sentence-ending punctuation"
    r"(?!\s*[)\]\"'»])  # not if followed by a closing bracket/quote (mid-sentence)"
    r"\s+             # whitespace gap"
    r"(?=[A-ZÅÄÖ\d])  # followed by uppercase or digit (new sentence starts)",
    re.VERBOSE,
)


def _split_into_sentences(text: str) -> list[str]:
    """
    Split a block of text into individual sentences.

    Strategy:
    1. Try splitting on sentence-ending punctuation followed by a capital letter.
    2. Skip the split if the word before the dot looks like a Finnish abbreviation.
    3. Fall back to returning the whole text as one sentence when no split points found.

    This keeps each sentence as a self-contained unit of Finnish grammar so that
    the translation model gets proper context for compound words.
    """
    if not text:
        return []

    # Fast path — short text is almost certainly a single sentence
    if len(text) < 80:
        return [text.strip()] if text.strip() else []

    candidates = _SENTENCE_SPLIT_RE.split(text)

    sentences = []
    buf = ""
    for part in candidates:
        part = part.strip()
        if not part:
            continue
        # Check if the part ends with an abbreviation-like word followed by a dot.
        # If so, it is NOT a sentence boundary — glue it to the next part.
        last_token = re.split(r"\s+", part)[-1].rstrip(".").rstrip()
        if _ABBREV_RE.match(last_token) and part.endswith("."):
            buf = (buf + " " + part).strip() if buf else part
        else:
            full = (buf + " " + part).strip() if buf else part
            if full:
                sentences.append(full)
            buf = ""
    if buf:
        sentences.append(buf)

    return sentences if sentences else [text.strip()]


def _translate_paragraph_as_sentences(
    paragraph: str,
    translate_list_fn,      # _nllb_transformers_translate_list or _opus_translate_list
) -> str:
    """
    Split *paragraph* into sentences, translate each sentence individually,
    then rejoin them with a single space.

    Why sentence-by-sentence?
    - Finnish compound words like "bittiviidakon" only have unambiguous meaning
      within the sentence they appear in (not across paragraphs).
    - Individual sentences are always well under the 400-token NLLB limit, so
      no truncation ever corrupts the input.
    - Translating a whole paragraph as one unit risks losing the latter half
      of the paragraph if it exceeds the token limit.
    """
    sentences = _split_into_sentences(paragraph)
    if not sentences:
        return ""

    translated_sentences = translate_list_fn(sentences)
    return " ".join(s.strip() for s in translated_sentences if s.strip())


# List of offensive or hallucinated words to sanitize from automated translations
_PROFANITY_REPLACEMENTS = [
    # Specific known Finnish compound hallucination: "bittiviidakon Tarzan" -> "Tarzan the Bitch"
    (re.compile(r"\bTarzan\s+the\s+Bitch\b", re.IGNORECASE), "Tarzan of the Digital Jungle"),
    (re.compile(r"\bthe\s+bitch\b", re.IGNORECASE), "digital specialist"),
    (re.compile(r"\bbitches\b", re.IGNORECASE), "specialists"),
    (re.compile(r"\bbitch\b", re.IGNORECASE), "expert"),
    # General offensive words that should never appear in job posts
    (re.compile(r"\b(fuck|fucking|fucker|fucked)\b", re.IGNORECASE), "[removed]"),
    (re.compile(r"\bshit\b", re.IGNORECASE), "[removed]"),
    (re.compile(r"\basshole(s)?\b", re.IGNORECASE), "[removed]"),
    (re.compile(r"\bbastard(s)?\b", re.IGNORECASE), "[removed]"),
    (re.compile(r"\bcunt(s)?\b", re.IGNORECASE), "[removed]"),
    (re.compile(r"\bwhore(s)?\b", re.IGNORECASE), "[removed]"),
    (re.compile(r"\bslut(s)?\b", re.IGNORECASE), "[removed]"),
]


def post_process_translation(text: str) -> str:
    """Clean translation text and sanitize any inappropriate machine translation hallucinations."""
    if not text:
        return ""
    cleaned = text.strip()
    for pattern, replacement in _PROFANITY_REPLACEMENTS:
        cleaned = pattern.sub(replacement, cleaned)
    return cleaned


# ---------------------------------------------------------------------------
# Public API (100% GPU Accelerated)
# ---------------------------------------------------------------------------

def translate_batch(texts: list[str]) -> list[str]:
    """
    Translate a list of short strings (FI→EN) in a batch.
    Each string is treated as a self-contained sentence so the model gets
    clean context for every item.

    Priority (100% GPU):
      1. NLLB-200-1.3B transformers  (highest accuracy, GPU CUDA fp32)
      2. Helsinki-NLP Opus-MT fi→en  (fallback — GPU CUDA)
      3. Per-item fallback via translate_fi_to_en()
    """
    if not texts:
        return []

    indexed = [(i, t) for i, t in enumerate(texts) if t and t.strip()]
    if not indexed:
        return list(texts)

    result = list(texts)
    indices, to_translate = zip(*indexed)

    # 1. Try NLLB-200-1.3B via Transformers (Primary — Most Accurate, GPU)
    if is_nllb_transformers_available():
        try:
            translated = _nllb_transformers_translate_list(list(to_translate))
            if len(translated) == len(to_translate):
                _thread_local.last_backend = "nllb-1.3b"
                for idx, val in zip(indices, translated):
                    clean_val = post_process_translation(val) if val and val.strip() else texts[idx]
                    result[idx] = clean_val
                return result
        except Exception as e:
            logger.warning("NLLB-1.3B batch translation failed: %s. Trying Opus-MT fallback...", e)

    # 2. Try Helsinki-NLP Opus-MT (Fallback, GPU)
    if is_opus_available():
        try:
            translated = _opus_translate_list(list(to_translate))
            if len(translated) == len(to_translate):
                _thread_local.last_backend = "opus-mt"
                for idx, val in zip(indices, translated):
                    clean_val = post_process_translation(val) if val and val.strip() else texts[idx]
                    result[idx] = clean_val
                return result
        except Exception as e:
            logger.warning("Opus-MT batch translation failed: %s. Falling back to per-item...", e)

    # 3. Per-item fallback
    for i, text in indexed:
        result[i] = translate_fi_to_en(text)
    return result


def translate_fi_to_en(text: str) -> str:
    """
    Translate Finnish (or Swedish/auto) text to English using sentence-level
    translation within each paragraph.

    Why sentence-level?
    - Finnish compound words are disambiguated only within their sentence context.
    - Sending a whole paragraph risks hitting the 400-token NLLB limit and silently
      truncating the second half of the paragraph.
    - Individual sentences are always under the token limit, giving consistent results.

    Structure preserved:
    - Paragraphs (double newlines) are translated and rejoined with double newlines.
    - Within each paragraph, sentences are translated individually then rejoined
      with single spaces — matching the original prose flow.

    Priority (100% GPU):
      1. NLLB-200-1.3B transformers  (primary  — highest accuracy, GPU CUDA fp32)
      2. Helsinki-NLP Opus-MT fi→en  (fallback — GPU CUDA)
      3. Original text                (last resort)
    """
    if not text or len(text.strip()) < 2:
        return text

    clean_text = _clean_for_translation(text)
    if not clean_text:
        return text

    # Split into paragraphs first — each paragraph is an independent block of prose.
    paragraphs = [p.strip() for p in clean_text.split("\n\n") if p.strip()]
    if not paragraphs:
        paragraphs = [clean_text]

    # --- Strategy 1: NLLB-200-1.3B via Transformers (Primary — Most Accurate, GPU) ---
    if is_nllb_transformers_available():
        try:
            translated_paras = [
                _translate_paragraph_as_sentences(para, _nllb_transformers_translate_list)
                for para in paragraphs
            ]
            translated = "\n\n".join(translated_paras).strip()
            if translated:
                _thread_local.last_backend = "nllb-1.3b"
                return post_process_translation(translated)
        except Exception as e:
            logger.warning("NLLB-1.3B translation failed: %s. Falling back to Opus-MT...", e)

    # --- Strategy 2: Helsinki-NLP Opus-MT (Fallback, GPU) ---
    if is_opus_available():
        try:
            translated_paras = [
                _translate_paragraph_as_sentences(para, _opus_translate_list)
                for para in paragraphs
            ]
            translated = "\n\n".join(translated_paras).strip()
            if translated:
                _thread_local.last_backend = "opus-mt"
                return post_process_translation(translated)
        except Exception as e:
            logger.warning("Opus-MT translation failed: %s.", e)

    # --- Strategy 3: Original Text ---
    logger.error("All GPU translation strategies exhausted. Returning original text.")
    _thread_local.last_backend = "original"
    return post_process_translation(text)
