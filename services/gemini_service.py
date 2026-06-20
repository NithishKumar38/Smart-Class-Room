"""
services/gemini_service.py
==========================
Gemini AI integration layer for the AI Classroom Co-Pilot.

Provides:
  - generate_concept_explanation() — Hinglish explanation with Mermaid diagram
  - generate_quiz()               — JSON quiz with MCQs

Uses the new google-genai SDK (successor to google-generativeai).
Implements retry logic via tenacity for robust production use.

Author: AI Classroom Co-Pilot Team
"""

import os
import logging
from pathlib import Path
from typing import Optional

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)
from google import genai
from google.genai import types

# ---------------------------------------------------------------------------
# Bootstrap
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Sync st.secrets → os.environ (works on Streamlit Cloud)
try:
    import streamlit as st
    for _k, _v in st.secrets.items():
        if _k not in os.environ:
            os.environ[_k] = str(_v)
except Exception:
    pass
logger = logging.getLogger(__name__)

# Model identifier for Gemini 2.5 Flash
GEMINI_MODEL = "gemini-2.5-flash"

# Path to prompt templates
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


# ---------------------------------------------------------------------------
# Client Initialisation
# ---------------------------------------------------------------------------

def _get_client() -> genai.Client:
    """
    Initialise and return the Gemini API client.

    Reads GEMINI_API_KEY from environment variables.
    Raises ValueError if key is missing.
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key or api_key == "your_gemini_api_key_here":
        raise ValueError(
            "GEMINI_API_KEY is not set. "
            "Please copy .env.example to .env and add your API key."
        )
    return genai.Client(api_key=api_key)


# ---------------------------------------------------------------------------
# Prompt Loader
# ---------------------------------------------------------------------------

def _load_prompt(filename: str) -> str:
    """
    Load a prompt template from the prompts/ directory.

    Args:
        filename: Prompt file name (e.g., 'concept_prompt.txt').

    Returns:
        Raw prompt string.

    Raises:
        FileNotFoundError if the prompt file does not exist.
    """
    path = PROMPTS_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Retry Decorator
# ---------------------------------------------------------------------------

def _gemini_retry():
    """
    Tenacity retry decorator configured for Gemini API calls.

    Retries up to 3 times with exponential backoff (2s, 4s, 8s).
    Logs each retry attempt.
    """
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=10),
        retry=retry_if_exception_type(Exception),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )


# ---------------------------------------------------------------------------
# Core Generation Functions
# ---------------------------------------------------------------------------

@_gemini_retry()
def generate_concept_explanation(
    topic: str,
    grade_level: int = 6,
) -> dict:
    """
    Generate a Hinglish concept explanation with Mermaid diagram.

    Uses the concept_prompt.txt template and Gemini 2.5 Flash.

    Args:
        topic:       The educational topic to explain.
        grade_level: Class level for age-appropriate language (1–12).

    Returns:
        Dict with keys:
          - 'explanation' (str): Full formatted explanation text.
          - 'mermaid_code' (str | None): Extracted Mermaid diagram code.
          - 'raw_response' (str): Raw LLM output.
          - 'topic' (str): Original topic.
          - 'grade_level' (int): Grade level used.

    Raises:
        ValueError: If API key is missing.
        Exception:  On API failure after all retries.
    """
    if not topic or not topic.strip():
        raise ValueError("Topic cannot be empty.")

    # Load and fill prompt template
    prompt_template = _load_prompt("concept_prompt.txt")
    prompt = prompt_template.replace("{topic}", topic.strip())
    prompt = prompt.replace("{grade_level}", str(grade_level))

    logger.info("Generating explanation for topic='%s', grade=%d", topic, grade_level)

    client = _get_client()
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.7,
            max_output_tokens=1500,
        ),
    )

    raw_text = response.text or ""

    # Extract Mermaid diagram code from response
    mermaid_code = _extract_mermaid(raw_text)

    # Remove mermaid block from display text for clean rendering
    display_text = _strip_mermaid_block(raw_text)

    return {
        "explanation": display_text.strip(),
        "mermaid_code": mermaid_code,
        "raw_response": raw_text,
        "topic": topic,
        "grade_level": grade_level,
    }


@_gemini_retry()
def generate_quiz(
    topic: str,
    num_questions: int = 5,
    grade_level: int = 6,
) -> dict:
    """
    Generate a multiple-choice quiz in validated JSON format.

    Uses the quiz_prompt.txt template and Gemini 2.5 Flash.

    Args:
        topic:         The quiz subject.
        num_questions: Number of MCQ questions to generate (1–15).
        grade_level:   Class level for difficulty calibration.

    Returns:
        Dict with keys:
          - 'quiz_data' (dict): Parsed quiz JSON with title and questions.
          - 'raw_response' (str): Raw LLM output.
          - 'success' (bool): Whether parsing succeeded.
          - 'error' (str | None): Error message if parsing failed.

    Raises:
        ValueError: If inputs are invalid.
        Exception:  On API failure after all retries.
    """
    if not topic or not topic.strip():
        raise ValueError("Topic cannot be empty.")

    # Clamp question count to safe range
    num_questions = max(1, min(15, num_questions))

    # Load and fill prompt template
    prompt_template = _load_prompt("quiz_prompt.txt")
    prompt = prompt_template.replace("{topic}", topic.strip())
    prompt = prompt.replace("{num_questions}", str(num_questions))
    prompt = prompt.replace("{grade_level}", str(grade_level))

    logger.info(
        "Generating quiz: topic='%s', questions=%d, grade=%d",
        topic, num_questions, grade_level,
    )

    client = _get_client()
    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.5,          # Lower temp for consistent JSON structure
            max_output_tokens=4000,
        ),
    )

    raw_text = response.text or ""

    # Parse the JSON response
    from utils.helpers import safe_json_parse, validate_quiz_json

    quiz_data = safe_json_parse(raw_text)

    if quiz_data is None:
        logger.error("Quiz JSON parse failed. Raw: %.300s", raw_text)
        return {
            "quiz_data": None,
            "raw_response": raw_text,
            "success": False,
            "error": "Gemini returned invalid JSON. Please try again.",
        }

    is_valid, error_msg = validate_quiz_json(quiz_data)
    if not is_valid:
        logger.warning("Quiz JSON schema invalid: %s", error_msg)
        return {
            "quiz_data": quiz_data,
            "raw_response": raw_text,
            "success": False,
            "error": f"Quiz structure issue: {error_msg}",
        }

    return {
        "quiz_data": quiz_data,
        "raw_response": raw_text,
        "success": True,
        "error": None,
    }


# ---------------------------------------------------------------------------
# Private Helpers
# ---------------------------------------------------------------------------

def _extract_mermaid(text: str) -> Optional[str]:
    """
    Extract Mermaid diagram code from the LLM response.

    Looks for content between [MERMAID_START] and [MERMAID_END] tags.

    Args:
        text: Raw LLM response string.

    Returns:
        Mermaid code string or None if not found.
    """
    import re
    pattern = r"\[MERMAID_START\](.*?)\[MERMAID_END\]"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    if match:
        code = match.group(1).strip()
        return code if code else None
    return None


def _strip_mermaid_block(text: str) -> str:
    """
    Remove the MERMAID_START/END block from display text.

    Args:
        text: Raw LLM response string.

    Returns:
        Text with Mermaid block removed.
    """
    import re
    return re.sub(
        r"\[MERMAID_START\].*?\[MERMAID_END\]",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    ).strip()


def check_api_key() -> tuple[bool, str]:
    """
    Validate that the Gemini API key is configured.

    Returns:
        Tuple (is_valid: bool, message: str).
    """
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return False, "GEMINI_API_KEY is not set in your .env file."
    if api_key == "your_gemini_api_key_here":
        return False, "Please replace the placeholder with your actual Gemini API key."
    return True, "API key is configured."
