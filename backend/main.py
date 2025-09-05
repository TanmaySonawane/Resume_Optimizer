
import time
import traceback
import io
from typing import Dict, List, Optional, Any

# FastAPI imports
from fastapi import FastAPI, File, UploadFile, Form, Request, HTTPException, status

from fastapi.middleware.gzip import GZipMiddleware

from pydantic import BaseModel, Field

from contextlib import asynccontextmanager

# Import local modules
import parser
from suggest_skills import get_missing_skills
from ats_calculator import ATSCalculator
from restructure_advice import analyze_resume_structure

# Global state for rate limiting
request_logs: Dict[str, List[float]] = {}

# Constants for configuration
class Config:
    RATE_LIMIT = 10  # requests per minute
    RATE_LIMIT_WINDOW = 60  # seconds
    MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB
    ALLOWED_EXTENSIONS = {"pdf", "docx"}
    CHUNK_SIZE = 1024 * 64  # 64KB chunks for streaming
    TIMEOUT = 15  # seconds

class ResumeAnalysisRequest(BaseModel):
    """Request model for resume analysis endpoint"""
    jd_text: Optional[str] = Field(
        None,
        description="Job description text to compare against the resume",
        example="Looking for a Python developer with 3+ years of experience..."
    )
    resume: UploadFile = Field(
        ...,
        description="Resume file to analyze (PDF or DOCX)",
        example="resume.pdf"
    )

class AnalysisResponse(BaseModel):
    """Response model for analysis results"""
    success: bool
    jd_text: Optional[str] = None
    # parser.parse_resume returns a list of structure elements
    resume_structure: Optional[List[Dict[str, Any]]] = None
    resume_text: Optional[str] = None
    # ATS score can be fractional during calculation
    ats_score: Optional[float] = None
    # Use Field(default_factory=...) to avoid shared mutable defaults
    suggested_skills: List[str] = Field(default_factory=list)
    improvement_recommendation: List[Dict[str, str]] = Field(default_factory=list)
    error: Optional[str] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application startup and shutdown events.
    
    This context manager handles the application's lifecycle, initializing resources
    on startup and cleaning them up on shutdown.
    
    Yields:
        None: The application runs in this context
    """
    startup_time = time.time()
    
    # Startup: Initialize resources
    print("\n" + "="*50)
    print("Starting Resume Optimizer API...")
    print(f"Startup time: {time.ctime(startup_time)}")
    print("Configuration:")
    print(f"- Rate limit: {Config.RATE_LIMIT} requests per {Config.RATE_LIMIT_WINDOW} seconds")
    print(f"- Max file size: {Config.MAX_FILE_SIZE/1024/1024:.1f}MB")
    print(f"- Allowed file types: {', '.join(Config.ALLOWED_EXTENSIONS)}")
    print("="*50 + "\n")
    
    try:
        # Initialize any required resources here
        
        # Yield control to the application
        yield
        
    except Exception as e:
        print(f"Error in application: {str(e)}")
        raise
        
    finally:
        # Shutdown: Clean up resources
        shutdown_time = time.time()
        uptime = shutdown_time - startup_time
        print("\n" + "="*50)
        print("Shutting down Resume Optimizer API...")
        print(f"Uptime: {uptime:.1f} seconds")
        print(f"Shutdown time: {time.ctime(shutdown_time)}")
        print("="*50 + "\n")

# Initialize FastAPI app with lifespan and metadata
app = FastAPI(
    title="Resume Optimizer API",
    description="""
    ## ATS-Optimized Resume Analysis API
    
    This API provides automated resume analysis and optimization suggestions
    to help job seekers improve their resumes for Applicant Tracking Systems (ATS).
    
    ### Features:
    - Resume parsing and structure analysis
    - ATS scoring based on job description
    - Skill gap analysis
    - Detailed improvement recommendations
    """,
    version="1.0.0",
    contact={
        "name": "API Support",
        "email": "support@resumeoptimizer.com"
    },
    license_info={
        "name": "MIT",
    },
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# Add GZip compression for responses
app.add_middleware(GZipMiddleware, minimum_size=1024)

@app.get("/health", tags=["Health"])
async def health_check():
    """
    Health check endpoint.
    
    Returns:
        dict: Status of the API and its components
    """
    status = {
        "status": "healthy",
        "timestamp": time.time(),
        "version": "1.0.0",
        "components": {
            "api": True,
            "rate_limiting": True,
            "file_processing": True
        }
    }
    
    # Add rate limiting status
    try:
        status["rate_limiting"] = {
            "enabled": True,
            "limit": Config.RATE_LIMIT,
            "window_seconds": Config.RATE_LIMIT_WINDOW
        }
    except Exception as e:
        status["components"]["rate_limiting"] = False
        status["status"] = "degraded"
        status["error"] = f"Rate limiting not available: {str(e)}"
    
    return status

async def check_rate_limit(request: Request) -> None:
    """
    Middleware to enforce rate limiting per IP address.
    
    This function implements a sliding window rate limiting algorithm that allows
    up to RATE_LIMIT requests per RATE_LIMIT_WINDOW seconds per IP address.
    
    Args:
        request: The incoming HTTP request
        
    Raises:
        HTTPException: 429 if rate limit is exceeded with appropriate headers
    """
    try:
        # Get client IP, handling various proxy scenarios
        if request.client is None:
            # Try to get IP from X-Forwarded-For header if behind a proxy
            forwarded = request.headers.get("X-Forwarded-For")
            if forwarded:
                ip = forwarded.split(",")[0].strip()
            else:
                ip = "unknown"
        else:
            ip = request.client.host or "unknown"
        
        current_time = time.time()
        
        # Initialize request logs for this IP if not exists
        if ip not in request_logs:
            request_logs[ip] = []
        
        # Clean up old requests outside the rate limit window
        window_start = current_time - Config.RATE_LIMIT_WINDOW
        request_logs[ip] = [t for t in request_logs[ip] if t > window_start]
        
        # Check if rate limit is exceeded
        if len(request_logs[ip]) >= Config.RATE_LIMIT:
            # Calculate when the next request will be allowed
            retry_after = int(Config.RATE_LIMIT_WINDOW - (current_time - request_logs[ip][0]))
            
            # Add rate limit headers as per RFC 6585
            headers = {
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(Config.RATE_LIMIT),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(current_time + retry_after))
            }
            
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "Rate limit exceeded",
                    "message": f"Too many requests. Please try again in {retry_after} seconds.",
                    "retry_after": retry_after
                },
                headers=headers
            )
        
        # Log the successful request
        request_logs[ip].append(current_time)
        
    except Exception as e:
        # If rate limiting fails, log the error but don't block the request
        # This is a security measure to avoid DoS if the rate limiting fails
        print(f"Rate limiting error: {str(e)}")
        import traceback
        traceback.print_exc()

@app.post("/debug-jd")
async def debug_jd(request: Request):
    data = await request.json()
    print("\n=== DEBUG: Received JD from frontend ===")
    print(data)
    return {"status": "ok", "received": data}

async def validate_file(file: UploadFile) -> UploadFile:
    """
    Validate the uploaded file for type, size, and page count.
    
    Args:
        file: The uploaded file to validate
        
    Returns:
        UploadFile: The validated file with reset file pointer
        
    Raises:
        HTTPException: If file validation fails with appropriate status code and error details
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "No file provided",
                "message": "Please upload a valid file"
            }
        )
    
    try:
        # Check file extension
        if '.' not in file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Invalid file",
                    "message": "File has no extension"
                }
            )
            
        file_extension = file.filename.split(".")[-1].lower()
        if file_extension not in Config.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "Invalid file type",
                    "message": f"File type '{file_extension}' not allowed. "
                              f"Allowed types: {', '.join(Config.ALLOWED_EXTENSIONS)}"
                }
            )
        
        # Check file size using streaming to avoid memory issues
        file_size = 0
        chunks = []
        
        try:
            # Read file in chunks
            while True:
                chunk = await file.read(Config.CHUNK_SIZE)
                if not chunk:
                    break
                file_size += len(chunk)
                chunks.append(chunk)
                
                if file_size > Config.MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail={
                            "error": "File too large",
                            "message": f"File exceeds maximum size of {Config.MAX_FILE_SIZE/1024/1024:.1f}MB"
                        }
                    )
        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "error": "File read error",
                    "message": "Error reading the uploaded file"
                }
            )
        
        # Check page count for PDF files
        if file_extension == 'pdf':
            try:
                from PyPDF2 import PdfReader
                
                # Combine chunks into a single bytes object
                file_content = b''.join(chunks)
                pdf_reader = PdfReader(io.BytesIO(file_content))
                
                if len(pdf_reader.pages) > 2:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail={
                            "error": "Resume too long",
                            "message": "Current version of this app is not designed to handle resumes longer than 2 pages"
                        }
                    )
            except Exception as e:
                if isinstance(e, HTTPException):
                    raise e
                # If we can't read the PDF, we'll let the parser handle that error
                print(f"Warning: Could not validate PDF pages: {str(e)}")
        
        # Reset file pointer for further processing
        file.file = io.BytesIO(b''.join(chunks))
        return file
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error": "Validation error",
                "message": "An unexpected error occurred during file validation"
            }
        )

@app.post(
    "/process",
    response_model=AnalysisResponse,
    summary="Analyze resume with optional job description",
    description="""
    Processes an uploaded resume (max 2 pages) and optionally compares it against a job description
    to provide ATS optimization feedback, skill gap analysis, and improvement suggestions.
    
    Note: The current version of this app only supports resumes that are 2 pages or less.
    Uploading a longer resume will result in an error.
    """,
    responses={
        200: {"model": AnalysisResponse, "description": "Analysis completed successfully"},
        400: {
            "description": "Invalid input, file format, or resume too long",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Resume too long",
                        "message": "Current version of this app is not designed to handle resumes longer than 2 pages"
                    }
                }
            }
        },
        413: {"description": "File too large (max 5MB)"},
        422: {"description": "Validation error"},
        429: {"description": "Rate limit exceeded"},
        500: {"description": "Internal server error"}
    },
    tags=["Analysis"]
)
async def process_resume_and_jd(
    jd_text: Optional[str] = Form(
        None,
        description="Optional job description text to compare against the resume"
    ),
    resume: UploadFile = File(..., description="Resume file (PDF or DOCX)"),
    request: Request = None
) -> AnalysisResponse:
    """
    Process a resume and optionally compare it with a job description.
    
    This endpoint performs several analyses:
    - Extracts text and structure from the resume
    - Identifies missing skills compared to the job description
    - Calculates an ATS compatibility score
    - Provides specific improvement recommendations
    
    The response includes structured data that can be used to display
    the analysis results to the user.
    """
    start_time = time.time()
    timeout_seconds = Config.TIMEOUT
    
    try:
        # Rate limiting check
        if request:
            await check_rate_limit(request)
            
        # Validate the uploaded file
        await validate_file(resume)
        
        # Parse the resume
        try:
            resume_text, resume_structure = parser.parse_resume(resume)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Error parsing resume: {str(e)}"
            )
        
        # Check for timeout before analysis
        if time.time() - start_time > timeout_seconds - 3:
            raise HTTPException(
                status_code=408,
                detail="Request timed out during resume parsing."
            )
        
        # Initialize default values
        ats_score = 0.0
        suggested_skills = []
        issues = []
        
        # Only perform analysis if job description is provided
        if jd_text and jd_text.strip():
            try:
                print("Starting analysis...")

                # Check for timeout before each operation
                if time.time() - start_time > timeout_seconds - 10:
                    print("Timeout approaching, skipping detailed analysis")
                    raise TimeoutError("Analysis timeout")

                print("Extracting missing skills...")
                suggested_skills = get_missing_skills(jd_text, resume_text)

                if time.time() - start_time > timeout_seconds - 8:
                    print("Timeout approaching, skipping ATS calculation")
                    raise TimeoutError("Analysis timeout")

                print("Calculating ATS score...")
                ats = ATSCalculator(jd_text)
                ats_score = ats.total_score(resume_text, resume_structure)

                if time.time() - start_time > timeout_seconds - 5:
                    print("Timeout approaching, skipping structure analysis")
                    raise TimeoutError("Analysis timeout")

                print("Analyzing resume structure...")
                issues = analyze_resume_structure(resume_text, resume_structure)

                print("Analysis completed successfully")

            except Exception as e:
                # Log the error but don't fail the entire request
                print(f"Warning: Analysis error: {str(e)}")
                traceback.print_exc()
                # Continue with default values
        # Build response
        return AnalysisResponse(
            success=True,
            jd_text=jd_text,
            resume_text=resume_text,
            resume_structure=resume_structure,
            ats_score=ats_score,
            suggested_skills=suggested_skills,
            improvement_recommendation=issues
        )
    except HTTPException as he:
        # Re-raise HTTP exceptions (like rate limiting, timeouts)
        raise he
    except Exception as e:
        # Log the full error for debugging
        print(f"Error in /process: {str(e)}")
        traceback.print_exc()
        # Return a generic error message to the client
        return JSONResponse(
            status_code=500,
            content={"error": "An internal server error occurred. Please try again later."}
        )
    finally:
        # Cleanup: close the uploaded file
        if 'resume' in locals():
            try:
                await resume.close()
            except:
                pass
