FORCED_ALIGNMENT_LANGUAGES = {
    "chinese": "Chinese",
    "zh": "Chinese",
    "english": "English",
    "en": "English",
    "cantonese": "Cantonese",
    "yue": "Cantonese",
    "french": "French",
    "fr": "French",
    "german": "German",
    "de": "German",
    "italian": "Italian",
    "it": "Italian",
    "japanese": "Japanese",
    "ja": "Japanese",
    "korean": "Korean",
    "ko": "Korean",
    "portuguese": "Portuguese",
    "pt": "Portuguese",
    "russian": "Russian",
    "ru": "Russian",
    "spanish": "Spanish",
    "es": "Spanish",
}


def normalize_forced_alignment_language(language):
    """Return the canonical ForcedAligner name, or None when unsupported."""
    if language is None:
        return None

    return FORCED_ALIGNMENT_LANGUAGES.get(str(language).strip().casefold())
