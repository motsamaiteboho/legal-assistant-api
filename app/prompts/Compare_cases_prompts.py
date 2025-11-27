ADVANCED_COMPARISON_SYSTEM_PROMPT = """
You are a South African legal research assistant who specialises in analysing and 
comparing multiple judgments.

Your task is to produce a structured, professional comparison of the supplied cases.

OUTPUT FORMAT (IMPORTANT):

- You MUST return valid HTML ONLY (no <html>, <head> or <body> tags).
- Use <h5> for section headings.
- Use <p> for paragraphs.
- Use <ul><li> for bullet lists where useful.
- Do NOT include any inline styles.

CONTENT RULES:

1. Provide a short introductory paragraph.
2. Then structure the comparison into the following sections, each with its own <h5> heading:
   - "Common factual patterns"
   - "Legal issues: overlaps and differences"
   - "Comparison of reasoning (ratio decidendi)"
   - "Outcomes and practical implications"
   - "Precedential value and how to use these cases"

3. Base everything ONLY on the extracted summaries (facts, issues, ratio, outcome, precedents).
   Do not introduce external cases or citations.
4. Write in professional South African legal style.
"""

def build_advanced_comparison_prompt(cases: list[dict]) -> str:
    case_blocks = []
    for c in cases:
        block = f"""
Case {c['id']} – {c['fileName']}:
Facts: {c['facts']}
Issues: {', '.join(c['issues']) if c['issues'] else 'None extracted'}
Ratio: {c['ratio']}
Outcome: {c.get('outcome', 'Not extracted')}
Precedents count: {len(c.get('precedents', []))}
"""
        case_blocks.append(block.strip())

    joined_cases = "\n\n".join(case_blocks)

    return f"""
{ADVANCED_COMPARISON_SYSTEM_PROMPT}

---
Extracted Case Summaries:
{joined_cases}

Generate the HTML comparison now.
"""
