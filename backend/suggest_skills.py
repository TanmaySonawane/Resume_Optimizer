import re
import spacy
from spacy.matcher import PhraseMatcher
from skillNer.skill_extractor_class import SkillExtractor
from skillNer.general_params import SKILL_DB
from typing import List, Set

# Initialize spaCy model
try:
    nlp = spacy.load("en_core_web_lg")
except OSError:
    try:
        nlp = spacy.load("en_core_web_sm")
    except OSError:
        raise ImportError("spaCy model not found. Please install en_core_web_lg or en_core_web_sm")

# Initialize SkillExtractor globally with error handling
try:
    # phrase_matcher = PhraseMatcher(nlp.vocab)
    skill_extractor = SkillExtractor(nlp, SKILL_DB, PhraseMatcher)
except Exception as e:
    print(f"Warning: Could not initialize SkillExtractor: {e}")
    print("Falling back to basic skill extraction...")
    skill_extractor = None

# Common technical skills and keywords for pattern matching
COMMON_SKILLS = {
    # Programming Languages
    'python', 'java', 'javascript', 'typescript', 'c++', 'c#', 'c', 'ruby', 'php', 'swift', 'kotlin',
    'go', 'rust', 'scala', 'r', 'matlab', 'perl', 'shell', 'bash', 'powershell',

    # Web Technologies
    'html', 'css', 'react', 'angular', 'vue', 'node.js', 'express', 'django', 'flask', 'spring',
    'laravel', 'ruby on rails', 'asp.net', '.net', 'jquery', 'bootstrap', 'sass', 'less',

    # Databases
    'sql', 'mysql', 'postgresql', 'mongodb', 'redis', 'elasticsearch', 'oracle', 'sqlite',
    'nosql', 'cassandra', 'dynamodb', 'firebase',

    # Cloud & DevOps
    'aws', 'azure', 'gcp', 'docker', 'kubernetes', 'jenkins', 'git', 'github', 'gitlab',
    'terraform', 'ansible', 'chef', 'puppet', 'vagrant', 'linux', 'unix', 'windows',

    # Data Science & ML
    'machine learning', 'deep learning', 'tensorflow', 'pytorch', 'keras', 'scikit-learn',
    'pandas', 'numpy', 'matplotlib', 'seaborn', 'jupyter', 'tableau', 'power bi',
    'data analysis', 'data science', 'statistics', 'excel',

    # Mobile Development
    'ios', 'android', 'react native', 'flutter', 'xamarin', 'cordova', 'ionic',

    # Other Technologies
    'api', 'rest', 'graphql', 'microservices', 'agile', 'scrum', 'kanban', 'jira',
    'confluence', 'slack', 'teams', 'zoom'
}

def clean_phrase(text: str) -> str:
    """Clean and normalize text."""
    return re.sub(r'[^\w\s]', ' ', text.lower()).strip()

def extract_skills(text: str) -> Set[str]:
    """
    Extract skills from text using SkillNER and pattern matching.
    Returns a set of cleaned and normalized skill names.
    """
    global skill_extractor

    if not text or not isinstance(text, str):
        return set()

    skills = set()

    # Extract skills using SkillNER if available
    if not text.strip():
        return skills

    if skill_extractor is not None:
        try:
            annotations = skill_extractor.annotate(text)
            # Get full matches
            full_matches = set()
            for match in annotations['results']['full_matches']:
                skill = clean_phrase(match['doc_node_value'])
                if skill and len(skill) <= 100:  # Sanity check for skill length
                    full_matches.add(skill)

            # Get n-gram matches with confidence > 0.7
            ngram_matches = set()
            for match in annotations['results']['ngram_scored']:
                if match.get('score', 0) > 0.7:
                    skill = clean_phrase(match['doc_node_value'])
                    if skill and len(skill) <= 100:  # Sanity check
                        ngram_matches.add(skill)

            skills.update(full_matches.union(ngram_matches))
        except Exception as e:
            print(f"SkillNER extraction error: {e}")
            skill_extractor = None  # Disable for future calls

    # Fallback to pattern matching and common skills if SkillNER is not available
    if skill_extractor is None:
        # Use spaCy NER for basic skill detection
        try:
            doc = nlp(text)
            for ent in doc.ents:
                if ent.label_ in ['PERSON', 'ORG', 'PRODUCT']:  # These might be skills/technologies
                    skill = clean_phrase(ent.text)
                    if skill and len(skill) <= 100 and skill.lower() in COMMON_SKILLS:
                        skills.add(skill.lower())
        except Exception as e:
            print(f"spaCy NER error: {e}")

        # Check against common skills list
        text_lower = text.lower()
        for skill in COMMON_SKILLS:
            if skill in text_lower:
                skills.add(skill)
    
    # Also look for common skill patterns
    skill_patterns = [
        r'\b(?:proficient in|experience with|skilled in|expertise in|knowledge of|familiar with)[\s:]+([\w\s/&+.\-/]+)(?:\.|,|;|$)',
        r'\b(?:technologies?|skills?|tools?)[\s:]+([\w\s/&+.\-/]+)(?:\.|,|;|$)',
    ]
    
    for pattern in skill_patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            skills.update(clean_phrase(s) for s in re.split(r'[,/&+]', match.group(1)) if s.strip())
    
    return skills

def extract_phrases(text: str) -> Set[str]:
    """
    Extract potential skill phrases using spaCy's noun chunks and named entities.
    Returns a set of cleaned phrases.
    """
    if not text or not text.strip():
        return set()
    
    doc = nlp(text)
    phrases = set()
    
    # Add noun chunks (e.g., 'machine learning', 'data analysis')
    for chunk in doc.noun_chunks:
        if len(chunk.text.split()) <= 3:  # Limit phrase length
            phrase = clean_phrase(chunk.text)
            if phrase and len(phrase) > 2:  # Filter out very short phrases
                phrases.add(phrase)
    
    # Add named entities that could be skills (e.g., 'Python', 'JavaScript')
    for ent in doc.ents:
        if ent.label_ in ['PRODUCT', 'ORG', 'LANGUAGE', 'TECH']:
            phrase = clean_phrase(ent.text)
            if phrase and len(phrase) >= 2 and len(phrase.split()) <= 3:
                phrases.add(phrase)
    
    return phrases

def get_missing_skills(jd_text: str, resume_text: str) -> List[str]:
    """
    Find skills in job description that are missing from the resume using SkillNER.
    Returns a list of missing skills as strings, sorted by importance.
    """
    if not jd_text or not resume_text:
        return []

    try:
        jd_skills = extract_skills(jd_text)
        resume_skills = extract_skills(resume_text)

        # Find skills in JD that aren't in resume
        missing_skills = jd_skills - resume_skills

        # Filter to only skills in COMMON_SKILLS
        filtered_missing = [
            skill for skill in missing_skills 
            if skill.lower() in COMMON_SKILLS and len(skill) > 2  # Only COMMON_SKILLS, skip short ones
        ]

        # Create result with skill details for sorting
        skill_details = []
        for skill in filtered_missing:
            # Count occurrences in JD as a simple importance metric
            importance = jd_text.lower().count(skill.lower())
            skill_details.append({
                'skill': skill,
                'importance': importance
            })

        # Sort by importance (descending), then alphabetically
        sorted_skills = sorted(
            skill_details,
            key=lambda x: (-x['importance'], x['skill'].lower())
        )

        # Return just the skill names as strings
        return [item['skill'] for item in sorted_skills[:20]]  # Limit to top 20

    except Exception as e:
        print(f"Error in get_missing_skills: {str(e)}")
        return []
