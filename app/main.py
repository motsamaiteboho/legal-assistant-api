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
        
        # Enhanced headers to mimic a real browser
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1',
            'Cache-Control': 'max-age=0',
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"'
        }
        
        # Use session with cookies and retries
        session = requests.Session()
        session.headers.update(headers)
        
        # Add a small delay to be more human-like
        import time
        time.sleep(2)
        
        # Try to access the main page first to get cookies
        try:
            main_page = session.get('https://www.saflii.org', timeout=10, verify=False)
            print(f"Main page status: {main_page.status_code}")
        except:
            print("Could not access main page, continuing anyway...")
        
        # Now try to download the PDF
        response = session.get(pdf_url, timeout=30, verify=False, allow_redirects=True)
        
        # Check if we got redirected to a blocking page
        if 'text/html' in response.headers.get('content-type', '') and len(response.content) < 10000:
            # Might be a blocking page, check content
            content = response.text.lower()
            if any(blocked in content for blocked in ['access denied', 'forbidden', 'bot', 'blocked']):
                raise HTTPException(
                    status_code=400, 
                    detail="Website is blocking automated access. Please try uploading the PDF file directly."
                )
        
        response.raise_for_status()
        
        # Check if it's actually a PDF
        if not response.content.startswith(b'%PDF'):
            # Check if it's HTML (blocking page)
            if response.content.startswith(b'<!DOCTYPE') or response.content.startswith(b'<html'):
                raise HTTPException(
                    status_code=400, 
                    detail="Received HTML instead of PDF. The website may be blocking automated access."
                )
            raise HTTPException(status_code=400, detail="Downloaded content is not a valid PDF file")
        
        # Check file size
        content_length = response.headers.get('content-length')
        if content_length and int(content_length) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="PDF size must be less than 10MB")
        
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