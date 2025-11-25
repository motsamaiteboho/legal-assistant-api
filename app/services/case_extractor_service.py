import PyPDF2
import json
import re
from langchain_openai import ChatOpenAI
from app.config.config import Config
from app.prompts.case_extractor_prompts import build_case_analysis_prompt

class CaseExtractorService:
    """Service for extracting legal elements from PDF documents"""
    
    def __init__(self):
        self.llm = ChatOpenAI(
            model=Config.CHAT_MODEL,
            temperature=Config.TEMPERATURE
        )
    
    def extract_from_pdf(self, pdf_file):
        """Extract legal elements from PDF file"""
        try:
            # Extract text
            text = self._extract_text_from_pdf(pdf_file.file)
            if not text.strip():
                raise ValueError("No text could be extracted from the PDF")
            
            # Clean and preprocess text
            cleaned_text = self._clean_legal_text(text)
            
            # Analyze document
            analysis_result = self._analyze_legal_document(cleaned_text)
            
            return {
                "success": True,
                "result": analysis_result,
                "metadata": {
                    "filename": getattr(pdf_file, 'filename', 'unknown'),
                    "text_length": len(text),
                    "cleaned_length": len(cleaned_text)
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def extract_from_pdf_content(self, pdf_content, source_url=None):
        """Extract legal elements from PDF content (BytesIO object)"""
        try:
            # Extract text from PDF content
            text = self._extract_text_from_pdf_content(pdf_content)
            if not text.strip():
                raise ValueError("No text could be extracted from the PDF content")
            
            # Clean and preprocess text
            cleaned_text = self._clean_legal_text(text)
            
            # Analyze document
            analysis_result = self._analyze_legal_document(cleaned_text)
            
            return {
                "success": True,
                "result": analysis_result,
                "metadata": {
                    "source_type": "url",
                    "source_url": source_url,
                    "filename": source_url.split('/')[-1] if source_url else 'unknown.pdf',
                    "text_length": len(text),
                    "cleaned_length": len(cleaned_text)
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def _extract_text_from_pdf_content(self, pdf_content):
        """Extract text from PDF BytesIO content"""
        try:
            # Reset the BytesIO position to start
            pdf_content.seek(0)
            
            # Use PyPDF2 to read from BytesIO
            pdf_reader = PyPDF2.PdfReader(pdf_content)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            return text
        except Exception as e:
            raise Exception(f"Failed to extract text from PDF content: {str(e)}")
    
    def _extract_text_from_pdf(self, pdf_file):
        """Extract text from PDF file"""
        try:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            return text
        except Exception as e:
            raise Exception(f"Failed to extract text from PDF: {str(e)}")
    
    def _clean_legal_text(self, text):
        """Clean and preprocess legal text for better analysis"""
        # Remove excessive whitespace
        text = re.sub(r'\n\s*\n', '\n\n', text)
        
        # Remove page numbers and headers
        text = re.sub(r'\bPage \d+ of \d+\b', '', text)
        text = re.sub(r'\b\d+\s*\\s*\d+\b', '', text)  # Page numbers like "1 / 10"
        
        # Remove common legal document noise
        text = re.sub(r'©.*?\n', '', text)
        text = re.sub(r'SAFLII.*?\n', '', text)
        
        # Limit text length to avoid token limits
        return text[:8000]  # Reduced from 12000 to 8000 for better processing
    
    def _analyze_legal_document(self, text):
        """Analyze legal document using LLM with better error handling"""
        try:
            prompt = build_case_analysis_prompt(text)
            response = self.llm.invoke(prompt)
            content = response.content if hasattr(response, "content") else str(response)
            
            print("🔍 LLM Response:", content[:500] + "...")  # Debug logging
            
            # Try to parse as JSON
            try:
                parsed_result = json.loads(content)
                # Validate the parsed result has required fields
                if self._validate_extraction_result(parsed_result):
                    # ✅ Ensure advanced fields are present
                    enriched = self._ensure_advanced_fields(parsed_result, text)
                    return enriched
                else:
                    print("⚠️ JSON validation failed, using fallback")
                    return self._create_structured_response_from_text(content)
                    
            except json.JSONDecodeError as e:
                print(f"⚠️ JSON parsing failed: {e}")
                return self._create_structured_response_from_text(content)
                
        except Exception as e:
            print(f"❌ Analysis failed: {e}")
            return self._create_fallback_response()

    
    def _validate_extraction_result(self, result):
        """Validate that the extraction result has the expected structure"""
        required_fields = ['facts', 'issues', 'ratio', 'precedents']
        if not all(field in result for field in required_fields):
            return False
        
        # Check that we have actual content, not just placeholder text
        if (result.get('facts', '').strip() in ['', 'Unable to extract this section from the document.'] or
            result.get('ratio', '').strip() in ['', 'Unable to extract this section from the document.']):
            return False
            
        return True
    
    def _create_structured_response_from_text(self, text):
        """Create structured response when JSON parsing fails with better parsing"""
        print("🔄 Using enhanced text parsing fallback")
    
        facts = self._extract_enhanced_section(text, ['FACTS:', 'FACTS', 'Factual Background:', 'The facts'])
        issues = self._extract_enhanced_list(text, ['LEGAL_ISSUES:', 'ISSUES:', 'Legal Issues:', 'The issues'])
        ratio = self._extract_enhanced_section(text, ['RATIO_DECIDENDI:', 'RATIO:', 'Ratio:', 'The court held'])
        precedents = self._extract_enhanced_precedents(text)

        outcome = self._extract_outcome_from_raw_text(text)
        issue_evidence = self._extract_issue_evidence_from_raw_text(issues, text)

        return {
            "facts": facts if facts and "Unable to extract" not in facts else self._extract_facts_from_raw_text(text),
            "issues": issues if issues and "Unable to extract" not in issues[0] else self._extract_issues_from_raw_text(text),
            "ratio": ratio if ratio and "Unable to extract" not in ratio else self._extract_ratio_from_raw_text(text),
            "precedents": precedents if precedents and precedents[0].get('caseName') != 'No precedents extracted' else self._extract_precedents_from_raw_text(text),
            "outcome_analysis": outcome,
            "issue_evidence": issue_evidence,
        }

    
    def _extract_enhanced_section(self, text, markers):
        """Extract section using multiple possible markers"""
        for marker in markers:
            section = self._extract_section(text, marker)
            if section and "Unable to extract" not in section and len(section) > 10:
                return section
        return "Unable to extract this section from the document."
    
    def _extract_enhanced_list(self, text, markers):
        """Extract list using multiple possible markers"""
        for marker in markers:
            items = self._extract_list_section(text, marker)
            if items and "Unable to extract" not in items[0] and len(items) > 0:
                return items
        return ["Unable to extract legal issues."]
    
    def _extract_enhanced_precedents(self, text):
        """Extract precedents with better parsing"""
        precedents_section = self._extract_section(text, "PRECEDENTS_CITED:")
        if "Unable to extract" in precedents_section:
            return [{"caseName": "No precedents extracted", "citation": "N/A", "relevance": "Analysis limited"}]
        
        # Try to parse precedents from the text
        lines = [line.strip() for line in precedents_section.split('\n') if line.strip()]
        precedents = []
        
        for line in lines:
            if line and not line.startswith('{') and not line.startswith('['):
                # Try to extract case name and citation
                case_match = re.search(r'([A-Z][^\.\n]{10,50}?)(?:\[(\d{4})\] ([A-Z]+ \d+))?', line)
                if case_match:
                    case_name = case_match.group(1).strip()
                    citation = f"[{case_match.group(2)}] {case_match.group(3)}" if case_match.group(2) else "Citation not found"
                    precedents.append({
                        "caseName": case_name,
                        "citation": citation,
                        "relevance": "Cited in judgment"
                    })
        
        return precedents if precedents else [
            {"caseName": "Precedents analysis limited", "citation": "N/A", "relevance": "Complex extraction required"}
        ]
    
    def _extract_facts_from_raw_text(self, text):
        """Extract facts directly from raw text using patterns"""
        # Look for factual patterns in the text
        sentences = text.split('.')
        factual_sentences = [s.strip() for s in sentences if any(word in s.lower() for word in 
                            ['plaintiff', 'defendant', 'occurred', 'alleged', 'claimed', 'evidence', 'found'])]
        
        if factual_sentences:
            return '. '.join(factual_sentences[:3]) + '.'
        return "Key facts could not be automatically extracted."
    
    def _extract_issues_from_raw_text(self, text):
        """Extract legal issues directly from raw text"""
        sentences = text.split('.')
        issue_sentences = [s.strip() for s in sentences if any(word in s.lower() for word in 
                           ['whether', 'issue', 'question', 'determine', 'consider'])]
        
        if issue_sentences:
            return issue_sentences[:5]  # Return top 5 potential issues
        return ["Legal issues could not be automatically identified."]
    
    def _extract_ratio_from_raw_text(self, text):
        """Extract ratio decidendi directly from raw text"""
        sentences = text.split('.')
        ratio_sentences = [s.strip() for s in sentences if any(word in s.lower() for word in 
                          ['held', 'court finds', 'concluded', 'principle', 'rule', 'therefore'])]
        
        if ratio_sentences:
            return '. '.join(ratio_sentences[:2]) + '.'
        return "Legal principle could not be automatically extracted."
    
    def _extract_precedents_from_raw_text(self, text):
        """Extract precedents directly from raw text using case citation patterns"""
        # Look for case citation patterns
        case_pattern = r'([A-Z][a-zA-Z\s]+ v [A-Z][a-zA-Z\s]+)(?:\s*\[(\d{4})\]\s*([A-Z]+\s+\d+))?'
        matches = re.findall(case_pattern, text)
        
        precedents = []
        for match in matches[:5]:  # Limit to 5 precedents
            case_name = match[0].strip()
            citation = f"[{match[1]}] {match[2]}" if match[1] and match[2] else "Citation not found"
            precedents.append({
                "caseName": case_name,
                "citation": citation,
                "relevance": "Cited in judgment"
            })
        
        return precedents if precedents else [
            {"caseName": "No case citations automatically detected", "citation": "N/A", "relevance": "Pattern matching limited"}
        ]
    
    def _create_fallback_response(self):
        """Create a fallback response when all else fails"""
        return {
            "facts": "Document analysis failed. Please try a different PDF or check the document format.",
            "issues": ["Analysis service unavailable"],
            "ratio": "Unable to process document",
            "precedents": [
                {
                    "caseName": "Service Error",
                    "citation": "N/A", 
                    "relevance": "Technical issue prevented analysis"
                }
            ]
        }
    
    # Keep the original helper methods for compatibility
    def _extract_section(self, text, start_marker, end_marker=None):
        """Extract text between two markers"""
        try:
            start_idx = text.find(start_marker)
            if start_idx == -1:
                return "Unable to extract this section from the document."
            
            start_idx += len(start_marker)
            if end_marker:
                end_idx = text.find(end_marker, start_idx)
                if end_idx == -1:
                    return text[start_idx:].strip()
                return text[start_idx:end_idx].strip()
            else:
                return text[start_idx:].strip()
        except:
            return "Unable to extract this section from the document."
    
    def _extract_list_section(self, text, start_marker, end_marker=None):
        """Extract list items between two markers"""
        section_text = self._extract_section(text, start_marker, end_marker)
        if "Unable to extract" in section_text:
            return ["Unable to extract legal issues."]
        
        lines = [line.strip() for line in section_text.split('\n') if line.strip()]
        return [line for line in lines if line and not line.startswith('{') and not line.startswith('[')]
    
    def _extract_outcome_from_raw_text(self, text: str) -> str:
        """Very lightweight extraction of the outcome/holding."""
        lowered = text.lower()
        if 'appeal is dismissed' in lowered or 'appeal is hereby dismissed' in lowered:
            return "The court dismissed the appeal."
        if 'appeal is upheld' in lowered or 'appeal succeeds' in lowered:
            return "The court upheld the appeal."
        if 'application is dismissed' in lowered:
            return "The court dismissed the application."
        if 'application is granted' in lowered:
            return "The court granted the application."
        # fallback: use first 2 ratio sentences as an outcome-style explanation
        ratio = self._extract_ratio_from_raw_text(text)
        if ratio and "could not be automatically" not in ratio:
            return ratio
        return "The precise outcome of the matter could not be automatically extracted."

    def _extract_issue_evidence_from_raw_text(self, issues, text: str):
        """Link each issue to a few supporting sentences from the judgment."""
        if not issues or not text:
            return []

        sentences = [s.strip() for s in re.split(r'(?<=[\.\?!])\s+', text) if s.strip()]
        evidence_list = []

        for issue in issues:
            if not issue or "unable to extract" in issue.lower():
                evidence_list.append({"issue": issue, "supporting_paragraphs": []})
                continue

            key_words = [w.lower() for w in re.findall(r'\w+', issue) if len(w) > 4]
            supporting = []
            for sent in sentences:
                if any(k in sent.lower() for k in key_words):
                    supporting.append(sent)
                if len(supporting) >= 3:
                    break

            evidence_list.append({
                "issue": issue,
                "supporting_paragraphs": supporting
            })

        return evidence_list
    
    def _ensure_advanced_fields(self, result: dict, text: str) -> dict:
        """
        Ensure the parsed LLM result also contains the advanced fields:
        - outcome_analysis
        - issue_evidence
        without breaking old responses.
        """
        # Make a shallow copy so we don't mutate the original unintentionally
        enriched = dict(result)

        # outcome_analysis: if missing or empty, derive from raw text
        if not enriched.get("outcome_analysis"):
            enriched["outcome_analysis"] = self._extract_outcome_from_raw_text(text)

        # issue_evidence: if missing or not a list, derive from raw text + issues
        issues = enriched.get("issues") or []
        issue_evidence = enriched.get("issue_evidence")
        if not isinstance(issue_evidence, list):
            enriched["issue_evidence"] = self._extract_issue_evidence_from_raw_text(issues, text)
        else:
            # normalise each entry
            normalised = []
            for entry in issue_evidence:
                if not isinstance(entry, dict):
                    continue
                issue = entry.get("issue", "")
                supporting = entry.get("supporting_paragraphs") or []
                if not isinstance(supporting, list):
                    supporting = [str(supporting)]
                normalised.append({
                    "issue": issue,
                    "supporting_paragraphs": supporting,
                })
            # if LLM gave an empty list, we can still populate via fallback
            if not normalised and issues:
                normalised = self._extract_issue_evidence_from_raw_text(issues, text)
            enriched["issue_evidence"] = normalised

        return enriched


# Global instance
case_extractor_service = CaseExtractorService()