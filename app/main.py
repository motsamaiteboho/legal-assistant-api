import asyncio
import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Optional
import io

import pdfkit
import requests
import uvicorn
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config.config import Config
from app.models import CaseExtractionResponse, ChatRequest, ChatResponse, HealthResponse
from app.models.case_models import (
    AdvancedComparisonExportRequest,
    AdvancedComparisonRequest,
    AdvancedComparisonResponse,
    PdfUrlRequest,
)
from app.models.transcript_models import (
    TranscriptRequest,
    TranscriptResponse,
    TranscriptUrlRequest,
)
from app.services import transcript_service
from app.services.case_comparison_service import case_comparison_service
from app.services.case_extractor_service import case_extractor_service
from app.services.chat_service import chat_service
from app.services.vector_store_service import vector_store_service
from app.utils.file_utils import allowed_file, validate_file_size

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# App setup
# -----------------------------------------------------------------------------
app = FastAPI(
    title="Legal Assistant API",
    description="A comprehensive API for South African legal research and case analysis",
    version="2.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS (tighten in production when you can)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).parent
TEMPLATE_DIR = BASE_DIR / "templates"

env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    autoescape=select_autoescape(["html", "xml"]),
)

WKHTMLTOPDF_PATH = os.getenv("WKHTMLTOPDF_PATH", "/app/bin/wkhtmltopdf")
pdfkit_config = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH)

# pdfkit_config = pdfkit.configuration( 
# wkhtmltopdf=r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe" 
# )

MAX_FILE_BYTES = 10 * 1024 * 1024  # 10MB


# -----------------------------------------------------------------------------
# Root endpoint
# -----------------------------------------------------------------------------
@app.get("/")
async def root():
    return {
        "message": "Legal Assistant API",
        "version": "2.0.0",
        "endpoints": {
            "docs": "/docs",
            "chat": "/ask (POST)",
            "case_extractor_upload": "/extract-case/upload (POST)",
            "case_extractor_url": "/extract-case/url (POST)",
            "transcript_analyze": "/transcripts/analyze (POST)",
            "transcript_upload": "/transcripts/upload (POST)",
            "transcript_url": "/transcripts/url (POST)",
            "health": "/health (GET)",
        },
    }


# -----------------------------------------------------------------------------
# Chat endpoint
# -----------------------------------------------------------------------------
@app.post("/ask", response_model=ChatResponse)
async def ask_question(request: ChatRequest):
    """
    Ask a legal question.

    Submit a legal question and receive an AI-generated answer based on SAFLII case law.
    The response includes relevant legal sources and citations.
    """
    if not request.query.strip():
        raise HTTPException(status_code=400, detail="Please enter a question.")

    result = chat_service.process_query(request.query)
    return result


# -----------------------------------------------------------------------------
# Case extraction: upload
# -----------------------------------------------------------------------------
@app.post("/extract-case/upload", response_model=CaseExtractionResponse)
async def extract_case_from_upload(file: UploadFile = File(...)):
    """Extract legal elements from uploaded PDF file."""
    if not allowed_file(file.filename):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    # validate_file_size may move the pointer; ensure it is reset afterwards
    if not validate_file_size(file.file):
        raise HTTPException(status_code=400, detail="File size must be less than 10MB")

    file.file.seek(0)
    result = case_extractor_service.extract_from_pdf(file)

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Extraction failed"))

    return result


# -----------------------------------------------------------------------------
# Case extraction: URL
# -----------------------------------------------------------------------------
@app.post("/extract-case/url", response_model=CaseExtractionResponse)
async def extract_case_from_url(request: PdfUrlRequest):
    """Extract legal elements from PDF URL."""
    pdf_url = (request.pdf_url or "").strip()
    if not pdf_url:
        raise HTTPException(status_code=400, detail="Please provide a PDF URL.")

    # Ensure URL has a scheme
    if not pdf_url.startswith(("http://", "https://")):
        pdf_url = f"https://{pdf_url}"

    logger.info("Starting extraction for URL: %s", pdf_url)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,"
            "image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
        "Referer": "https://www.saflii.org/",
    }

    session = requests.Session()
    session.headers.update(headers)

    # If you still want a delay, do it async-safe:
    await asyncio.sleep(0.2)

    try:
        response = session.get(pdf_url, timeout=30, allow_redirects=True)
        content_type = (response.headers.get("content-type") or "").lower()

        # Detect blocking pages early
        if "text/html" in content_type:
            preview = response.text[:500].lower()
            indicators = ("access denied", "forbidden", "bot", "blocked", "cloudflare")
            if any(i in preview for i in indicators):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Website is blocking automated access. "
                        "Please try uploading the PDF file directly."
                    ),
                )

        response.raise_for_status()

        # Must be PDF
        if not response.content.startswith(b"%PDF"):
            # Sometimes blocking HTML is served with wrong content-type
            head = response.content[:200].lower()
            if b"<html" in head or head.startswith(b"<!doctype"):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "Received an HTML page instead of a PDF. "
                        "The website may be blocking automated access."
                    ),
                )
            raise HTTPException(status_code=400, detail="Downloaded content is not a valid PDF file")

        # File size check
        content_length = response.headers.get("content-length")
        if content_length and int(content_length) > MAX_FILE_BYTES:
            raise HTTPException(status_code=400, detail="PDF size must be less than 10MB")

        pdf_content = io.BytesIO(response.content)
        result = case_extractor_service.extract_from_pdf_content(pdf_content, pdf_url)

        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Extraction failed"))

        return result

    except requests.exceptions.RequestException as e:
        logger.exception("Failed to download PDF from URL")
        raise HTTPException(status_code=400, detail=f"Failed to download PDF from URL: {e}") from e


# -----------------------------------------------------------------------------
# PDF export endpoints
# -----------------------------------------------------------------------------
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
        headers={"Content-Disposition": f'attachment; filename="{filename}.pdf"'},
    )


@app.post("/export-advanced-comparison-pdf")
async def export_advanced_comparison_pdf(payload: AdvancedComparisonExportRequest):
    """Export the advanced comparison HTML as a nicely formatted PDF."""
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
        headers={"Content-Disposition": f'attachment; filename="{filename}.pdf"'},
    )


# -----------------------------------------------------------------------------
# Advanced comparison
# -----------------------------------------------------------------------------
@app.post("/advanced-comparison", response_model=AdvancedComparisonResponse)
async def advanced_comparison(req: AdvancedComparisonRequest):
    """Perform a high-level legal comparison of multiple extracted case summaries."""
    if not req.cases or len(req.cases) < 2:
        raise HTTPException(status_code=400, detail="At least two cases are required.")

    comparison = case_comparison_service.generate_advanced_comparison(req.cases)
    return AdvancedComparisonResponse(comparison=comparison)


# -----------------------------------------------------------------------------
# Health endpoint
# -----------------------------------------------------------------------------
@app.get("/health", response_model=HealthResponse)
async def health_check():
    return {
        "status": "healthy",
        "services": {
            "chat": "available" if vector_store_service.is_available() else "unavailable",
            "case_extractor": "available",
        },
    }


# -----------------------------------------------------------------------------
# Transcript endpoints
# -----------------------------------------------------------------------------
@app.post("/transcripts/analyze", response_model=TranscriptResponse)
async def analyze_transcript(request: TranscriptRequest):
    if not request.transcript.strip():
        raise HTTPException(status_code=400, detail="Please provide transcript text.")

    try:
        return transcript_service.analyze_transcript(request.transcript, request.context)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error analyzing transcript: {e}") from e


@app.post("/transcripts/upload", response_model=TranscriptResponse)
async def upload_and_analyze_transcript(
    file: UploadFile = File(...),
    context: Optional[str] = None,
):
    """Upload a transcript file and analyze it. Supports PDF, TXT, DOC, and DOCX."""
    try:
        if not transcript_service.allowed_file(file.filename):
            raise HTTPException(
                status_code=400,
                detail="File must be PDF, TXT, DOC, or DOCX format",
            )

        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)

        if file_size > MAX_FILE_BYTES:
            raise HTTPException(status_code=400, detail="File size must be less than 10MB")

        content = await file.read()
        text = transcript_service.extract_text_from_file(content, file.filename)
        result = transcript_service.analyze_transcript(text, context)

        # Update metadata
        result.metadata.filename = file.filename
        result.metadata.upload_date = datetime.now()

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing transcript file: {e}") from e


@app.post("/transcripts/url", response_model=TranscriptResponse)
async def analyze_transcript_from_url(request: TranscriptUrlRequest):
    transcript_url = (request.transcript_url or "").strip()
    if not transcript_url:
        raise HTTPException(status_code=400, detail="Please provide a transcript URL.")

    if not transcript_url.startswith(("http://", "https://")):
        transcript_url = f"https://{transcript_url}"

    try:
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "*/*",
        }

        session = requests.Session()
        session.headers.update(headers)

        response = session.get(transcript_url, timeout=30, allow_redirects=True)
        response.raise_for_status()

        content_length = response.headers.get("content-length")
        if content_length and int(content_length) > MAX_FILE_BYTES:
            raise HTTPException(status_code=400, detail="File size must be less than 10MB")

        filename = "transcript"
        cd = response.headers.get("content-disposition") or ""
        match = re.search(r'filename="?([^"]+)"?', cd)
        if match:
            filename = match.group(1)
        else:
            filename = transcript_url.split("/")[-1].split("?")[0] or filename

        text = transcript_service.extract_text_from_file(response.content, filename)
        result = transcript_service.analyze_transcript(text, request.context)

        result.metadata.filename = filename
        result.metadata.upload_date = datetime.now()
        result.metadata.source_url = transcript_url

        return result

    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to download transcript from URL: {e}",
        ) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing transcript: {e}") from e


@app.post("/transcripts/export-pdf")
async def export_transcript_analysis(payload: TranscriptResponse):
    if not payload.success or payload.summary is None:
        raise HTTPException(status_code=400, detail="No valid analysis result to export")

    try:
        metadata = payload.metadata or {}
        filename = metadata.get("filename", "transcript_analysis")

        template = env.get_template("transcript_summary.html")
        upload_dt = metadata.get("upload_date") or datetime.now()

        html_str = template.render(
            filename=filename,
            witness=metadata.get("witness", "Unknown"),
            upload_date=upload_dt.strftime("%Y-%m-%d %H:%M"),
            summary=payload.summary,
            generated_at=datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
        )

        pdf_bytes = pdfkit.from_string(html_str, False, configuration=pdfkit_config)
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}_analysis.pdf"'},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating PDF: {e}") from e


# -----------------------------------------------------------------------------
# Local dev entry
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    Config.validate_config()
    port = int(os.getenv("PORT", "5000"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
