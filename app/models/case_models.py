from pydantic import BaseModel
from typing import Any, List, Optional

class Precedent(BaseModel):
    caseName: str
    citation: str
    relevance: str
    isSuggested: Optional[bool] = False  # NEW FIELD

class IssueEvidence(BaseModel):
    issue: str
    supporting_paragraphs: List[str]     # NEW STRUCTURE

class CaseExtractionResult(BaseModel):
    facts: str
    issues: List[str]
    ratio: str
    precedents: List[Precedent]

    # NEW FIELDS:
    outcome_analysis: Optional[str] = ""
    issue_evidence: Optional[List[IssueEvidence]] = []


class CaseExtractionResponse(BaseModel):
    success: bool
    result: Optional[CaseExtractionResult] = None
    error: Optional[str] = None
    metadata: Optional[dict] = None

class AdvancedCaseInput(BaseModel):
    id: int
    fileName: str
    facts: str
    issues: List[str] = []
    ratio: str
    precedents: List[Any] = []
    outcome: Optional[str] = None

class AdvancedComparisonRequest(BaseModel):
    cases: List[AdvancedCaseInput]

class AdvancedComparisonResponse(BaseModel):
    comparison: str

class AdvancedComparisonExportRequest(BaseModel):
    comparison_html: str   # the HTML you already show with [innerHTML]
    filename: Optional[str] = None
    title: Optional[str] = "Advanced Comparison Report"


class PdfUrlRequest(BaseModel):
    pdf_url: str
