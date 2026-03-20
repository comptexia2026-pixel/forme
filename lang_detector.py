# modules/lang_detector.py
#
# Detects document language (EN, FR, DE).
# Primary method: langid library (statistical classifier).
# Fallback: keyword frequency (if langid is not installed).
#
# Install langid: pip install langid

import logging

import config

logger = logging.getLogger(__name__)

# Try to load langid at import time. If not installed, we fall back gracefully.
try:
    import langid
    langid.set_languages(["en", "fr", "de"])
    _LANGID_AVAILABLE = True
    logger.info("langid loaded -- using statistical language detection")
except ImportError:
    _LANGID_AVAILABLE = False
    logger.info("langid not installed -- falling back to keyword detection")

# Map langid codes to our internal codes
_LANGID_TO_CODE = {"en": "EN", "fr": "FR", "de": "DE"}


def detect_language(text: str) -> str:
    """
    Return 'EN', 'FR', or 'DE'.
    Uses langid if available, otherwise falls back to keyword counting.
    """
    if not text or len(text) < 50:
        return "EN"

    # -- Primary: langid --
    if _LANGID_AVAILABLE:
        try:
            lang_code, confidence = langid.classify(text[:8000])
            result = _LANGID_TO_CODE.get(lang_code, None)
            if result:
                logger.info(f"Language detected (langid): {result} (raw={lang_code}, conf={confidence:.2f})")
                return result
        except Exception as e:
            logger.warning(f"langid failed: {e}, falling back to keywords")

    # -- Fallback: keyword frequency --
    return _detect_by_keywords(text)


def _detect_by_keywords(text: str) -> str:
    """Count language-specific keywords to determine language."""
    text_lower = text.lower()
    scores = {}
    for lang, keywords in config.LANG_KEYWORDS.items():
        scores[lang] = sum(1 for kw in keywords if kw.lower() in text_lower)

    best_lang = max(scores, key=scores.get)
    best_score = scores[best_lang]

    if best_score == 0:
        logger.warning("No language keywords matched, defaulting to EN")
        return "EN"

    logger.info(f"Language detected (keywords): {best_lang} (scores: {scores})")
    return best_lang
