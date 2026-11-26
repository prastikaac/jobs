"""
Wrapper for translation (FI/SV->EN).

Priority order:
  1. Google Translate Free Web API (`client=gtx` / `clients5`) — Primary (0 GPU VRAM)
  2. Meta NLLB-200-1.3B via Transformers — Secondary / Backup 1 (Local GPU CUDA fp32)
  3. Helsinki-NLP Opus-MT fi->en — Tertiary / Backup 2 (Local GPU CUDA)
  4. deep-translator (GoogleTranslator / MyMemoryTranslator) — Quaternary
  5. Original text — Last resort
"""
import html
import json
import logging
import re
import threading
import time
import urllib.parse
import urllib.request

try:
    import torch
except ImportError:
    torch = None  # type: ignore[assignment]

logger = logging.getLogger("translator")

# Thread-local storage so parallel workers track their own backend
_thread_local = threading.local()

# Chunk size limit per Google Translate request
_GOOGLE_CHUNK_LIMIT = 4500
_MAX_RETRIES = 3
_RETRY_DELAYS = [1.5, 3.0, 6.0]

try:
    from deep_translator import GoogleTranslator, MyMemoryTranslator  # type: ignore[import]
    _DEEP_TRANSLATOR_AVAILABLE = True
except ImportError:
    _DEEP_TRANSLATOR_AVAILABLE = False


def get_last_backend() -> str:
    """Return the translation backend used in the most recent call on this thread."""
    return getattr(_thread_local, "last_backend", "unknown")


# ===========================================================================
# 1. Primary: Free Google Translate Web API
# ===========================================================================

def _google_gtx_translate(chunk: str) -> str | None:
    """
    Translate `chunk` via Google Translate's free `client=gtx` endpoint (POST).
    Returns translated string or None on failure.
    """
    url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=en&dt=t"
    body = urllib.parse.urlencode({"q": chunk}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw_json = resp.read().decode("utf-8")
    data = json.loads(raw_json)
    if not data or not isinstance(data, list) or not data[0]:
        return None
    translated = "".join(part[0] for part in data[0] if part and part[0])
    return translated.strip() if translated and translated.strip() else None


def _google_clients5_translate(chunk: str) -> str | None:
    """
    Fallback free Google Translate endpoint (`clients5.google.com/translate_a/t`).
    """
    url = "https://clients5.google.com/translate_a/t?client=dict-chrome-ex&sl=auto&tl=en"
    body = urllib.parse.urlencode({"q": chunk}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        raw_json = resp.read().decode("utf-8")
    data = json.loads(raw_json)
    if isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, list) and first:
            return str(first[0]).strip()
        if isinstance(first, str):
            return first.strip()
    return None


def _try_google_translate(chunk: str) -> str | None:
    """
    Attempt translation of chunk via Google Translate Free endpoints with retries.
    Returns translated text or None if all attempts fail.
    """
    for attempt in range(_MAX_RETRIES):
        try:
            res = _google_gtx_translate(chunk)
            if res:
                _thread_local.last_backend = "google-free"
                return res
        except Exception as e1:
            try:
                res2 = _google_clients5_translate(chunk)
                if res2:
                    _thread_local.last_backend = "google-clients5"
                    return res2
            except Exception:
                pass
            if attempt < _MAX_RETRIES - 1:
                delay = _RETRY_DELAYS[attempt]
                logger.warning(
                    "Google Translate attempt %d/%d failed (%s). Retrying in %.1fs...",
                    attempt + 1, _MAX_RETRIES, e1, delay,
                )
                time.sleep(delay)
            else:
                logger.warning("Google Translate failed after %d attempts: %s", _MAX_RETRIES, e1)
    return None


# ===========================================================================
# 2. Secondary (Backup 1): Meta NLLB-200-1.3B (Local GPU CUDA fp32)
# ===========================================================================
NLLB_TR_MODEL = "facebook/nllb-200-distilled-1.3B"
NLLB_TR_SRC_LANG = "fin_Latn"
NLLB_TR_TGT_LANG = "eng_Latn"

_NLLB_TR_CHECKED = False
_NLLB_TR_AVAILABLE = False
_nllb_tr_model = None
_nllb_tr_tokenizer = None
_nllb_tr_device = "cuda"
_nllb_tr_lock = threading.Lock()


def _evict_ollama_vram() -> None:
    """Evict any loaded models from Ollama to free GPU VRAM for local translation models."""
    try:
        url = "http://127.0.0.1:11434/api/generate"
        payload = json.dumps({"model": "qwen2.5:7b-instruct", "keep_alive": 0}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            pass
        logger.info("Evicted Ollama model from GPU VRAM.")
    except Exception:
        pass


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

            # Free Ollama if it is occupying GPU VRAM before loading NLLB
            _evict_ollama_vram()

            _nllb_tr_device = "cuda"
            gpu_name = torch.cuda.get_device_name(0)
            vram_gb = torch.cuda.get_device_properties(0).total_memory / 1e9
            logger.info(
                "Loading Secondary (Backup 1) NLLB-200-1.3B on GPU: %s (%.1f GB VRAM) in fp32...",
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


is_nllb_available = is_nllb_transformers_available


def _nllb_transformers_translate_list(texts: list[str]) -> list[str]:
    """Translate a list of strings using NLLB-200-1.3B on GPU (fp32)."""
    if not is_nllb_transformers_available() or _nllb_tr_model is None or _nllb_tr_tokenizer is None:
        raise RuntimeError("NLLB-200-1.3B transformers model not initialized")

    import torch  # type: ignore[import]

    _nllb_tr_tokenizer.src_lang = NLLB_TR_SRC_LANG
    target_lang_id = _nllb_tr_tokenizer.convert_tokens_to_ids(NLLB_TR_TGT_LANG)

    results = []
    for text in texts:
        if not text or not text.strip():
            results.append("")
            continue
        inputs = _nllb_tr_tokenizer(
            text, return_tensors="pt", padding=True, truncation=True, max_length=400
        )
        inputs = {k: v.to(_nllb_tr_device) for k, v in inputs.items()}
        seq_len = inputs["input_ids"].shape[1]
        dyn_max_new_tokens = min(400, max(32, int(seq_len * 1.6) + 24))
        with torch.inference_mode():
            translated_ids = _nllb_tr_model.generate(
                **inputs,
                forced_bos_token_id=target_lang_id,
                num_beams=2,
                max_new_tokens=dyn_max_new_tokens,
            )
        decoded = _nllb_tr_tokenizer.decode(translated_ids[0], skip_special_tokens=True)
        results.append(decoded.strip())

    return results


# ===========================================================================
# 3. Tertiary (Backup 2): Helsinki-NLP Opus-MT fi→en (Local GPU CUDA)
# ===========================================================================
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

            _evict_ollama_vram()
            logger.info("Loading Tertiary (Backup 2) Helsinki-NLP Opus-MT fi→en model onto GPU (CUDA)...")
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

    import torch  # type: ignore[import]
    results = []
    for text in texts:
        if not text or not text.strip():
            results.append("")
            continue
        inputs = _opus_tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=512)
        inputs = {k: v.to("cuda") for k, v in inputs.items()}
        with torch.inference_mode():
            translated_ids = _opus_model.generate(**inputs, max_new_tokens=400)
        decoded = _opus_tokenizer.decode(translated_ids[0], skip_special_tokens=True)
        results.append(decoded.strip())
    return results


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


# ===========================================================================
# 4. Text Processing, Language Check & Sentence Splitting
# ===========================================================================

_FI_SV_INDICATORS_RE = re.compile(
    r"\b(?:"
    r"ja|on|ei|että|kuin|mutta|tai|kun|jos|sekä|myös|ovat|ole|oli|tule|tulee|"
    r"haemme|etsimme|tarjoamme|odotamme|toivomme|edellytämme|arvostamme|"
    r"työ|työhön|työssä|työskentely|työtehtävät|tehtävä|tehtävässä|tehtäviin|"
    r"asiakas|tiimi|suomen|suomi|englanti|ruotsi|kokoaikainen|kokoaikatyö|"
    r"osa-aikainen|osa-aikatyö|vakituinen|määräaikainen|kesätyö|"
    r"hakemus|palkka|kokemus|osaaminen|koulutus|sinulla|sinulta|sinua|sinulle|"
    r"meillä|meiltä|meille|kanssa|kautta|mukaan|lisäksi|esimerkiksi|"
    r"vastaat|toimit|osallistut|lisätietoja|lähetä|hae|viimeistään|yhteystiedot|"
    r"och|att|det|som|för|på|med|till|av|är|vi|du|dig|har|kan|vill|hos|inom"
    r")\b",
    re.IGNORECASE,
)

_EN_WORDS = {
    "the", "and", "to", "of", "in", "for", "with", "on", "at", "from", "by",
    "about", "as", "into", "through", "after", "over", "between", "without",
    "before", "under", "around", "among", "we", "you", "our", "your", "are",
    "is", "will", "be", "have", "has", "can", "work", "working", "team",
    "role", "experience", "skills", "looking", "join", "responsibilities",
    "requirements", "position", "company", "business", "development",
    "support", "customer", "service", "management", "project", "please",
    "apply", "application", "knowledge", "strong", "ability", "opportunity",
    "environment", "solutions", "global", "including", "ensure", "provide",
}


def _is_already_english(text: str) -> bool:
    """
    Fast, conservative check for whether text is already in English.
    Never returns True if Finnish/Swedish characters (ä, ö, å) or indicator words appear.
    """
    if not text:
        return True
    s = text.strip()
    if not s:
        return True
    if not any(ch.isalpha() for ch in s):
        return True
    if any(ch in s for ch in "äöåÄÖÅ"):
        return False
    if _FI_SV_INDICATORS_RE.search(s):
        return False

    words = [w.lower() for w in re.findall(r"[A-Za-z]+", s)]
    if len(words) < 4:
        return False
    en_hits = sum(1 for w in words if w in _EN_WORDS)
    return (en_hits / len(words)) >= 0.25


def _clean_for_translation(text: str) -> str:
    """Pre-process text for cleaner translation."""
    if not text:
        return ""
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = html.unescape(text)
    return text.strip()


_ABBREV_RE = re.compile(
    r"\b(?:"
    r"[A-ZÅÄÖ]"                          # single capital letter  ("A. Smith")
    r"|[a-zåäöA-ZÅÄÖ]{1,3}"              # very short words       ("ko", "ao", "em")
    r"|(?:jne|jms|ns|os|ko|ao|em|esim|vm|ko|n|v|p|s|ao|puh|ao)"  # known Finnish abbrevs
    r")\Z",
    re.IGNORECASE,
)

_SENTENCE_SPLIT_RE = re.compile(
    r"(?<=[.!?…])"       # after a sentence-ending punctuation
    r"(?!\s*[)\]\"'»])"  # not if followed by a closing bracket/quote (mid-sentence)
    r"\s+"               # whitespace gap
    r"(?=[A-ZÅÄÖ\d])",   # followed by uppercase or digit (new sentence starts)
)


def _subsplit_long_sentence(sentence: str, max_chars: int = 400) -> list[str]:
    """
    If a sentence is longer than max_chars, sub-split it on semicolons, colons, or commas
    to guarantee it never exceeds NLLB token limits.
    """
    if len(sentence) <= max_chars:
        return [sentence]

    sub_parts = re.split(r"(?<=[;:])\s+", sentence)
    if len(sub_parts) > 1 and all(len(p) <= max_chars for p in sub_parts):
        return [p.strip() for p in sub_parts if p.strip()]

    sub_parts = re.split(r"(?<=,)\s+", sentence)
    if len(sub_parts) > 1:
        merged = []
        cur = ""
        for p in sub_parts:
            if cur and len(cur) + len(p) + 2 > max_chars:
                merged.append(cur.strip())
                cur = p
            else:
                cur = f"{cur}, {p}" if cur else p
        if cur.strip():
            merged.append(cur.strip())
        return merged

    words = sentence.split()
    chunks = []
    curr = []
    curr_len = 0
    for w in words:
        if curr_len + len(w) + 1 > max_chars and curr:
            chunks.append(" ".join(curr))
            curr = [w]
            curr_len = len(w)
        else:
            curr.append(w)
            curr_len += len(w) + 1
    if curr:
        chunks.append(" ".join(curr))
    return chunks


def _split_into_sentences(text: str) -> list[str]:
    """
    Split a block of text into individual sentences.
    Safe against Finnish abbreviations and ensures no sentence exceeds 400 chars.
    """
    if not text:
        return []

    if len(text) < 80:
        return [text.strip()] if text.strip() else []

    candidates = _SENTENCE_SPLIT_RE.split(text)

    sentences = []
    buf = ""
    for part in candidates:
        part = part.strip()
        if not part:
            continue
        last_token = re.split(r"\s+", part)[-1].rstrip(".").rstrip()
        if _ABBREV_RE.match(last_token) and part.endswith("."):
            buf = (buf + " " + part).strip() if buf else part
        else:
            full = (buf + " " + part).strip() if buf else part
            if full:
                sentences.extend(_subsplit_long_sentence(full, max_chars=400))
            buf = ""
    if buf:
        sentences.extend(_subsplit_long_sentence(buf, max_chars=400))

    return sentences if sentences else _subsplit_long_sentence(text.strip(), max_chars=400)


def _translate_paragraph_with_gpu(paragraph: str) -> str | None:
    """
    Fallback: Translate a paragraph using local GPU models.
    Tries Meta NLLB-200-1.3B first (Secondary), then Helsinki-NLP Opus-MT (Tertiary).
    """
    sentences = _split_into_sentences(paragraph)
    if not sentences:
        return ""

    # Secondary: Meta NLLB-200-1.3B (Local GPU fp32)
    if is_nllb_transformers_available():
        try:
            trans_list = _nllb_transformers_translate_list(sentences)
            joined = " ".join(s for s in trans_list if s).strip()
            if joined:
                _thread_local.last_backend = "nllb-1.3b"
                return joined
        except Exception as e:
            logger.warning("NLLB-1.3B paragraph translation failed: %s. Trying Opus-MT...", e)

    # Tertiary: Helsinki-NLP Opus-MT fi->en (Local GPU)
    if is_opus_available():
        try:
            trans_list = _opus_translate_list(sentences)
            joined = " ".join(s for s in trans_list if s).strip()
            if joined:
                _thread_local.last_backend = "opus-mt"
                return joined
        except Exception as e:
            logger.warning("Opus-MT paragraph translation failed: %s.", e)

    return None


# List of offensive or hallucinated words to sanitize from automated translations
_PROFANITY_REPLACEMENTS = [
    (re.compile(r"\bTarzan\s+the\s+Bitch\b", re.IGNORECASE), "Tarzan of the Digital Jungle"),
    (re.compile(r"\bthe\s+bitch\b", re.IGNORECASE), "digital specialist"),
    (re.compile(r"\bbitches\b", re.IGNORECASE), "specialists"),
    (re.compile(r"\bbitch\b", re.IGNORECASE), "expert"),
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


# ===========================================================================
# 5. Core Translation Pipeline
# ===========================================================================

def _translate_chunk(chunk: str) -> str:
    """
    Translate a single chunk (<= 4500 chars).
    Priority:
      1. Google Translate Free API (gtx / clients5) — Primary (0 GPU VRAM)
      2. Meta NLLB-200-1.3B (Local GPU CUDA fp32) — Secondary (Backup 1)
      3. Helsinki-NLP Opus-MT fi->en (Local GPU CUDA) — Tertiary (Backup 2)
      4. deep-translator (GoogleTranslator / MyMemory) — Quaternary
      5. Original chunk (last resort)
    """
    if not chunk or not chunk.strip():
        return chunk
    if _is_already_english(chunk):
        _thread_local.last_backend = "english-skip"
        return chunk.strip()

    # 1. Primary: Google Translate Free
    res = _try_google_translate(chunk)
    if res:
        return res

    # 2 & 3. Secondary & Tertiary: Local GPU (NLLB-200-1.3B / Opus-MT)
    logger.info("Falling back to local GPU translation for chunk (%d chars)...", len(chunk))
    paragraphs = [p.strip() for p in chunk.split("\n\n") if p.strip()]
    if paragraphs:
        gpu_paras = []
        gpu_ok = True
        for p in paragraphs:
            trans_p = _translate_paragraph_with_gpu(p)
            if trans_p is not None:
                gpu_paras.append(trans_p)
            else:
                gpu_ok = False
                break
        if gpu_ok and gpu_paras:
            return "\n\n".join(gpu_paras).strip()

    # 4. Quaternary: deep-translator
    if _DEEP_TRANSLATOR_AVAILABLE:
        try:
            res = GoogleTranslator(source="auto", target="en").translate(chunk)
            if res and res.strip():
                _thread_local.last_backend = "deep-translator"
                return res.strip()
        except Exception:
            pass
        if len(chunk) <= 490:
            try:
                res = MyMemoryTranslator(source="fi-FI", target="en-US").translate(chunk)
                if res and res.strip():
                    _thread_local.last_backend = "mymemory"
                    return res.strip()
            except Exception:
                pass

    # 5. Last resort: Original text
    _thread_local.last_backend = "original"
    return chunk


def translate_fi_to_en(text: str) -> str:
    """
    Translate Finnish (or Swedish/auto) text to English.
    Splits texts longer than 4,500 chars on paragraph boundaries.
    """
    if not text or len(text.strip()) < 2:
        return text

    clean_text = _clean_for_translation(text)
    if not clean_text:
        return text

    if len(clean_text) <= _GOOGLE_CHUNK_LIMIT:
        translated = _translate_chunk(clean_text)
        return post_process_translation(translated) if translated else text

    # Chunk long texts by paragraph
    paragraphs = clean_text.split("\n\n")
    translated_pieces: list[str] = []
    current_chunk = ""

    for p in paragraphs:
        if len(current_chunk) + len(p) + 2 <= _GOOGLE_CHUNK_LIMIT:
            current_chunk = f"{current_chunk}\n\n{p}" if current_chunk else p
        else:
            if current_chunk.strip():
                translated_pieces.append(_translate_chunk(current_chunk.strip()))
            if len(p) > _GOOGLE_CHUNK_LIMIT:
                for i in range(0, len(p), _GOOGLE_CHUNK_LIMIT):
                    sub = p[i : i + _GOOGLE_CHUNK_LIMIT].strip()
                    if sub:
                        translated_pieces.append(_translate_chunk(sub))
                current_chunk = ""
            else:
                current_chunk = p

    if current_chunk.strip():
        translated_pieces.append(_translate_chunk(current_chunk.strip()))

    translated = "\n\n".join(piece for piece in translated_pieces if piece).strip()
    return post_process_translation(translated) if translated else text


def translate_title_and_body(title: str, body: str) -> tuple[str, str]:
    """
    Translate job title and job body.
    Combines title and body separated by `\\n\\n` when under the chunk limit so
    Google Translate processes it in 1 request.
    If split fails or text is too long, falls back to translating title and body separately.
    """
    clean_title = _clean_for_translation(title) if title else ""
    clean_body = _clean_for_translation(body) if body else ""

    if not clean_title and not clean_body:
        return "", ""
    if not clean_body:
        return (translate_fi_to_en(clean_title) if clean_title else ""), ""
    if not clean_title:
        return "", (translate_fi_to_en(clean_body) if clean_body else "")

    combined = f"{clean_title}\n\n{clean_body}"
    if len(combined) <= _GOOGLE_CHUNK_LIMIT:
        translated_combined = translate_fi_to_en(combined)
        parts = translated_combined.split("\n\n", 1)
        if len(parts) == 2 and parts[0].strip() and parts[1].strip():
            return post_process_translation(parts[0].strip()), post_process_translation(parts[1].strip())

    # Fallback if combined > limit or newline split didn't match
    trans_title = post_process_translation(translate_fi_to_en(clean_title))
    trans_body = post_process_translation(translate_fi_to_en(clean_body))
    return trans_title, trans_body


def translate_batch(texts: list[str]) -> list[str]:
    """
    Translate a list of strings (FI->EN).
    Priority:
      1. Google Translate Free (bulk delimiter request)
      2. Meta NLLB-200-1.3B (Local GPU fp32)
      3. Helsinki-NLP Opus-MT (Local GPU)
      4. Per-item fallback via translate_fi_to_en()
    """
    if not texts:
        return []

    indexed = [(i, t.strip()) for i, t in enumerate(texts) if t and t.strip()]
    if not indexed:
        return list(texts)

    result = list(texts)
    indices, to_translate = zip(*indexed)

    # Single-item fast path
    if len(to_translate) == 1:
        result[indices[0]] = translate_fi_to_en(to_translate[0])
        return result

    # 1. Primary: Google Translate Free via bulk delimiter
    bulk_text = "\n\n---\n\n".join(to_translate)
    if len(bulk_text) <= _GOOGLE_CHUNK_LIMIT:
        res = _try_google_translate(bulk_text)
        if res:
            parts = [p.strip() for p in re.split(r"\n*-{2,}\n*", res)]
            if len(parts) == len(to_translate):
                for idx, val in zip(indices, parts):
                    result[idx] = post_process_translation(val) if val else texts[idx]
                return result

    # 2. Secondary: Meta NLLB-200-1.3B (Local GPU)
    if is_nllb_transformers_available():
        try:
            translated = _nllb_transformers_translate_list(list(to_translate))
            if len(translated) == len(to_translate):
                _thread_local.last_backend = "nllb-1.3b"
                for idx, val in zip(indices, translated):
                    result[idx] = post_process_translation(val) if val and val.strip() else texts[idx]
                return result
        except Exception as e:
            logger.warning("NLLB-1.3B batch translation failed: %s. Trying Opus-MT...", e)

    # 3. Tertiary: Helsinki-NLP Opus-MT (Local GPU)
    if is_opus_available():
        try:
            translated = _opus_translate_list(list(to_translate))
            if len(translated) == len(to_translate):
                _thread_local.last_backend = "opus-mt"
                for idx, val in zip(indices, translated):
                    result[idx] = post_process_translation(val) if val and val.strip() else texts[idx]
                return result
        except Exception as e:
            logger.warning("Opus-MT batch translation failed: %s.", e)

    # 4. Per-item fallback
    for idx, t in indexed:
        result[idx] = translate_fi_to_en(t)
    return result
