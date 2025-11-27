import datetime
from pathlib import Path
from typing import Optional
import requests  # Add this import
import io        # Add this import
from app.models.case_models import AdvancedComparisonExportRequest, AdvancedComparisonRequest, AdvancedComparisonResponse, PdfUrlRequest
from app.services.case_comparison_service import case_comparison_service
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from app.config.config import Config
from app.services.chat_service import chat_service
from app.services.case_extractor_service import case_extractor_service
from app.services.vector_store_service import vector_store_service
from app.utils.file_utils import allowed_file, validate_file_size
from fastapi.responses import Response
from jinja2 import Environment, FileSystemLoader, select_autoescape
from datetime import datetime
from pathlib import Path
import pdfkit

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

BASE_DIR = Path(__file__).parent
TEMPLATE_DIR = BASE_DIR / "templates"

env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)

# If wkhtmltopdf is on PATH, this is enough:
#pdfkit_config = pdfkit.configuration(wkhtmltopdf="/app/bin/wkhtmltopdf")
pdfkit_config = pdfkit.configuration(
     wkhtmltopdf=r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
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
        print(f"🔍 Starting extraction for URL: {pdf_url}")
        
        # Ensure URL has a scheme
        if not pdf_url.startswith(('http://', 'https://')):
            pdf_url = f'https://{pdf_url}'
        
        print(f"📡 Processing URL: {pdf_url}")
        
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
            'Cache-Control': 'max-age=0',
            'Referer': 'https://www.saflii.org/'
        }
        
        # Use session with cookies
        session = requests.Session()
        session.headers.update(headers)
        
        # Add a small delay
        import time
        time.sleep(1)
        
        print("🌐 Attempting to download PDF...")
        
        # Download the PDF
        response = session.get(pdf_url, timeout=30, verify=False, allow_redirects=True)
        
        print(f"📄 Response status: {response.status_code}")
        print(f"📄 Content-Type: {response.headers.get('content-type', 'unknown')}")
        print(f"📄 Content length: {len(response.content)} bytes")
        
        # Check if we got a blocking page
        content_type = response.headers.get('content-type', '').lower()
        if 'text/html' in content_type:
            # Check for blocking indicators in content
            content_preview = response.text[:500].lower()
            if any(indicator in content_preview for indicator in ['access denied', 'forbidden', 'bot', 'blocked', 'cloudflare']):
                print("❌ Blocking page detected")
                raise HTTPException(
                    status_code=400, 
                    detail="Website is blocking automated access. Please try uploading the PDF file directly."
                )
        
        response.raise_for_status()
        
        # Check if it's actually a PDF
        if not response.content.startswith(b'%PDF'):
            print("❌ Content is not a PDF")
            # Check if it's HTML (blocking page)
            if response.content.startswith(b'<!DOCTYPE') or response.content.startswith(b'<html') or b'<html' in response.content[:100]:
                raise HTTPException(
                    status_code=400, 
                    detail="Received HTML page instead of PDF. The website may be blocking automated access."
                )
            raise HTTPException(status_code=400, detail="Downloaded content is not a valid PDF file")
        
        print("✅ Valid PDF downloaded")
        
        # Check file size
        content_length = response.headers.get('content-length')
        if content_length and int(content_length) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="PDF size must be less than 10MB")
        
        # Create a file-like object from the response content
        pdf_content = io.BytesIO(response.content)
        
        print("🔧 Processing PDF content...")
        
        # Process the PDF content
        result = case_extractor_service.extract_from_pdf_content(pdf_content, pdf_url)
        
        print(f"✅ Extraction result: {result.get('success', False)}")
        
        if not result['success']:
            raise HTTPException(status_code=400, detail=result['error'])
        
        return result
        
    except requests.exceptions.RequestException as e:
        print(f"❌ Request error: {str(e)}")
        raise HTTPException(
            status_code=400, 
            detail=f"Failed to download PDF from URL: {str(e)}"
        )
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        print(f"❌ Error type: {type(e).__name__}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500, 
            detail=f"Unexpected error processing PDF: {str(e)}"
        )

@app.post("/export-pdf")
async def export_pdf(payload: CaseExtractionResponse):
    if not payload.success or payload.result is None:
        raise HTTPException(status_code=400, detail="No valid extraction result to export")

    metadata = payload.metadata or {}
    filename = metadata.get("filename", "case_summary")
    char_count = metadata.get("text_length", 0)

    template = env.get_template("case_summary.html")
    html_str = template.render(
        filename=filename,
        char_count=char_count,
        facts=payload.result.facts,
        issues=payload.result.issues,
        ratio=payload.result.ratio,
        precedents=payload.result.precedents,
        outcome_analysis=getattr(payload.result, "outcome_analysis", None),
        issue_evidence=getattr(payload.result, "issue_evidence", None),
        generated_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    )

    pdf_bytes = pdfkit.from_string(html_str, False, configuration=pdfkit_config)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}.pdf"'
        },
    )

@app.post("/export-advanced-comparison-pdf")
async def export_advanced_comparison_pdf(payload: AdvancedComparisonExportRequest):
    """
    Export the advanced comparison HTML as a nicely formatted PDF.
    """
    if not payload.comparison_html.strip():
        raise HTTPException(status_code=400, detail="No comparison content to export")

    filename = (payload.filename or "advanced_comparison").replace(" ", "_")
    title = payload.title or "Advanced Comparison Report"

    template = env.get_template("advanced_comparison.html")
    html_str = template.render(
      title=title,
      comparison_html=payload.comparison_html,
      generated_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
    )

    pdf_bytes = pdfkit.from_string(html_str, False, configuration=pdfkit_config)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}.pdf"'
        },
    )

@app.post("/advanced-comparison", response_model=AdvancedComparisonResponse)
async def advanced_comparison(req: AdvancedComparisonRequest):
    """
    Perform a high-level legal comparison of multiple extracted case summaries.
    """
    if not req.cases or len(req.cases) < 2:
        raise HTTPException(status_code=400, detail="At least two cases are required.")

    comparison = case_comparison_service.generate_advanced_comparison(req.cases)
    return AdvancedComparisonResponse(comparison=comparison)

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