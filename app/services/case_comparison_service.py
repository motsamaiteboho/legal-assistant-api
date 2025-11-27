from app.prompts.Compare_cases_prompts import build_advanced_comparison_prompt
from langchain_openai import ChatOpenAI
from app.config.config import Config


class CaseComparisonService:
    """Service for performing advanced comparison between extracted case summaries"""

    def __init__(self):
        self.llm = ChatOpenAI(
            model=Config.CHAT_MODEL,
            temperature=Config.TEMPERATURE
        )

    def generate_advanced_comparison(self, cases):
        """Run LLM to generate advanced comparison."""
        case_dicts = [c.dict() for c in cases]
        prompt = build_advanced_comparison_prompt(case_dicts)

        response = self.llm.invoke(prompt)
        return response.content if hasattr(response, "content") else str(response)


# Global instance
case_comparison_service = CaseComparisonService()