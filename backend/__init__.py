"""
Backend package for Resume Optimizer ATS system.
Initializes the SkillNER extractor and other shared resources.
"""
from __future__ import annotations

import spacy
from spacy.matcher import PhraseMatcher

# SkillNer is optional at runtime; if it fails to import/init, we fall back gracefully.
try:
    from skillNer.skill_extractor_class import SkillExtractor
    from skillNer.general_params import SKILL_DB
except Exception:
    SkillExtractor = None  # type: ignore
    SKILL_DB = None  # type: ignore

nlp = None
skill_extractor = None  # will cache the initialized SkillExtractor or remain None


def load_spacy_model():
    """Load and cache a spaCy model (prefer large, fall back to small)."""
    global nlp
    if nlp is not None:
        return nlp
    for model_name in ("en_core_web_lg", "en_core_web_sm"):
        try:
            nlp = spacy.load(model_name)
            return nlp
        except Exception:
            continue
    raise ImportError(
        "spaCy model not found. Install 'en_core_web_lg' (preferred) or 'en_core_web_sm'."
    )


def get_skill_extractor():
    """
    Get (and lazily initialize) the shared SkillNER extractor instance.
    Returns None if SkillNer isn't available or initialization fails.
    """
    global skill_extractor
    if skill_extractor is not None:
        return skill_extractor

    _nlp = load_spacy_model()

    if SkillExtractor is None or SKILL_DB is None:
        # SkillNer isn't installed/available
        return None

    try:
        # phrase_matcher = PhraseMatcher(_nlp.vocab)
        skill_extractor = SkillExtractor(_nlp, SKILL_DB, PhraseMatcher)
    except Exception as e:
        print(f"Warning: Could not initialize SkillExtractor: {e}")
        skill_extractor = None

    return skill_extractor


__all__ = ["get_skill_extractor", "load_spacy_model", "nlp", "SKILL_DB"]
