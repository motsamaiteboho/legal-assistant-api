from typing import List, Optional, Dict
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

class TranscriptSummary(BaseModel):
    """Transcript analysis summary model"""
    executive_summary: str = Field(..., description="Executive summary of the testimony")
    key_topics: List[str] = Field(default_factory=list, description="Key topics discussed")
    critical_admissions: List[str] = Field(default_factory=list, description="Critical admissions made")
    contradictions: List[str] = Field(default_factory=list, description="Contradictions and inconsistencies")
    evidence_mentioned: List[str] = Field(default_factory=list, description="Evidence and exhibits mentioned")
    follow_up_areas: List[str] = Field(default_factory=list, description="Areas for follow-up")
    key_quotes: Optional[List[Dict[str, str]]] = Field(None, description="Key testimony quotes")
    witness_credibility: Optional[str] = Field(None, description="Witness credibility assessment")
    testimony_strengths: Optional[List[str]] = Field(None, description="Strengths in testimony")
    testimony_weaknesses: Optional[List[str]] = Field(None, description="Weaknesses in testimony")

class TranscriptMetadata(BaseModel):
    """Transcript metadata model"""
    filename: str = Field(..., description="Original filename")
    upload_date: Optional[datetime] = Field(None, description="Upload timestamp")
    witness: Optional[str] = Field(None, description="Witness name")
    pages: Optional[int] = Field(None, description="Estimated page count")
    duration: Optional[str] = Field(None, description="Estimated deposition duration")
    context: Optional[str] = Field(None, description="Case context provided")
    text_length: Optional[int] = Field(None, description="Character count of transcript")
    source_url: Optional[str] = Field(None, description="Source URL if downloaded")

class TranscriptRequest(BaseModel):
    """Request model for direct transcript text analysis"""
    transcript: str = Field(..., description="The transcript text to analyze")
    context: Optional[str] = Field(None, description="Case context for better analysis")

class TranscriptUrlRequest(BaseModel):
    """Request model for transcript analysis from URL"""
    transcript_url: str = Field(..., description="URL of the transcript to analyze")
    context: Optional[str] = Field(None, description="Case context for better analysis")

class TranscriptUploadRequest(BaseModel):
    """Request model for transcript upload"""
    context: Optional[str] = Field(None, description="Case context for better analysis")

class TranscriptResponse(BaseModel):
    """Response model for transcript analysis"""
    success: bool = Field(..., description="Whether the analysis was successful")
    summary: Optional[TranscriptSummary] = Field(None, description="Analysis summary")
    metadata: Optional[TranscriptMetadata] = Field(None, description="Transcript metadata")
    message: Optional[str] = Field(None, description="Status message")
    error: Optional[str] = Field(None, description="Error message if any")

class FileType(str, Enum):
    """Supported file types for transcripts"""
    PDF = "pdf"
    TXT = "txt"
    DOC = "doc"
    DOCX = "docx"

class AnalysisOptions(BaseModel):
    """Options for transcript analysis"""
    extract_quotes: bool = Field(True, description="Whether to extract key quotes")
    assess_credibility: bool = Field(True, description="Whether to assess witness credibility")
    identify_follow_up: bool = Field(True, description="Whether to identify follow-up areas")
    language: str = Field("en", description="Language of the transcript")