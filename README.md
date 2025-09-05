# Resume Optimizer ATS

An open-source tool that parses resumes and job descriptions, extracts skills using NLP, and calculates ATS match scores.  
Provides actionable feedback for improving resume alignment with job postings.

## Features
- Resume and Job Description parsing (PDF, DOCX)
- Skill extraction with spaCy + SkillNer
- ATS scoring with TF-IDF and cosine similarity
- Recommendations for missing skills and structure improvements
- FastAPI backend + React frontend

## Installation

```bash
git clone https://github.com/<your-username>/resume-optimizer.git
cd resume-optimizer
python -m venv .venv
. .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m spacy download en_core_web_lg
