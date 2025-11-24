from langchain_openai import ChatOpenAI
from app.config.config import Config
from app.prompts.chat_prompts import build_chat_prompt
from app.services.vector_store_service import vector_store_service

class ChatService:
    """Service for handling chat operations"""
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model=Config.CHAT_MODEL,
            temperature=Config.TEMPERATURE
        )
    
    def process_query(self, user_query: str):
        """Process a user query and return response with sources"""
        if not vector_store_service.is_available():
            return {
                "answer": "Legal database is currently unavailable. Please try again later.",
                "sources": []
            }
        
        # Get relevant documents
        retriever = vector_store_service.get_retriever()
        docs = retriever.get_relevant_documents(user_query) if retriever else []
        
        # Fallback to basic retriever
        if not docs and vector_store_service.retriever:
            docs = vector_store_service.retriever.get_relevant_documents(user_query)
        
        # Build context
        context = self._build_context(docs)
        
        # Generate response
        prompt = build_chat_prompt(user_query, context)
        response = self.llm.invoke(prompt)
        answer = response.content if hasattr(response, "content") else str(response)
        
        # Check for refusal
        refusal_line = "I'm only able to assist with South African legal questions based on SAFLII case law."
        if refusal_line in answer:
            return {"answer": refusal_line, "sources": []}
        
        # Add note if no sources
        if not docs:
            answer += "\n\n_No specific SAFLII case excerpts could be retrieved for this query._"
        
        # Build sources
        sources = self._build_sources(docs)
        
        return {
            "answer": answer,
            "sources": sources
        }
    
    def _build_context(self, docs):
        """Build context from retrieved documents"""
        context_parts = []
        for doc in docs:
            metadata = doc.metadata or {}
            case_name = metadata.get("case_name") or "Unknown case"
            citation = metadata.get("neutral_citation") or ""
            court = metadata.get("court") or ""
            judgment_date = metadata.get("judgment_date") or ""
            saflii_url = metadata.get("saflii_case_url") or metadata.get("saflii_url") or ""
            
            header = f"Source: {case_name} ({citation})"
            if court or judgment_date:
                header += f" – {court} {judgment_date}".strip()
            if saflii_url:
                header += f"\nSAFLII: {saflii_url}"
            
            snippet = doc.page_content[:800] + "..."
            context_parts.append(f"{header}\n{snippet}")
        
        return "\n\n".join(context_parts)
    
    def _build_sources(self, docs):
        """Build sources list from documents"""
        sources = []
        seen_keys = set()
        
        for doc in docs:
            metadata = doc.metadata or {}
            key = (metadata.get("case_name"), metadata.get("neutral_citation"))
            
            if key in seen_keys:
                continue
            seen_keys.add(key)
            
            sources.append({
                "case_name": metadata.get("case_name"),
                "citation": metadata.get("neutral_citation"),
                "court": metadata.get("court"),
                "judgment_date": metadata.get("judgment_date"),
                "saflii_url": metadata.get("saflii_case_url") or metadata.get("saflii_url"),
                "pdf_url": metadata.get("pdf_url"),
                "summary": doc.page_content[:400] + "..."
            })
        
        return sources

# Global instance
chat_service = ChatService()