"""
restructure_advice.py
-----------------------
Analyzes resume structure for ATS compatibility issues and provides specific,
actionable advice for improvement.

This module performs structural analysis of resumes to identify potential issues
that could affect parsing by Applicant Tracking Systems (ATS). It provides
specific, actionable advice for improving resume structure and content.

Usage:
    >>> from restructure_advice import analyze_resume_structure
    >>> issues = analyze_resume_structure(resume_text, resume_structure)
"""

import re
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass

# Pre-compile regex patterns for better performance
EMAIL_REGEX = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', re.IGNORECASE)
PHONE_REGEX = re.compile(r'(\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}')
LINKEDIN_REGEX = re.compile(r'linkedin\.com/in/[\w-]+')
GITHUB_REGEX = re.compile(r'github\.com/[\w-]+')

# Constants
MIN_FONT_SIZE = 9  # Minimum recommended font size
MAX_WORD_COUNT = 800  # Maximum recommended word count
MIN_WORD_COUNT = 200  # Minimum recommended word count
MAX_BULLETS_PER_SECTION = 5  # Maximum recommended bullet points per section

@dataclass
class ContactInfo:
    """Stores contact information validation results."""
    name: bool = False
    email: bool = False
    phone: bool = False
    profile: bool = False

def check_contact_info(resume_text: str) -> Tuple[bool, ContactInfo, List[Dict[str, str]]]:
    """Check for presence and validity of contact information.
    
    Args:
        resume_text: The full text content of the resume.
        
    Returns:
        Tuple containing:
            - bool: Whether minimum contact info is present (name + email/phone)
            - ContactInfo: Object with contact info validation results
            - List[Dict]: List of issues found with corresponding advice
    """
    if not isinstance(resume_text, str) or not resume_text.strip():
        raise ValueError("resume_text must be a non-empty string")
        
    issues = []
    contact_info = ContactInfo()
    
    try:
        # Check for name (usually at the top of the resume)
        first_100_chars = resume_text[:100].strip()
        name_parts = first_100_chars.split('\n')[0].strip().split()
        if 2 <= len(name_parts) <= 4 and all(part and part[0].isupper() for part in name_parts):
            contact_info.name = True
        
        # Check for email using pre-compiled regex
        contact_info.email = bool(EMAIL_REGEX.search(resume_text))
        
        # Check for phone number using pre-compiled regex
        contact_info.phone = bool(PHONE_REGEX.search(resume_text))
        
        # Check for online profiles using pre-compiled regex
        contact_info.profile = bool(
            LINKEDIN_REGEX.search(resume_text) or 
            GITHUB_REGEX.search(resume_text)
        )
    
        # Generate specific advice for missing contact info
        if not contact_info.name:
            issues.append({
                'issue': 'Missing or unclear name at the top of the resume',
                'advice': 'Add your full name prominently at the top of your resume.'
            })
            
        if not contact_info.email and not contact_info.phone:
            issues.append({
                'issue': 'Missing both email and phone number',
                'advice': 'Include at least one reliable contact method (email or phone).'
            })
            
        if not contact_info.profile:
            issues.append({
                'issue': 'No professional profile links',
                'advice': 'Consider adding your LinkedIn profile or personal website.'
            })
        
        has_min_contact = contact_info.name and (contact_info.email or contact_info.phone)
        return has_min_contact, contact_info, issues
        
    except Exception as e:
        # Log the error and return a generic error message
        print(f"Error in check_contact_info: {str(e)}")
        return False, ContactInfo(), [{
            'issue': 'Error processing contact information',
            'advice': 'Could not verify contact information. Please check the format.'
        }]

def check_sections(resume_text: str, resume_structure: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Check for missing or poorly structured sections in the resume.

    Args:
        resume_text: The full text content of the resume.
        resume_structure: List containing parsed resume structure elements.

    Returns:
        List of dictionaries, each containing 'issue' and 'advice' keys.
    """
    if not isinstance(resume_text, str) or not resume_text.strip():
        raise ValueError("resume_text must be a non-empty string")
    if not isinstance(resume_structure, list):
        raise ValueError("resume_structure must be a list")
        
    issues = []
    required_sections = [
        ('experience', 'work experience', 'employment history'),
        ('education', 'academic background'),
        ('skills', 'technical skills', 'key skills')
    ]
    
    try:
        # Pre-compile section patterns for better performance
        section_patterns = {
            section_group[0]: [
                re.compile(rf'{re.escape(variant)}', re.IGNORECASE) 
                for variant in section_group
            ]
            for section_group in required_sections
        }
        
        found_sections = {}
        for section_name, patterns in section_patterns.items():
            found = any(
                pattern.search(resume_text) 
                for pattern in patterns
            )
            if not found:
                display_name = section_name.title()
                issues.append({
                    'issue': f'Missing "{display_name}" section',
                    'advice': f'Add a clearly labeled "{display_name}" section.'
                })
        
        # Check section order (basic check: name should be first, contact info near top)
        # Extract headings from the structure list
        headings = [
            item['content'].lower().strip()
            for item in resume_structure
            if item.get('type') == 'heading' and item.get('content')
        ]

        if headings:
            # Check if first heading looks like a name (simple heuristic)
            first_heading = headings[0]
            name_parts = first_heading.split()
            if not (2 <= len(name_parts) <= 4 and all(part[0].isupper() for part in name_parts if part)):
                issues.append({
                    'issue': 'Name/contact information not at the top',
                    'advice': 'Place your name and contact information at the top of the first page.'
                })
        
        return issues
        
    except Exception as e:
        print(f"Error in check_sections: {str(e)}")
        return [{
            'issue': 'Error analyzing resume sections',
            'advice': 'Could not analyze section structure. Please check the format.'
        }]

def check_formatting(resume_structure: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Check formatting issues like fonts, spacing, and structure.

    Args:
        resume_structure: List containing parsed resume structure elements.

    Returns:
        List of dictionaries, each containing 'issue' and 'advice' keys.
    """
    if not isinstance(resume_structure, list):
        raise ValueError("resume_structure must be a list")
        
    issues = []
    
    try:
        # Extract font sizes from structure list
        font_sizes = [
            float(item.get('font_size', 11))
            for item in resume_structure
            if 'font_size' in item and isinstance(item.get('font_size'), (int, float))
        ]

        if font_sizes:  # Only process if we have valid font sizes
            min_size = min(font_sizes)
            max_size = max(font_sizes)

            if min_size < MIN_FONT_SIZE:
                issues.append({
                    'issue': f'Font size too small ({min_size:.1f}pt)',
                    'advice': f'Increase all text to at least {MIN_FONT_SIZE + 1}pt for better readability.'
                })

            # Check for excessive font size variation
            if max_size - min_size > 6:  # More than 6pt variation
                issues.append({
                    'issue': 'Inconsistent font sizes',
                    'advice': 'Limit font size variations to 2-3 sizes for better visual hierarchy.'
                })

        # Check for tables
        table_count = sum(1 for item in resume_structure if item.get('type') == 'table')
        if table_count > 0:
            issues.append({
                'issue': 'Uses tables or columns',
                'advice': 'Avoid tables and columns as they may cause parsing issues with ATS.'
            })

        # Check for images/graphics
        image_count = sum(1 for item in resume_structure if item.get('type') == 'image')
        if image_count > 0:
            issues.append({
                'issue': 'Contains images or graphics',
                'advice': 'Remove images, icons, and graphics as they are not ATS-friendly.'
            })
        
        return issues
        
    except Exception as e:
        print(f"Error in check_formatting: {str(e)}")
        return [{
            'issue': 'Error analyzing resume formatting',
            'advice': 'Could not analyze document formatting. Please check the file.'
        }]

def check_content_quality(resume_text: str, resume_structure: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """Check content quality issues like bullet points, action verbs, and length.

    Args:
        resume_text: The full text content of the resume.
        resume_structure: List containing parsed resume structure elements.

    Returns:
        List of dictionaries, each containing 'issue' and 'advice' keys.
    """
    if not isinstance(resume_text, str) or not resume_text.strip():
        raise ValueError("resume_text must be a non-empty string")
    if not isinstance(resume_structure, list):
        raise ValueError("resume_structure must be a list")
        
    issues = []
    
    try:
        # Check bullet point usage by analyzing structure list
        # Group bullets by section
        current_section = None
        section_bullets = {}

        for item in resume_structure:
            if item.get('type') == 'heading':
                heading = item.get('content', '').lower().strip()
                if any(exp in heading for exp in ['experience', 'work experience', 'projects', 'education']):
                    current_section = heading
                    section_bullets[current_section] = 0
                else:
                    current_section = None
            elif item.get('type') == 'bullet' and current_section:
                section_bullets[current_section] += 1

        # Check bullet counts per section
        for section_name, bullet_count in section_bullets.items():
            # Check for missing bullet points in experience sections
            if bullet_count == 0 and any(exp in section_name for exp in ['experience', 'work experience']):
                issues.append({
                    'issue': f'No bullet points in "{section_name}" section',
                    'advice': 'Use 3-5 bullet points per position to highlight achievements.'
                })
            # Check for excessive bullet points
            elif bullet_count > MAX_BULLETS_PER_SECTION:
                issues.append({
                    'issue': f'Too many bullet points ({bullet_count}) in "{section_name}"',
                    'advice': f'Limit to {MAX_BULLETS_PER_SECTION} bullet points per position for better readability.'
                })
        
        # Check for action verbs using pre-compiled patterns
        # Expand the action_verbs list (original has 12; add more for coverage):
        action_verbs = [
            'achieved', 'managed', 'increased', 'developed', 'led', 'implemented',
            'created', 'improved', 'reduced', 'designed', 'launched', 'spearheaded',
            'built', 'optimized', 'analyzed', 'collaborated', 'mentored', 'taught',  # Add these
            'coordinated', 'executed', 'facilitated', 'generated', 'resolved'  # More common ones
        ]

        # Update the pattern to match word boundaries but allow suffixes (e.g., 'developing'):
        action_verb_pattern = re.compile(
            r'\b(' + '|'.join(map(re.escape, action_verbs)) + r')\w*\b',  # Add \w* for variations like 'developed' or 'developing'
            re.IGNORECASE
        )
        
        if not action_verb_pattern.search(resume_text):
            issues.append({
                'issue': 'Weak action verbs',
                'advice': 'Start bullet points with strong action verbs (e.g., "Led", "Developed", "Increased").'
            })
        
        # Check resume length

        
        return issues
        
    except Exception as e:
        print(f"Error in check_content_quality: {str(e)}")
        return [{
            'issue': 'Error analyzing content quality',
            'advice': 'Could not analyze resume content. Please check the format.'
        }]

def analyze_resume_structure(resume_text: str, resume_structure: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Comprehensive analysis of resume structure and content for ATS optimization.

    Args:
        resume_text (str): Full text content of the resume
        resume_structure (List[Dict[str, Any]]): Parsed resume structure from parser.py

    Returns:
        list: List of dictionaries, each containing 'issue' and 'advice' keys
    """
    if not resume_text or not isinstance(resume_text, str):
        return [{
            'issue': 'Invalid resume text',
            'advice': 'Provide valid resume text for analysis.'
        }]

    if not resume_structure or not isinstance(resume_structure, list):
        resume_structure = []
    
    # Initialize list to collect all issues
    all_issues = []
    
    # Run all checks
    _, _, contact_issues = check_contact_info(resume_text)
    section_issues = check_sections(resume_text, resume_structure)
    formatting_issues = check_formatting(resume_structure)
    content_issues = check_content_quality(resume_text, resume_structure)
    
    # Combine all issues
    all_issues.extend(contact_issues)
    all_issues.extend(section_issues)
    all_issues.extend(formatting_issues)
    all_issues.extend(content_issues)
    
    # If no issues found, return a positive message
    if not all_issues:
        return [{
            'issue': 'No major issues detected',
            'advice': 'Your resume appears to be well-structured for ATS. Consider having it reviewed by a professional for further optimization.'
        }]
    
    return all_issues