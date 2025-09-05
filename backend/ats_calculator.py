# ats_calculator.py
"""
Advanced, profession-agnostic ATS Scoring with SkillNER + TF-IDF + structural checks.

Key ideas:
- Content (60% total):
  - 0.25 = Skill coverage using SkillNER
  - 0.20 = TF-IDF cosine similarity between JD and resume
  - 0.15 = Keyword matching for important terms
- Formatting (40% total):
  - Sections present (skills/experience/education), bullet balance, readability, action verbs,


Profession-agnostic skill extraction:
- Extract skills using SkillNER
- Use TF-IDF for content relevance
- Keyword matching for important terms

Public API:
    calc = ATSCalculator(jd_text)
    final_score = calc.total_score(resume_text, resume_structure)
      - returns an integer 0–100

Requirements (add to requirements.txt):
    skill-ner>=1.1.0
    spacy>=3.5.0
    scikit-learn>=1.1.0
    en-core-web-lg (or sm) model installed for spaCy
"""

from __future__ import annotations
from typing import List, Dict, Tuple, Set, Any
import re

from collections import Counter

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import spacy
from spacy.matcher import PhraseMatcher
from skillNer.skill_extractor_class import SkillExtractor
from skillNer.general_params import SKILL_DB
from parser import _normalize

# Initialize spaCy model
try:
    nlp = spacy.load("en_core_web_lg")
except Exception:
    try:
        nlp = spacy.load("en_core_web_sm")
    except Exception:
        raise ImportError("spaCy model not found. Please install en_core_web_lg or en_core_web_sm")


# -----------------------
# Utility: phrase extraction
# -----------------------
def _strip_punct_ends(text: str) -> str:
    """Strip common punctuation at the ends to stabilize phrase matching."""
    return text.strip(".,;:()[]{}<>•-–—")


def extract_phrases(text: str) -> Set[str]:
    """
    Extract candidate 'skill-ish' phrases in a profession-agnostic way:
      - spaCy noun chunks (e.g., 'supply chain optimization', 'financial modeling')
      - 1–2 token n-grams as a fallback for short tool names (e.g., 'SQL', 'Tableau', 'AutoCAD')

    Returns a set of cleaned phrases.
    """
    text = _normalize(text)
    doc = nlp(text)
    phrases: Set[str] = set()

    # Noun chunks (helpful for multi-word skill phrases)
    for chunk in doc.noun_chunks:
        phrase = _strip_punct_ends(chunk.text.lower())
        if 1 <= len(phrase) <= 60 and any(ch.isalnum() for ch in phrase):
            phrases.add(phrase)

    # 1–2 token windows of non-space, non-punct tokens (to catch short skills/tools)
    toks = [t.text for t in doc if not (t.is_space or t.is_punct)]
    for i in range(len(toks)):
        one = _strip_punct_ends(toks[i].lower())
        if one and any(ch.isalnum() for ch in one) and len(one) <= 30:
            phrases.add(one)
        if i + 1 < len(toks):
            two = _strip_punct_ends((toks[i] + " " + toks[i + 1]).lower())
            if two and any(ch.isalnum() for ch in two) and len(two) <= 40:
                phrases.add(two)

    # De-duplicate & lightly filter empty leftovers
    phrases = {p for p in phrases if p}
    return phrases


# -----------------------
# Main calculator
# -----------------------
class ATSCalculator:
    """
    Final score is an integer 0–100 intended for the frontend.
    Internally, we keep details for logging or future explainability.
    """

    MIN_TEXT_LENGTH = 50  # sanity threshold for meaningful content

    # Scoring weights (sum to 1.0)
    SKILL_COVERAGE_WEIGHT = 0.25
    TFIDF_SIM_WEIGHT = 0.20
    KEYWORD_MATCH_WEIGHT = 0.15
    SECTIONS_WEIGHT = 0.20
    BULLETS_WEIGHT = 0.10
    READABILITY_VERBS_WEIGHT = 0.10

    # Important keywords that should be in a good resume
    IMPORTANT_KEYWORDS = {
        'experience', 'education', 'skills', 'projects', 'certifications',
        'leadership', 'achievements', 'technical', 'professional', 'summary'
    }

    def __init__(self, jd_text: str):
        ok, msg = self._validate_text(jd_text, "Job description")
        if not ok:
            raise ValueError(msg)

        self.jd_text_raw = jd_text
        self.jd_text = _normalize(jd_text)

        # Initialize SkillNER with error handling
        self.nlp = nlp  # Use shared spaCy instance
        try:
            # phrase_matcher = PhraseMatcher(self.nlp.vocab)
            self.skill_extractor = SkillExtractor(self.nlp, SKILL_DB, PhraseMatcher)
        except Exception as e:
            print(f"Warning: Could not initialize SkillExtractor in ATS Calculator: {e}")
            print("Using fallback skill extraction...")
            self.skill_extractor = None

        # Extract skills from JD
        self.jd_skills = self._extract_skills(self.jd_text)
        
        # Extract experience requirements once
        self.jd_required_years = self._extract_experience_requirements(self.jd_text)

        # For internal logging/explainability
        self.debug_details: Dict[str, Any] = {}

    # -----------------------
    # Public API
    # -----------------------
    def total_score(self, resume_text: str, resume_structure: List[Dict]) -> int:
        """
        Compute final ATS score 0–100.
        Only return the integer to keep frontend simple.
        """
        ok, msg = self._validate_text(resume_text, "Resume")
        if not ok:
            # Log internally and return 0 for invalid text
            self.debug_details["error"] = msg
            return 0

        if not isinstance(resume_structure, list) or not resume_structure:
            self.debug_details["error"] = "Invalid or empty resume structure"
            return 0

        # Check disqualifiers early
        disq_ok, disq_reason = self._check_disqualifiers(resume_structure)
        if not disq_ok:
            self.debug_details["disqualified"] = disq_reason
            return 0

        try:
            content_score = self._content_score(resume_text)
            formatting_score = self._formatting_score(resume_text, resume_structure)
            final = content_score + formatting_score
            final_pct = int(round(final * 100))
            self.debug_details["final_score"] = final_pct
            return final_pct
        except Exception as e:
            self.debug_details["error"] = f"ATS computation error: {e}"
            return 0

    # -----------------------
    # Content scoring (0.60)
    # -----------------------
    def _extract_skills(self, text: str) -> Set[str]:
        """Extract skills from text using SkillNER or fallback methods."""
        if not text or not text.strip():
            return set()

        skills = set()

        # Try SkillNER if available
        if self.skill_extractor is not None:
            try:
                annotations = self.skill_extractor.annotate(text)
                # Get full matches and high-confidence n-gram matches
                full_matches = {match['doc_node_value'].lower().strip()
                              for match in annotations['results']['full_matches']}
                ngram_matches = {match['doc_node_value'].lower().strip()
                               for match in annotations['results']['ngram_scored']
                               if match.get('score', 0) > 0.7}
                skills.update(full_matches.union(ngram_matches))
            except Exception as e:
                print(f"Skill extraction error: {e}")
                self.skill_extractor = None  # Disable for future calls

        # Fallback to basic pattern matching if SkillNER is not available
        if self.skill_extractor is None:
            # Use basic keyword matching
            text_lower = text.lower()
            common_skills = {
                'python', 'java', 'javascript', 'sql', 'html', 'css', 'react', 'angular',
                'machine learning', 'data analysis', 'docker', 'kubernetes', 'aws', 'azure'
            }
            for skill in common_skills:
                if skill in text_lower:
                    skills.add(skill)

        return skills

    def _content_score(self, resume_text: str) -> float:
        """Combine skill coverage, TF-IDF similarity, and keyword matching."""
        resume_norm = _normalize(resume_text)
        resume_skills = self._extract_skills(resume_norm)
        
        # 1) Skill coverage (0.25)
        skill_coverage = 0.0
        if self.jd_skills:
            matched_skills = self.jd_skills.intersection(resume_skills)
            skill_coverage = len(matched_skills) / len(self.jd_skills)
        
        skill_component = self.SKILL_COVERAGE_WEIGHT * skill_coverage
        
        # 2) TF-IDF similarity (0.20)
        tfidf_component = 0.0
        try:
            vec = TfidfVectorizer(ngram_range=(1, 2), stop_words="english", 
                                min_df=1, max_df=0.9)
            tfidf = vec.fit_transform([self.jd_text, resume_norm])
            sim = cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0]
            tfidf_component = self.TFIDF_SIM_WEIGHT * float(sim)
        except Exception as e:
            print(f"TF-IDF error: {e}")
            
        # 3) Keyword matching (0.15)
        keyword_component = 0.0
        try:
            doc = self.nlp(resume_norm.lower())
            present_keywords = [kw for kw in self.IMPORTANT_KEYWORDS 
                              if kw in doc.text]
            keyword_score = len(present_keywords) / len(self.IMPORTANT_KEYWORDS)
            keyword_component = self.KEYWORD_MATCH_WEIGHT * keyword_score
        except Exception as e:
            print(f"Keyword matching error: {e}")
            
        # Experience bonus (small)
        exp_bonus = self._experience_bonus(resume_norm)
        
        total_content = (skill_component + tfidf_component + 
                        keyword_component + exp_bonus)
        return max(0.0, min(0.60, total_content))

    # -----------------------
    # Formatting scoring (0.40)
    # -----------------------
    def _formatting_score(self, resume_text: str, resume_structure: List[Dict]) -> float:
        score = 0.0
        details: Dict = {}

        # 1) Sections presence (0.20): skills/experience/education
        required = {"skills", "experience", "education"}
        headings = [it.get("content", "").lower() for it in resume_structure if it.get("type") == "heading"]
        present = {h for h in headings if h in required}
        sections_component = self.SECTIONS_WEIGHT * (len(present) / len(required))
        score += sections_component
        details["sections_found"] = list(present)

        # 2) Bullet balance (0.10): reward 2–4 bullets per major section, mild penalty beyond
        bullets_by_section = Counter()
        current = None
        for it in resume_structure:
            if it.get("type") == "heading":
                h = it.get("content", "").lower()
                current = h if h in {"experience", "projects", "project", "education"} else None
                if current and current not in bullets_by_section:
                    bullets_by_section[current] = 0
            elif it.get("type") == "bullet" and current:
                bullets_by_section[current] += 1

        bullet_component = 0.0
        for _, cnt in bullets_by_section.items():
            if cnt >= 2:
                bullet_component += (self.BULLETS_WEIGHT / 4.0)  # distribute small rewards
            if cnt > 4:
                bullet_component -= (self.BULLETS_WEIGHT / 10.0)  # light penalty
        # Clamp within [0, BULLETS_WEIGHT]
        bullet_component = max(0.0, min(self.BULLETS_WEIGHT, bullet_component))
        score += bullet_component
        details["bullets_by_section"] = dict(bullets_by_section)

        # 3) Readability & action verbs (0.10)
        read_component = 0.0
        doc = nlp(resume_text)
        sents = [s for s in doc.sents]
        if sents:
            avg_len = sum(len([t for t in s if not (t.is_punct or t.is_space)]) for s in sents) / len(sents)
        else:
            avg_len = 0.0

        # Reward moderate sentences
        if 10 <= avg_len <= 30:
            read_component += self.READABILITY_VERBS_WEIGHT * 0.5  # 50% of this bucket

        # Action verbs: bullets that start with a verb
        verb_starts = 0
        for it in resume_structure:
            if it.get("type") == "bullet":
                bdoc = nlp(it.get("content", ""))
                first = next((t for t in bdoc if not (t.is_punct or t.is_space)), None)
                if first is not None and first.pos_ == "VERB":
                    verb_starts += 1
        if verb_starts >= 3:
            read_component += self.READABILITY_VERBS_WEIGHT * 0.5  # remaining 50%

        # Clamp within [0, READABILITY_VERBS_WEIGHT]
        read_component = max(0.0, min(self.READABILITY_VERBS_WEIGHT, read_component))
        score += read_component

        # Final clamp within 0–0.40 just in case
        return max(0.0, min(0.40, score))

    # -----------------------
    # Disqualifiers (hard fails)
    # -----------------------
    def _check_disqualifiers(self, resume_structure: List[Dict]) -> Tuple[bool, str]:
        """
        Hard rejections similar to ATS rules:
          - Tables/images present
          - No minimal contact info

        """
        # tables or images
        if any(it.get("type") in {"table", "image"} for it in resume_structure):
            return False, "Resume contains tables or images (not ATS-friendly)"

        # basic contact info check
        email_regex = r'\b[A-Za-z0-9._%+-]+@[\w.-]+\.[A-Za-z]{2,}\b'
        phone_regex = r'(\+\d{1,3}[-.\s]?)?\(?\d{1,5}\)?[-.\s]?\d{3}[-.\s]?\d{3,5}'  # Updated for broader formats
        linkedin_regex = r'linkedin\.com/in/[\w-]+'
        github_regex = r'github\.com/[\w-]+'

        has_name = False
        has_email = False
        has_phone_or_profile = False

        # Debug: Log all headings for inspection
        headings = [it.get("content", "").strip() for it in resume_structure if it.get("type") == "heading"]
        print("All headings:", headings)

        for it in resume_structure:
            content = (it.get("content") or "").strip()
            if it.get("type") == "heading" and content:
                # Relaxed name detection: Any first heading with 1-5 words, at least one capitalized
                parts = content.split()
                if 1 <= len(parts) <= 5 and any(p[0].isupper() for p in parts if p):
                    has_name = True
            low = content.lower()
            if re.search(email_regex, content):
                has_email = True
            if re.search(phone_regex, content) or re.search(linkedin_regex, low) or re.search(github_regex, low):
                has_phone_or_profile = True

        # Debug prints for troubleshooting (remove after testing)
        print("Has name:", has_name)
        print("Has email:", has_email)
        print("Has phone/profile:", has_phone_or_profile)

        # Less strict: Require name + (email OR phone/profile)
        if not (has_name and (has_email or has_phone_or_profile)):
            return False, "Missing minimal contact information (name + email + phone or profile)"

        return True, ""

    # -----------------------
    # Experience extraction / bonus
    # -----------------------
    def _extract_experience_requirements(self, text: str) -> int:
        """
        Extract a coarse 'required years' figure from the JD.
        Examples matched:
            "3+ years of experience", "at least 5 yrs", "2 years experience"
        Returns the maximum required years found, else 0.
        """
        text = _normalize(text)
        matches = re.findall(r"(\d+)\s*\+?\s*(?:years|yrs)\s+(?:of\s+)?experience", text)
        nums = [int(m) for m in matches if m.isdigit()]
        return max(nums) if nums else 0

    def _estimate_years_from_resume(self, text: str) -> int:
        """
        Very rough estimation: detect years like 2016, 2020, etc., and compute span.
        If at least two distinct years are present, span = max - min (bounded 0..40).
        """
        years = re.findall(r"(20\d{2}|19\d{2})", text)
        yrs = sorted({int(y) for y in years})
        if len(yrs) >= 2:
            span = max(yrs) - min(yrs)
            return max(0, min(40, span))
        return 0

    def _experience_bonus(self, resume_text: str) -> float:
        """
        Small bonus (up to 0.02 within content) if resume meets or exceeds JD requirement.
        """
        if self.jd_required_years <= 0:
            return 0.0

        resume_years = self._estimate_years_from_resume(resume_text)
        if resume_years >= self.jd_required_years:
            return 0.02  # small bonus for meeting experience
        return 0.0

    # -----------------------
    # Validation helpers
    # -----------------------
    def _validate_text(self, text: str, name: str) -> Tuple[bool, str]:
        if not isinstance(text, str) or not text.strip():
            return False, f"{name} is empty or not a string"
        if len(text.strip()) < self.MIN_TEXT_LENGTH:
            return False, f"{name} is too short (min {self.MIN_TEXT_LENGTH} chars)"
        ratio = sum(c.isalnum() or c.isspace() for c in text) / max(1, len(text))
        if ratio < 0.5:
            return False, f"{name} contains too many non-text characters"
        return True, ""
