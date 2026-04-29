"""
Wrapper for translation (FI->EN).
Uses deep-translator (Google Translate) with MyMemory as fallback.

SSL FIX: The GoogleTranslator instance is re-created on every retry attempt
so each attempt opens a brand-new HTTP connection. The UNEXPECTED_EOF_WHILE_READING
error occurs when Google drops an already-open SSL session; forcing a new
connection avoids re-using the stale, dead socket.
"""
import logging
import re
import html
import time

logger = logging.getLogger("translator")

try:
    from deep_translator import GoogleTranslator
    _GOOGLE_AVAILABLE = True
except ImportError:
    _GOOGLE_AVAILABLE = False
    logger.warning("deep-translator not installed; Google translation disabled.")

try:
    from deep_translator import MyMemoryTranslator
    _MYMEMORY_AVAILABLE = True
except ImportError:
    _MYMEMORY_AVAILABLE = False

# ---------------------------------------------------------------------------
# Retry configuration
# ---------------------------------------------------------------------------
_MAX_RETRIES = 3
_RETRY_DELAYS = [2, 5, 10]   # seconds – longer gaps give Google time to recover

# MyMemory hard limit per request
_MYMEMORY_CHUNK_LIMIT = 490


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _new_google() -> "GoogleTranslator | None":
    """Always returns a *fresh* GoogleTranslator (new HTTP session)."""
    if not _GOOGLE_AVAILABLE:
        return None
    try:
        return GoogleTranslator(source="auto", target="en")
    except Exception as e:
        logger.error(f"Failed to create GoogleTranslator: {e}")
        return None


def _new_mymemory() -> "MyMemoryTranslator | None":
    if not _MYMEMORY_AVAILABLE:
        return None
    try:
        return MyMemoryTranslator(source="fi-FI", target="en-US")
    except Exception as e:
        logger.error(f"Failed to create MyMemoryTranslator: {e}")
        return None


def _clean_for_translation(text: str) -> str:
    """Pre-process text for better translation results."""
    if not text:
        return ""
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = html.unescape(text)
    return text.strip()


def _mymemory_translate(chunk: str) -> str | None:
    """
    Translate via MyMemory (500-char per-request limit).
    Splits the chunk internally if needed.
    Returns translated text, or None on failure.
    """
    if not _MYMEMORY_AVAILABLE:
        return None
    try:
        translator = _new_mymemory()
        if not translator:
            return None

        # MyMemory rejects requests longer than ~500 chars
        if len(chunk) <= _MYMEMORY_CHUNK_LIMIT:
            result = translator.translate(chunk)
            return result if result and result.strip() else None

        # Split into sub-chunks
        parts = [
            chunk[i : i + _MYMEMORY_CHUNK_LIMIT]
            for i in range(0, len(chunk), _MYMEMORY_CHUNK_LIMIT)
        ]
        translated_parts = []
        for part in parts:
            t = _new_mymemory()
            if not t:
                return None
            r = t.translate(part.strip())
            if r and r.strip():
                translated_parts.append(r.strip())
            else:
                return None  # partial failure – bail out
        return " ".join(translated_parts)
    except Exception as e:
        logger.warning(f"MyMemory translation failed: {e}")
        return None


def _translate_chunk(chunk: str) -> str:
    """
    Translate a single chunk (≤4900 chars) with retry logic.
    - Each attempt creates a FRESH GoogleTranslator (new SSL connection).
    - After all Google attempts fail, falls back to MyMemory.
    - If MyMemory also fails, returns the original chunk unchanged.
    """
    last_error = None

    for attempt in range(_MAX_RETRIES):
        try:
            translator = _new_google()
            if not translator:
                break  # Google unavailable, skip to fallback
            result = translator.translate(chunk)
            if result and result.strip():
                return result
            raise ValueError("Empty translation returned")
        except Exception as e:
            last_error = e
            if attempt < _MAX_RETRIES - 1:
                delay = _RETRY_DELAYS[attempt]
                logger.warning(
                    f"Translation attempt {attempt + 1}/{_MAX_RETRIES} failed: {e}. "
                    f"Retrying in {delay}s..."
                )
                time.sleep(delay)
            else:
                logger.error(
                    f"Google translation failed after {_MAX_RETRIES} attempts: {e}. "
                    "Trying MyMemory fallback..."
                )

    # --- MyMemory fallback ---
    result = _mymemory_translate(chunk)
    if result:
        logger.info("MyMemory fallback translation succeeded.")
        return result

    logger.error(f"All translation attempts exhausted. Returning original text.")
    return chunk


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def translate_fi_to_en(text: str) -> str:
    """
    Translates Finnish (or auto-detected) text to English.
    Handles texts larger than 4900 characters by splitting into paragraph chunks.
    Falls back to original text only if every strategy fails.
    """
    if not text or len(text.strip()) < 2:
        return text

    if not _GOOGLE_AVAILABLE and not _MYMEMORY_AVAILABLE:
        logger.warning("No translation backend available.")
        return text

    try:
        clean_text = _clean_for_translation(text)
        limit = 4900

        if len(clean_text) <= limit:
            return _translate_chunk(clean_text)

        # --- Chunked translation for long texts ---
        logger.info(f"Text too long ({len(clean_text)} chars). Chunking translation...")
        translated_pieces = []
        paragraphs = clean_text.split("\n\n")
        current_chunk = ""

        for p in paragraphs:
            if len(current_chunk) + len(p) + 2 <= limit:
                current_chunk += p + "\n\n"
            else:
                if current_chunk.strip():
                    translated_pieces.append(_translate_chunk(current_chunk.strip()))
                current_chunk = p + "\n\n"

        if current_chunk.strip():
            if len(current_chunk) >= limit:
                logger.warning("Extremely long single paragraph. Forcing manual split.")
                parts = [
                    current_chunk[i : i + limit]
                    for i in range(0, len(current_chunk), limit)
                ]
                for part in parts:
                    translated_pieces.append(_translate_chunk(part.strip()))
            else:
                translated_pieces.append(_translate_chunk(current_chunk.strip()))

        translated = "\n\n".join(translated_pieces)

        if not translated or not translated.strip():
            return text

        return translated.strip()

    except Exception as e:
        logger.error(f"Translation pipeline error: {e}")
        return text
