#!/usr/bin/env python3

"""
Test script to verify the core functionality works without hanging.
"""

import sys
import time
from suggest_skills import get_missing_skills
from ats_calculator import ATSCalculator
from restructure_advice import analyze_resume_structure

def test_suggest_skills():
    """Test the suggest_skills functionality."""
    print("Testing suggest_skills...")
    
    jd_text = """
    We are looking for a Python developer with experience in:
    - Machine Learning
    - Data Analysis
    - SQL databases
    - REST APIs
    - Docker containers
    """
    
    resume_text = """
    John Doe
    Software Engineer
    
    Experience:
    - Developed web applications using Python and Flask
    - Worked with PostgreSQL databases
    - Built REST APIs for mobile applications
    
    Skills:
    - Python programming
    - Web development
    - Database design
    """
    
    try:
        start_time = time.time()
        missing_skills = get_missing_skills(jd_text, resume_text)
        end_time = time.time()
        
        print(f"✓ suggest_skills completed in {end_time - start_time:.2f} seconds")
        print(f"  Found {len(missing_skills)} missing skills: {missing_skills[:5]}")
        return True
    except Exception as e:
        print(f"✗ suggest_skills failed: {str(e)}")
        return False

def test_ats_calculator():
    """Test the ATS calculator functionality."""
    print("Testing ATS calculator...")
    
    jd_text = """
    Software Engineer position requiring:
    - 3+ years Python experience
    - Machine learning knowledge
    - Database skills
    """
    
    resume_text = """
    John Doe
    john@email.com
    (555) 123-4567
    
    Experience:
    Software Engineer (2020-2023)
    - Developed Python applications
    - Worked with databases
    - Built machine learning models
    
    Skills:
    Python, SQL, Machine Learning
    """
    
    resume_structure = [
        {"type": "heading", "content": "John Doe", "font_size": 14},
        {"type": "text", "content": "john@email.com", "font_size": 11},
        {"type": "text", "content": "(555) 123-4567", "font_size": 11},
        {"type": "heading", "content": "Experience", "font_size": 12},
        {"type": "text", "content": "Software Engineer (2020-2023)", "font_size": 11},
        {"type": "bullet", "content": "Developed Python applications", "font_size": 11},
        {"type": "bullet", "content": "Worked with databases", "font_size": 11},
        {"type": "bullet", "content": "Built machine learning models", "font_size": 11},
        {"type": "heading", "content": "Skills", "font_size": 12},
        {"type": "text", "content": "Python, SQL, Machine Learning", "font_size": 11},
    ]
    
    try:
        start_time = time.time()
        ats = ATSCalculator(jd_text)
        score = ats.total_score(resume_text, resume_structure)
        end_time = time.time()
        
        print(f"✓ ATS calculator completed in {end_time - start_time:.2f} seconds")
        print(f"  ATS Score: {score}%")
        return True
    except Exception as e:
        print(f"✗ ATS calculator failed: {str(e)}")
        return False

def test_restructure_advice():
    """Test the restructure advice functionality."""
    print("Testing restructure advice...")
    
    resume_text = """
    John Doe
    john@email.com
    
    Experience:
    Software Engineer
    - Developed applications
    - Worked with databases
    
    Skills:
    Python, SQL
    """
    
    resume_structure = [
        {"type": "heading", "content": "John Doe", "font_size": 14},
        {"type": "text", "content": "john@email.com", "font_size": 11},
        {"type": "heading", "content": "Experience", "font_size": 12},
        {"type": "text", "content": "Software Engineer", "font_size": 11},
        {"type": "bullet", "content": "Developed applications", "font_size": 11},
        {"type": "bullet", "content": "Worked with databases", "font_size": 11},
        {"type": "heading", "content": "Skills", "font_size": 12},
        {"type": "text", "content": "Python, SQL", "font_size": 11},
    ]
    
    try:
        start_time = time.time()
        advice = analyze_resume_structure(resume_text, resume_structure)
        end_time = time.time()
        
        print(f"✓ Restructure advice completed in {end_time - start_time:.2f} seconds")
        print(f"  Found {len(advice)} recommendations")
        return True
    except Exception as e:
        print(f"✗ Restructure advice failed: {str(e)}")
        return False

def main():
    """Run all tests."""
    print("Starting functionality tests...\n")
    
    total_start = time.time()
    
    tests = [
        test_suggest_skills,
        test_ats_calculator,
        test_restructure_advice
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"✗ Test failed with exception: {str(e)}")
            results.append(False)
        print()
    
    total_end = time.time()
    
    print(f"All tests completed in {total_end - total_start:.2f} seconds")
    print(f"Results: {sum(results)}/{len(results)} tests passed")
    
    if all(results):
        print("✓ All functionality tests PASSED!")
        return 0
    else:
        print("✗ Some tests FAILED!")
        return 1

if __name__ == "__main__":
    sys.exit(main())


'''
import spacy
nlp = spacy.load("en_core_web_lg")
print("SpaCy model loaded successfully!")
'''