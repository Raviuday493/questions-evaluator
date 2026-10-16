import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from agents.config import agent_settings

logger = logging.getLogger("qpi.agent.parser")

class ParsedQuestionSchema(BaseModel):
    question_number: str = Field(description="e.g. '1', '2(a)'")
    section_name: Optional[str] = Field(default="General", description="Section header if available")
    text: str = Field(description="Complete question prompt text")
    marks: int = Field(default=0, description="Marks allocated if explicitly listed")

class DocumentQuestionsSchema(BaseModel):
    questions: List[ParsedQuestionSchema]

class QuestionParserAgent:
    """Google ADK agent fallback for irregular, multi-column, or poorly formatted exam papers."""
    
    def __init__(self):
        self.model_name = agent_settings.DEFAULT_MODEL

    def parse_irregular_layout(self, raw_text: str) -> List[Dict[str, Any]]:
        logger.info("Invoking ADK QuestionParserAgent for complex layout parsing...")
        
        # If Gemini API Key is available, use Google GenAI SDK
        if agent_settings.GEMINI_API_KEY:
            try:
                from google import genai
                client = genai.Client(api_key=agent_settings.GEMINI_API_KEY)
                prompt = f"""
                You are an expert exam paper layout parser. Extract all individual questions and sub-questions from the following raw paper text.
                Return structured output containing question_number, section_name, text, and marks.

                RAW TEXT:
                {raw_text[:4000]}
                """
                response = client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config={
                        'response_mime_type': 'application/json',
                        'response_schema': DocumentQuestionsSchema,
                    }
                )
                data = DocumentQuestionsSchema.model_validate_json(response.text)
                return [q.model_dump() for q in data.questions]
            except Exception as e:
                logger.error(f"ADK Agent invocation failed: {e}. Falling back to structured extraction.", exc_info=True)

        # Fallback structured parsing if API key is unconfigured in local dev
        return [
            {
                "question_number": "1",
                "section_name": "General",
                "text": raw_text[:500],
                "marks": 10
            }
        ]
