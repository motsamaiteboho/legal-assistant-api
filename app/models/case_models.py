from pydantic import BaseModel
from typing import List, Optional

class Precedent(BaseModel):
    caseName: str
    citation: str
    relevance: str

class CaseExtractionResult(BaseModel):
    facts: str
    issues: List[str]
    ratio: str
    precedents: List[Precedent]

class CaseExtractionResponse(BaseModel):
    success: bool
    result: Optional[CaseExtractionResult] = None
    error: Optional[str] = None
    metadata: Optional[dict] = None

# Request models
class PdfUrlRequest(BaseModel):
    pdf_url: str
