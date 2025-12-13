import os
import tempfile
import json
import re
from typing import Dict, List, Optional, Any
from datetime import datetime
import PyPDF2
import docx
from openai import OpenAI
import tiktoken

from app.config.config import Config
from app.models.transcript_models import (
    TranscriptSummary,
    TranscriptMetadata,
    TranscriptResponse
)
from app.prompts.transcript_prompts import (
    TRANSCRIPT_SUMMARY_PROMPT,
    TRANSCRIPT_QUOTE_EXTRACTION_PROMPT,
    CREDIBILITY_ASSESSMENT_PROMPT
)

class TranscriptService:
    """Service for analyzing deposition transcripts"""
    
    def __init__(self):
        self.config = Config()
        self.client = OpenAI(api_key=self.config.OPENAI_API_KEY)
        self.max_tokens = 16000  # Adjust based on model limits
        
    def analyze_transcript(self, transcript_text: str, context: str = None) -> TranscriptResponse:
        """
        Analyze a deposition transcript and extract key legal elements
        
        Args:
            transcript_text: The transcript text to analyze
            context: Optional case context
            
        Returns:
            TranscriptResponse with analysis results
        """
        try:
            print(f"🔍 Starting transcript analysis (text length: {len(transcript_text)} chars)")
            
            # Truncate text if too long
            processed_text = self._preprocess_transcript(transcript_text)
            
            # Generate summary using OpenAI
            summary_data = self._generate_summary(processed_text, context)
            
            # Extract key quotes
            key_quotes = self._extract_key_quotes(processed_text)
            
            # Assess witness credibility
            credibility = self._assess_credibility(processed_text, context)
            
            # Create summary object
            summary = TranscriptSummary(
                executive_summary=summary_data.get("executive_summary", ""),
                key_topics=summary_data.get("key_topics", []),
                critical_admissions=summary_data.get("critical_admissions", []),
                contradictions=summary_data.get("contradictions", []),
                evidence_mentioned=summary_data.get("evidence_mentioned", []),
                follow_up_areas=summary_data.get("follow_up_areas", []),
                key_quotes=key_quotes.get("quotes", []),
                witness_credibility=credibility,
                testimony_strengths=summary_data.get("testimony_strengths", []),
                testimony_weaknesses=summary_data.get("testimony_weaknesses", [])
            )
            
            # Create metadata
            metadata = TranscriptMetadata(
                filename="transcript.txt",
                upload_date=datetime.now(),
                text_length=len(transcript_text),
                context=context,
                pages=self._estimate_pages(transcript_text),
                duration=self._estimate_duration(transcript_text)
            )
            
            return TranscriptResponse(
                success=True,
                summary=summary,
                metadata=metadata,
                message="Transcript analyzed successfully"
            )
            
        except Exception as e:
            print(f"❌ Error analyzing transcript: {str(e)}")
            return TranscriptResponse(
                success=False,
                error=f"Error analyzing transcript: {str(e)}",
                message="Failed to analyze transcript"
            )
    
    def extract_text_from_file(self, file_content: bytes, filename: str) -> str:
        """
        Extract text from various file formats
        
        Args:
            file_content: Raw file content as bytes
            filename: Original filename for format detection
            
        Returns:
            Extracted text
        """
        if filename.lower().endswith('.pdf'):
            return self._extract_text_from_pdf(file_content)
        elif filename.lower().endswith('.txt'):
            return file_content.decode('utf-8', errors='ignore')
        elif filename.lower().endswith(('.doc', '.docx')):
            return self._extract_text_from_docx(file_content)
        else:
            # Try to decode as text
            try:
                return file_content.decode('utf-8')
            except:
                raise ValueError(f"Unsupported file format: {filename}")
    
    def allowed_file(self, filename: str) -> bool:
        """
        Check if file type is allowed
        
        Args:
            filename: Name of the file
            
        Returns:
            True if file type is allowed
        """
        allowed_extensions = {'.pdf', '.txt', '.doc', '.docx'}
        return any(filename.lower().endswith(ext) for ext in allowed_extensions)
    
    def _preprocess_transcript(self, text: str) -> str:
        """
        Preprocess transcript text for analysis
        
        Args:
            text: Raw transcript text
            
        Returns:
            Preprocessed text
        """
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Truncate if too long (respect token limits)
        encoding = tiktoken.encoding_for_model(Config.CHAT_MODEL)
        tokens = encoding.encode(text)
        
        if len(tokens) > self.max_tokens:
            print(f"⚠️ Transcript too long ({len(tokens)} tokens), truncating to {self.max_tokens}")
            truncated_tokens = tokens[:self.max_tokens]
            text = encoding.decode(truncated_tokens)
        
        return text
    
    def _generate_summary(self, transcript_text: str, context: str) -> Dict:
        """
        Generate transcript summary using OpenAI
        
        Args:
            transcript_text: Processed transcript text
            context: Case context
            
        Returns:
            Dictionary with analysis results
        """
        try:
            prompt = TRANSCRIPT_SUMMARY_PROMPT.format(
                context=context or "General deposition testimony",
                transcript=transcript_text[:12000]  # Further truncate for prompt
            )
            
            response = self.client.chat.completions.create(
                model=Config.CHAT_MODEL,
                messages=[
                    {"role": "system", "content": "You are a legal expert specializing in deposition analysis."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            
            content = response.choices[0].message.content
            
            # Try to parse as JSON
            try:
                # Find JSON object in response
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
            
            # Fallback: Parse as text
            return self._parse_text_response(content)
            
        except Exception as e:
            print(f"❌ Error generating summary: {str(e)}")
            return {
                "executive_summary": "Error generating summary",
                "key_topics": [],
                "critical_admissions": [],
                "contradictions": [],
                "evidence_mentioned": [],
                "follow_up_areas": []
            }
    
    def _extract_key_quotes(self, transcript_text: str) -> Dict:
        """
        Extract key quotes from transcript
        
        Args:
            transcript_text: Transcript text
            
        Returns:
            Dictionary with quotes
        """
        try:
            prompt = TRANSCRIPT_QUOTE_EXTRACTION_PROMPT.format(
                transcript=transcript_text[:8000]
            )
            
            response = self.client.chat.completions.create(
                model=Config.CHAT_MODEL,
                messages=[
                    {"role": "system", "content": "You extract key quotes from legal testimony."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
            )
            
            content = response.choices[0].message.content
            
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return {"quotes": []}
                
        except Exception as e:
            print(f"❌ Error extracting quotes: {str(e)}")
            return {"quotes": []}
    
    def _assess_credibility(self, transcript_text: str, context: str) -> str:
        """
        Assess witness credibility
        
        Args:
            transcript_text: Transcript text
            context: Case context
            
        Returns:
            Credibility assessment text
        """
        try:
            prompt = CREDIBILITY_ASSESSMENT_PROMPT.format(
                transcript=transcript_text[:6000],
                context=context or "General case"
            )
            
            response = self.client.chat.completions.create(
                model=Config.CHAT_MODEL,
                messages=[
                    {"role": "system", "content": "You assess witness credibility in legal proceedings."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"❌ Error assessing credibility: {str(e)}")
            return "Unable to assess credibility due to analysis error."
    
    def _parse_text_response(self, text: str) -> Dict:
        """
        Parse text response into structured data
        
        Args:
            text: Response text from OpenAI
            
        Returns:
            Structured dictionary
        """
        result = {
            "executive_summary": "",
            "key_topics": [],
            "critical_admissions": [],
            "contradictions": [],
            "evidence_mentioned": [],
            "follow_up_areas": [],
            "testimony_strengths": [],
            "testimony_weaknesses": []
        }
        
        # Simple parsing logic
        lines = text.split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            
            if not line:
                continue
                
            # Detect section headers
            if 'executive summary' in line.lower():
                current_section = 'executive_summary'
                continue
            elif 'key topics' in line.lower():
                current_section = 'key_topics'
                continue
            elif 'critical admissions' in line.lower():
                current_section = 'critical_admissions'
                continue
            elif 'contradictions' in line.lower():
                current_section = 'contradictions'
                continue
            elif 'evidence' in line.lower():
                current_section = 'evidence_mentioned'
                continue
            elif 'follow-up' in line.lower():
                current_section = 'follow_up_areas'
                continue
            elif 'strengths' in line.lower():
                current_section = 'testimony_strengths'
                continue
            elif 'weaknesses' in line.lower():
                current_section = 'testimony_weaknesses'
                continue
            
            # Add content to current section
            if current_section:
                if current_section == 'executive_summary':
                    result[current_section] += line + ' '
                elif line.startswith(('-', '•', '*')) or line[0].isdigit() and '.' in line[:3]:
                    # List item
                    clean_line = re.sub(r'^[-•*\d.]+\s*', '', line)
                    if clean_line:
                        result[current_section].append(clean_line)
        
        # Clean up executive summary
        result['executive_summary'] = result['executive_summary'].strip()
        
        return result
    
    def _extract_text_from_pdf(self, pdf_content: bytes) -> str:
        """
        Extract text from PDF file
        """
        tmp_path = None
        try:
            # 1) Write to temp file, then close it
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp_file:
                tmp_file.write(pdf_content)
                tmp_file.flush()
                tmp_path = tmp_file.name   # save path

            # 2) Reopen for reading (file is now closed from previous with)
            text = ""
            with open(tmp_path, 'rb') as f:
                pdf_reader = PyPDF2.PdfReader(f)
                for page in pdf_reader.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"

            print(f"✅ Extracted text from PDF (length {len(text)} chars)")
            return text

        except Exception as e:
            raise Exception(f"Error extracting text from PDF: {str(e)}")
        finally:
            # 3) Now it's safe to delete
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except PermissionError as pe:
                    # Optional: log instead of crashing on cleanup
                    print(f"⚠️ Could not delete temp PDF {tmp_path}: {pe}")

    
    def _extract_text_from_docx(self, docx_content: bytes) -> str:
        """
        Extract text from DOCX file
        """
        tmp_path = None
        try:
            # 1) Write to temp file, then close it
            with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as tmp_file:
                tmp_file.write(docx_content)
                tmp_file.flush()
                tmp_path = tmp_file.name

            # 2) Use python-docx on the closed file
            doc = docx.Document(tmp_path)
            text = "\n".join(p.text for p in doc.paragraphs)

            return text

        except Exception as e:
            raise Exception(f"Error extracting text from DOCX: {str(e)}")
        finally:
            # 3) Safe cleanup
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except PermissionError as pe:
                    print(f"⚠️ Could not delete temp DOCX {tmp_path}: {pe}")

    
    def _estimate_pages(self, text: str) -> int:
        """
        Estimate page count based on text length
        
        Args:
            text: Transcript text
            
        Returns:
            Estimated page count
        """
        # Assume ~2500 characters per page
        return max(1, len(text) // 2500)
    
    def _estimate_duration(self, text: str) -> str:
        """
        Estimate deposition duration based on content
        
        Args:
            text: Transcript text
            
        Returns:
            Estimated duration string
        """
        word_count = len(text.split())
        
        if word_count < 3000:
            return "30-60 minutes"
        elif word_count < 6000:
            return "1-2 hours"
        elif word_count < 12000:
            return "2-3 hours"
        else:
            return "3+ hours"

# Create singleton instance
transcript_service = TranscriptService()