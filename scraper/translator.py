"""
Wrapper for translation (FI->EN).
Uses deep-translator (Google Translate) for vastly better contextual translation 
than ArgosTranslate, preserving idioms and proper grammar.
"""
import logging
import re
import html
import time
try:
    from deep_translator import GoogleTranslator
    _TRANSLATOR_AVAILABLE = True
except ImportError:
    _TRANSLATOR_AVAILABLE = False

logger = logging.getLogger("translator")

_auto_to_en = None

# Retry configuration
_MAX_RETRIES = 3
_RETRY_DELAYS = [1, 2, 4]  # seconds to wait before each retry attempt

def _get_translator():
    global _auto_to_en
    if not _TRANSLATOR_AVAILABLE:
        logger.warning("deep-translator not installed, translation disabled.")
        return None
    
    if _auto_to_en is None:
        try:
            _auto_to_en = GoogleTranslator(source='auto', target='en')
            logger.info("Deep-translator (Google) model loaded successfully (source='auto').")
        except Exception as e:
            logger.error(f"Failed to initialize translator: {e}")
            return None
    
    return _auto_to_en

def _clean_for_translation(text: str) -> str:
    """Pre-process text for better translation results."""
    if not text:
        return ""
    # Remove excessive blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Ensure quotes are literal
    text = html.unescape(text)
    return text.strip()

def _translate_with_retry(translator, chunk: str) -> str:
    """
    Translates a single chunk of text, retrying on failure with increasing delays.
    Returns the translated text, or the original chunk if all retries are exhausted.
    """
    for attempt in range(_MAX_RETRIES):
        try:
            result = translator.translate(chunk)
            if result and len(result.strip()) > 0:
                return result
            # If result is empty, treat it as a failure and retry
            raise ValueError("Empty translation returned")
        except Exception as e:
            if attempt < _MAX_RETRIES - 1:
                delay = _RETRY_DELAYS[attempt]
                logger.warning(
                    f"Translation attempt {attempt + 1}/{_MAX_RETRIES} failed: {e}. "
                    f"Retrying in {delay}s..."
                )
                time.sleep(delay)
            else:
                logger.error(
                    f"Translation failed after {_MAX_RETRIES} attempts: {e}"
                )
                return chunk  # Fall back to original text

def translate_fi_to_en(text: str) -> str:
    """
    Translates Finnish (or Swedish/other auto-detected languages) text to English using Google Translator.
    Handles texts larger than 4900 characters by chunking.
    Retries up to 3 times with increasing delays on failure, then falls
    back to the original text if all retries are exhausted.
    """
    if not text or len(text.strip()) < 2:
        return text

    translator = _get_translator()
    if not translator:
        return text
    
    try:
        clean_text = _clean_for_translation(text)
        
        # Google Translate API has a 5K char limit. Chunk if necessary.
        limit = 4900
        if len(clean_text) <= limit:
            translated = _translate_with_retry(translator, clean_text)
        else:
            logger.info(f"Text too long ({len(clean_text)} chars). Chunking translation...")
            translated_pieces = []
            paragraphs = clean_text.split('\n\n')
            current_chunk = ""
            for p in paragraphs:
                if len(current_chunk) + len(p) + 2 < limit:
                    current_chunk += p + "\n\n"
                else:
                    if current_chunk.strip():
                        translated_pieces.append(_translate_with_retry(translator, current_chunk.strip()))
                    current_chunk = p + "\n\n"
                    
            if current_chunk.strip():
                # If a single paragraph is outrageously long, chunk it by rough length
                if len(current_chunk) >= limit:
                    logger.warning("Extremely long single paragraph encountered. Forcing manual split.")
                    parts = [current_chunk[i:i+limit] for i in range(0, len(current_chunk), limit)]
                    for part in parts:
                        translated_pieces.append(_translate_with_retry(translator, part.strip()))
                else:
                    translated_pieces.append(_translate_with_retry(translator, current_chunk.strip()))
                
            translated = "\n\n".join(translated_pieces)
            
        # Prevent completely corrupted returns
        if not translated or len(translated.strip()) == 0:
            return text
            
        return translated.strip()
    except Exception as e:
        logger.error(f"Translation pipeline error: {e}")
        return text
