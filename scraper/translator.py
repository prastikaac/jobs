"""
Wrapper for ArgosTranslate FI->EN translation.
Loads models efficiently and exposes robust translation methods.
"""
import logging
import re
import html
try:
    import argostranslate.translate
    _ARGOS_AVAILABLE = True
except ImportError:
    _ARGOS_AVAILABLE = False

logger = logging.getLogger("translator")

_fi_to_en = None

def _get_translator():
    global _fi_to_en
    if not _ARGOS_AVAILABLE:
        logger.warning("argostranslate not installed, translation disabled.")
        return None
    
    if _fi_to_en is None:
        try:
            installed = argostranslate.translate.get_installed_languages()
            fi_lang = next((lang for lang in installed if lang.code == "fi"), None)
            en_lang = next((lang for lang in installed if lang.code == "en"), None)
            
            if not fi_lang or not en_lang:
                logger.error("fi -> en language packages not installed in ArgosTranslate.")
                return None
            
            _fi_to_en = fi_lang.get_translation(en_lang)
            logger.info("FI->EN translation model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load translation model: {e}")
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
    Translates Finnish text to English using ArgosTranslate.
    Silently falls back to the original text if translation fails or model is missing.
    """
    if not text or len(text.strip()) < 2:
        return text

    translator = _get_translator()
    if not translator:
        return text
    
    try:
        clean_text = _clean_for_translation(text)
        translated = translator.translate(clean_text)
        # Prevent completely corrupted returns
        if not translated or len(translated.strip()) == 0:
            return text
        return translated.strip()
    except Exception as e:
        logger.error(f"Translation failed: {e}")
        return text

