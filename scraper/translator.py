"""
Wrapper for translation (FI->EN).
Uses deep-translator (Google Translate) for vastly better contextual translation 
than ArgosTranslate, preserving idioms and proper grammar.
"""
import logging
import re
import html
try:
    from deep_translator import GoogleTranslator
    _TRANSLATOR_AVAILABLE = True
except ImportError:
    _TRANSLATOR_AVAILABLE = False

logger = logging.getLogger("translator")

_fi_to_en = None

def _get_translator():
    global _fi_to_en
    if not _TRANSLATOR_AVAILABLE:
        logger.warning("deep-translator not installed, translation disabled.")
        return None
    
    if _fi_to_en is None:
        try:
            _fi_to_en = GoogleTranslator(source='fi', target='en')
            logger.info("Deep-translator (Google) model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize translator: {e}")
            return None
    
    return _fi_to_en

def _clean_for_translation(text: str) -> str:
    """Pre-process text for better translation results."""
    if not text:
        return ""
    # Remove excessive blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Ensure quotes are literal
    text = html.unescape(text)
    return text.strip()

def translate_fi_to_en(text: str) -> str:
    """
    Translates Finnish text to English using Google Translator.
    Handles texts larger than 4900 characters by chunking.
    Silently falls back to the original text if translation fails.
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
            translated = translator.translate(clean_text)
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
                        translated_pieces.append(translator.translate(current_chunk.strip()))
                    current_chunk = p + "\n\n"
                    
            if current_chunk.strip():
                # If a single paragraph is outrageously long, chunk it by rough length
                if len(current_chunk) >= limit:
                    logger.warning("Extremely long single paragraph encountered. Forcing manual split.")
                    parts = [current_chunk[i:i+limit] for i in range(0, len(current_chunk), limit)]
                    for part in parts:
                        translated_pieces.append(translator.translate(part.strip()))
                else:
                    translated_pieces.append(translator.translate(current_chunk.strip()))
                
            translated = "\n\n".join(translated_pieces)
            
        # Prevent completely corrupted returns
        if not translated or len(translated.strip()) == 0:
            return text
            
        return translated.strip()
    except Exception as e:
        logger.error(f"Translation failed: {e}")
        return text

