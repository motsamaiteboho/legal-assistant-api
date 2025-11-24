from typing import Optional
import requests  # Add this import
import io        # Add this import
from app.models.case_models import PdfUrlRequest
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.config.config import Config
from app.services.chat_service import chat_service
from app.services.case_extractor_service import case_extractor_service
from app.services.vector_store_service import vector_store_service
from app.utils.file_utils import allowed_file, validate_file_size

# Import models from models folder
from app.models import (
    ChatRequest, 
    ChatResponse, 
    CaseExtractionResponse, 
    HealthResponse
)

# Create FastAPI app
app = FastAPI(
    title="Legal Assistant API",
    description="A comprehensive API for South African legal research and case analysis",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Root endpoint
@app.get("/")
async def root():
    return {
        "message": "Legal Assistant API",
        "version": "1.0.0",
        "endpoints": {
            "docs": "/docs",
            "chat": "/ask (POST)",
            "case_extractor_upload": "/extract-case/upload (POST)",
            "case_extractor_url": "/extract-case/url (POST)",
            "health": "/health (GET)"
        }
    }

# Chat endpoint
@app.post("/ask", response_model=ChatResponse)
async def ask_question(request: ChatRequest):
    """
    Ask a legal question
    
    Submit a legal question and receive an AI-generated answer based on SAFLII case law.
    The response includes relevant legal sources and citations.
    """
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Please enter a question.")
    
    result = chat_service.process_query(request.query)
    return result

# Case extraction from file upload
@app.post("/extract-case/upload", response_model=CaseExtractionResponse)
async def extract_case_from_upload(file: UploadFile = File(...)):
    """
    Extract legal elements from uploaded PDF file
    """
    # Validate file type
    if not allowed_file(file.filename):
        raise HTTPException(status_code=400, detail="File must be a PDF")
    
    # Validate file size
    if not validate_file_size(file.file):
        raise HTTPException(status_code=400, detail="File size must be less than 10MB")
    
    # Process the file
    result = case_extractor_service.extract_from_pdf(file)
    
    if not result['success']:
        raise HTTPException(status_code=400, detail=result['error'])
    
    return result

# Case extraction from URL
@app.post("/extract-case/url", response_model=CaseExtractionResponse)
async def extract_case_from_url(request: PdfUrlRequest):
    """
    Extract legal elements from PDF URL
    """
    pdf_url = request.pdf_url
    
    try:
        # Ensure URL has a scheme
        if not pdf_url.startswith(('http://', 'https://')):
            pdf_url = f'https://{pdf_url}'
        
        # Validate URL format
        if not pdf_url.lower().endswith('.pdf'):
            print(f"Warning: URL does not end with .pdf: {pdf_url}")
        
        # Download PDF from URL with SSL verification disabled for problematic sites
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # Try with SSL verification first, then without if it fails
        try:
            response = requests.get(pdf_url, headers=headers, timeout=30, verify=True)
            response.raise_for_status()
        except requests.exceptions.SSLError:
            # If SSL verification fails, try without verification
            print(f"SSL verification failed for {pdf_url}, retrying without verification...")
            response = requests.get(pdf_url, headers=headers, timeout=30, verify=False)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise HTTPException(
                status_code=400, 
                detail=f"Failed to download PDF from URL: {str(e)}"
            )
        
        # Check content type
        content_type = response.headers.get('content-type', '').lower()
        if 'pdf' not in content_type and 'application/octet-stream' not in content_type:
            # For SAFLII, sometimes they don't set proper content-type, so check the content
            if not response.content.startswith(b'%PDF'):
                raise HTTPException(
                    status_code=400, 
                    detail=f"URL does not point to a valid PDF. Content-Type: {content_type}"
                )
        
        # Check file size
        content_length = response.headers.get('content-length')
        if content_length and int(content_length) > 10 * 1024 * 1024:  # 10MB
            raise HTTPException(status_code=400, detail="PDF size must be less than 10MB")
        
        # Verify it's actually a PDF by checking the magic number
        if not response.content.startswith(b'%PDF'):
            raise HTTPException(status_code=400, detail="Downloaded content is not a valid PDF file")
        
        # Create a file-like object from the response content
        pdf_content = io.BytesIO(response.content)
        
        # Process the PDF content
        result = case_extractor_service.extract_from_pdf_content(pdf_content, pdf_url)
        
        if not result['success']:
            raise HTTPException(status_code=400, detail=result['error'])
        
        return result
        
    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=400, 
            detail=f"Failed to download PDF from URL: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Error processing PDF from URL: {str(e)}"
        )

# Health check endpoint
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "services": {
            "chat": "available" if vector_store_service.is_available() else "unavailable",
            "case_extractor": "available"
        }
    }

if __name__ == "__main__":
    # Validate configuration
    Config.validate_config()
    
    print("=" * 50)
    print("🚀 Legal Assistant API (FastAPI) Starting...")
    print("=" * 50)
    print("📚 Available Endpoints:")
    print("   📍 GET  /                          - API information")
    print("   💬 POST /ask                       - Chat with legal database")
    print("   📄 POST /extract-case/upload       - Analyze uploaded PDF")
    print("   🌐 POST /extract-case/url          - Analyze PDF from URL")
    print("   ❤️  GET  /health                   - Service health check")
    print("   📖 GET  /docs                      - Swagger UI Documentation")
    print("   📘 GET  /redoc                     - ReDoc Documentation")
    print("=" * 50)
    print("⚙️  Starting server on http://0.0.0.0:5000")
    print("=" * 50)
    
    uvicorn.run("app.main:app", host="0.0.0.0", port=5000, reload=True)