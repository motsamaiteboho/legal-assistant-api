"""
Prompts for deposition transcript analysis
"""

TRANSCRIPT_SUMMARY_PROMPT = """You are a legal assistant specializing in deposition analysis. 
Analyze the following deposition transcript and provide a comprehensive legal analysis.

CASE CONTEXT:
{context}

TRANSCRIPT TEXT:
{transcript}

Please analyze this deposition transcript and provide the following information:

1. EXECUTIVE SUMMARY (3-4 sentences):
   Provide a concise overview of the witness's key testimony and main points.

2. KEY TOPICS DISCUSSED (list each topic):
   Identify and list the main subjects and legal issues discussed.

3. CRITICAL ADMISSIONS (list each admission):
   Document any admissions made by the witness that could be damaging or helpful to either party.

4. CONTRADICTIONS & INCONSISTENCIES (list each contradiction):
   Note any inconsistencies within the testimony or contradictions with known facts.

5. EVIDENCE & EXHIBITS MENTIONED (list each piece):
   List all documents, exhibits, or evidence referenced during the testimony.

6. AREAS FOR FOLLOW-UP (list each area):
   Identify topics that require further investigation or questioning.

7. KEY TESTIMONY QUOTES (provide 3-5 important quotes with context):
   Extract and quote significant statements that capture the essence of the testimony.

8. WITNESS CREDIBILITY ASSESSMENT (brief analysis):
   Assess the witness's credibility, demeanor, and reliability.

9. TESTIMONY STRENGTHS (list key strengths):
   Identify strengths in the witness's testimony.

10. TESTIMONY WEAKNESSES (list key weaknesses):
    Identify weaknesses or vulnerabilities in the testimony.

Format the response as a JSON object with these exact keys:
- "executive_summary"
- "key_topics" 
- "critical_admissions"
- "contradictions"
- "evidence_mentioned"
- "follow_up_areas"
- "key_quotes" (array of objects with "text" and "context" keys)
- "witness_credibility"
- "testimony_strengths"
- "testimony_weaknesses"
"""

TRANSCRIPT_QUOTE_EXTRACTION_PROMPT = """Extract the 5 most important quotes from this deposition testimony.
Focus on quotes that:
1. Represent key admissions or denials
2. Show contradictions or inconsistencies
3. Reveal important facts or evidence
4. Demonstrate witness demeanor or credibility
5. Are central to the legal issues in the case

For each quote, provide:
- The exact quote text
- Brief context (what was being discussed)
- Why this quote is significant

TRANSCRIPT:
{transcript}

Respond in JSON format:
{{
  "quotes": [
    {{
      "text": "exact quote",
      "context": "brief context",
      "significance": "why this is important"
    }}
  ]
}}
"""

CREDIBILITY_ASSESSMENT_PROMPT = """Assess the credibility of the witness based on this deposition testimony.
Consider:
1. Consistency of testimony
2. Demeanor indicators (evasive, confident, nervous)
3. Knowledge and recall of events
4. Bias or potential motives
5. Corroboration with evidence

TRANSCRIPT:
{transcript}

CONTEXT:
{context}

Provide a brief credibility assessment (2-3 paragraphs) covering:
- Overall credibility rating (High/Medium/Low)
- Key factors affecting credibility
- Specific examples from testimony
- Recommendations for cross-examination
"""

CROSS_EXAMINATION_QUESTIONS_PROMPT = """Based on this deposition transcript, generate a list of cross-examination questions.
Focus on:
1. Weaknesses or inconsistencies in testimony
2. Areas where the witness seemed uncertain
3. Admissions that need to be clarified or emphasized
4. Follow-up on incomplete answers
5. Testing the witness's credibility

TRANSCRIPT SUMMARY:
{summary}

Generate 10-15 targeted cross-examination questions organized by topic.
Format as a JSON object with "questions_by_topic" containing arrays of questions for each key topic.
"""