"""
parser.py
Handles:
1. Extracting job descriptions (JD) from text or LinkedIn.
2. Parsing resumes (PDF/DOCX) to get text and structure.
"""

import re
import pdfplumber
import docx
from io import BytesIO
from fastapi import UploadFile


def _normalize(text: str) -> str:
    """Lowercase and collapse whitespace."""
    if not text:
        return ""
    t = text.lower()
    t = re.sub(r"\s+", " ", t).strip()
    return t


# -------------------------
# 1. JOB DESCRIPTION HANDLING
# -------------------------

def extract_jd_from_text(jd_text: str) -> str:
    """Return JD text as-is when pasted."""
    return jd_text.strip()


# -------------------------
# 2. RESUME PARSING
# -------------------------

def parse_pdf_resume(file_bytes: bytes) -> tuple:
    """
    Extract text and structure from a PDF resume, including detection of tables, images, and font sizes.
    
    Returns:
        tuple: (text: str, structure: list) where structure contains elements with types:
            - 'heading': Section headings with font size
            - 'bullet': Bullet points with font size
            - 'table': Extracted tables
            - 'image': Detected images
            - 'text': Regular text with font size
    
    Raises:
        ValueError: If the PDF cannot be processed
    """
    text = ""
    structure = []
    
    try:
        with pdfplumber.open(BytesIO(file_bytes)) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                # Get character-level data for font size analysis
                chars = page.chars if hasattr(page, 'chars') else []
                
                # 1. Extract text with font information
                if hasattr(page, 'extract_text'):
                    page_text = page.extract_text()
                    if page_text:
                        lines = page_text.split("\n")
                        current_line = ""
                        current_fonts = []
                        
                        # Group characters by line and collect font information
                        for char in chars:
                            if char.get('text') == '\n':
                                if current_line.strip():
                                    # Calculate average font size for the line
                                    avg_size = round(sum(f['size'] for f in current_fonts) / len(current_fonts), 1) if current_fonts else 0
                                    line_type = "text"
                                    
                                    # Determine line type
                                    line_stripped = current_line.strip()
                                    if line_stripped.endswith(":") or line_stripped.isupper():
                                        line_type = "heading"
                                    elif line_stripped.startswith(("•", "-", "*")):
                                        line_type = "bullet"
                                    
                                    structure.append({
                                        "type": line_type,
                                        "content": current_line,
                                        "font_size": avg_size,
                                        "page": page_num
                                    })
                                    
                                current_line = ""
                                current_fonts = []
                            else:
                                current_line += char.get('text', '')
                                current_fonts.append({
                                    'size': char.get('size', 0),
                                    'fontname': char.get('fontname', '')
                                })
                        
                        text += page_text + "\n"
                
                # 2. Extract tables
                try:
                    tables = page.extract_tables() if hasattr(page, 'extract_tables') else []
                    if tables:
                        for table_num, table in enumerate(tables, 1):
                            if table and any(any(cell for cell in row if cell) for row in table):
                                table_text = "\n".join(" | ".join(str(cell or "").strip() for cell in row) for row in table)
                                structure.append({
                                    "type": "table",
                                    "content": table_text,
                                    "page": page_num,
                                    "table_num": table_num
                                })
                                text += f"\n[Table {table_num} on page {page_num}]\n{table_text}\n"
                except Exception as e:
                    print(f"Warning: Error extracting tables from page {page_num}: {str(e)}")
                
                # 3. Check for images
                try:
                    if hasattr(page, 'images') and page.images:
                        for img_num, img in enumerate(page.images, 1):
                            structure.append({
                                "type": "image",
                                "page": page_num,
                                "image_num": img_num,
                                "bbox": img.get("bbox", []),
                                "width": img.get("width", 0),
                                "height": img.get("height", 0)
                            })
                            text += f"\n[Image {img_num} on page {page_num}]\n"
                except Exception as e:
                    print(f"Warning: Error processing images on page {page_num}: {str(e)}")
    
    except Exception as e:
        raise ValueError(f"Failed to parse PDF: {str(e)}")
    
    return text.strip(), structure


def parse_docx_resume(file_bytes: bytes) -> tuple:
    """
    Extract text and structure from a DOCX resume.
    Note: PDF format is recommended for best results as it provides more accurate
    structure and formatting information.
    
    Returns:
        tuple: (text: str, structure: list) with similar structure to PDF parsing,
        but with limited font information compared to PDF.
    """
    doc = docx.Document(BytesIO(file_bytes))
    text = ""
    structure = []
    
    # Default font size (in points) for DOCX (varies by template)
    DEFAULT_FONT_SIZE = 11.0
    
    for para in doc.paragraphs:
        clean_text = para.text.strip()
        if not clean_text:
            continue
            
        # Try to get font size (not always available in DOCX)
        font_size = DEFAULT_FONT_SIZE
        if para.runs and hasattr(para.runs[0].font, 'size'):
            if para.runs[0].font.size:
                # Convert 20ths of a point to points
                font_size = para.runs[0].font.size.pt if para.runs[0].font.size.pt > 0 else font_size
        
        # Determine element type
        style = para.style.name.lower()
        if "heading" in style:
            element_type = "heading"
        elif clean_text.startswith(("•", "-", "*")):
            element_type = "bullet"
        else:
            element_type = "text"
            
        structure.append({
            "type": element_type,
            "content": clean_text,
            "font_size": font_size,
            "page": 1  # DOCX doesn't have page info easily accessible
        })
        
        text += clean_text + "\n"
        
    return text.strip(), structure


def parse_resume(file: UploadFile) -> tuple:
    """
    Detect file type and call appropriate parser.
    
    Note: For best results, use PDF format as it provides more accurate
    structure and formatting information. DOCX support is provided as a fallback
    but with limited functionality.
    
    Args:
        file: Uploaded file (PDF or DOCX)
        
    Returns:
        tuple: (text: str, structure: list)
        
    Raises:
        ValueError: If file type is not supported or file cannot be parsed
    """
    file_bytes = file.file.read()
    try:
        if file.filename.lower().endswith(".pdf"):
            return parse_pdf_resume(file_bytes)
        elif file.filename.lower().endswith(".docx"):
            return parse_docx_resume(file_bytes)
        else:
            raise ValueError("Unsupported file type. Please upload PDF (recommended) or DOCX.")
    except Exception as e:
        raise ValueError(f"Error parsing file: {str(e)}")
