from pydantic import BaseModel
from typing import List, Optional

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


class PdfUrlRequest(BaseModel):
    pdf_url: str
