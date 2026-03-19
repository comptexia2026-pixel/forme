# modules/lang_detector.py
#
# Detects document language (EN, FR, DE) using keyword frequency.
# No external dependency -- just counts how many language-specific
# keywords appear in the text.

import logging

import config

logger = logging.getLogger(__name__)


def detect_language(text: str) -> str:
    """
    Return 'EN', 'FR', or 'DE' based on keyword frequency in the text.
    Falls back to 'EN' if nothing is detected.
    """
    if not text or len(text) < 50:
        return "EN"

    scores = {}
    for lang, keywords in config.LANG_KEYWORDS.items():
        count = 0
        for kw in keywords:
            if kw.lower() in text.lower():
                count += 1
        scores[lang] = count

    best_lang = max(scores, key=scores.get)
    best_score = scores[best_lang]

    if best_score == 0:
        logger.warning("No language keywords matched, defaulting to EN")
        return "EN"

    logger.info(f"Language detected: {best_lang} (scores: {scores})")
    return best_lang
