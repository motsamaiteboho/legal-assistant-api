from pydantic import BaseModel
from typing import List, Optional

class Source(BaseModel):
    case_name: Optional[str] = None
    citation: Optional[str] = None
    court: Optional[str] = None
    judgment_date: Optional[str] = None
    saflii_url: Optional[str] = None
    pdf_url: Optional[str] = None
    summary: Optional[str] = None

class ChatRequest(BaseModel):
    query: str

class ChatResponse(BaseModel):
    answer: str
    sources: List[Source]