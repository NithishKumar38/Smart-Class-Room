"""
utils/helpers.py
================
Shared utility functions used across the AI Classroom Co-Pilot application.
Provides input parsing, JSON cleaning, validation, and formatting helpers.

Author: AI Classroom Co-Pilot Team
"""

import re
import json
import logging
from typing import Optional

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Grade / Class Extraction
# ---------------------------------------------------------------------------

# Regex patterns to extract class/grade level from natural language
GRADE_PATTERNS = [
    r"class\s*(\d+)",          # "class 6", "class6"
    r"grade\s*(\d+)",          # "grade 5"
    r"kaksha\s*(\d+)",         # Hindi: kaksha
    r"(\d+)\s*(?:th|st|nd|rd)\s*class",  # "6th class"
    r"standard\s*(\d+)",       # "standard 8"
]


def parse_grade_from_text(text: str) -> int:
    """
    Extract class/grade level from a natural language string.

    Supports English and basic Hinglish patterns.
    Defaults to grade 6 if no grade is found.

    Args:
        text: Raw voice/text input from teacher.

    Returns:
        Integer grade level between 1 and 12.
    """
    if not text:
        return 6  # Default to Class 6

    text_lower = text.lower().strip()

    for pattern in GRADE_PATTERNS:
        match = re.search(pattern, text_lower)
        if match:
            grade = int(match.group(1))
            # Clamp to valid school grade range
            return max(1, min(12, grade))

    return 6  # Default fallback


# ---------------------------------------------------------------------------
# JSON Cleaning
# ---------------------------------------------------------------------------

def clean_json_response(raw: str) -> str:
    """
    Strip markdown code fences and extra whitespace from a raw LLM JSON response.

    Gemini sometimes wraps JSON in ```json ... ``` fences even when instructed
    not to. This function handles that gracefully.

    Args:
        raw: Raw string from Gemini API response.

    Returns:
        Clean JSON string ready for json.loads().
    """
    if not raw:
        return "{}"

    # Remove ```json ... ``` or ``` ... ``` fences
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip())

    return cleaned.strip()


# ---------------------------------------------------------------------------
# Quiz JSON Validation
# ---------------------------------------------------------------------------

def validate_quiz_json(data: dict) -> tuple[bool, str]:
    """
    Validate the structure of a quiz JSON object returned by Gemini.

    Args:
        data: Parsed dictionary from Gemini's quiz response.

    Returns:
        Tuple of (is_valid: bool, error_message: str).
        error_message is empty string if valid.
    """
    required_top_keys = {"title", "questions"}
    missing_top = required_top_keys - set(data.keys())
    if missing_top:
        return False, f"Missing top-level keys: {missing_top}"

    questions = data.get("questions", [])
    if not isinstance(questions, list) or len(questions) == 0:
        return False, "Questions list is empty or not a list."

    for i, q in enumerate(questions):
        q_num = i + 1
        if not isinstance(q, dict):
            return False, f"Question {q_num} is not a dict."

        required_q_keys = {"question", "options", "correct_answer"}
        missing_q = required_q_keys - set(q.keys())
        if missing_q:
            return False, f"Question {q_num} missing keys: {missing_q}"

        options = q.get("options", [])
        if not isinstance(options, list) or len(options) != 4:
            return False, f"Question {q_num} must have exactly 4 options."

        correct = q.get("correct_answer", "")
        if correct not in options:
            # Try to find by prefix matching (A), B), etc.)
            found = any(opt.startswith(correct[:2]) for opt in options if len(correct) >= 2)
            if not found:
                logger.warning("Q%d correct_answer '%s' not in options list.", q_num, correct)

    return True, ""


# ---------------------------------------------------------------------------
# Text Formatting Helpers
# ---------------------------------------------------------------------------

def format_duration(seconds: float) -> str:
    """
    Format a duration in seconds to a human-readable string.

    Args:
        seconds: Duration in seconds.

    Returns:
        Formatted string like "1m 23s" or "45s".
    """
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes, secs = divmod(seconds, 60)
    return f"{minutes}m {secs}s"


def truncate_text(text: str, max_length: int = 100) -> str:
    """
    Truncate text to a maximum length with an ellipsis.

    Args:
        text: Input string.
        max_length: Maximum number of characters.

    Returns:
        Truncated string.
    """
    if not text:
        return ""
    return text[:max_length] + "..." if len(text) > max_length else text


def extract_topic_from_command(command: str) -> str:
    """
    Extract the core topic from a teacher's voice command.

    Strips common command prefixes to get the actual subject.

    Examples:
        "Explain photosynthesis for Class 6" → "photosynthesis"
        "Create a quiz on water cycle" → "water cycle"
        "Generate questions about fractions" → "fractions"

    Args:
        command: Raw teacher voice/text command.

    Returns:
        Extracted topic string.
    """
    if not command:
        return ""

    command_lower = command.lower().strip()

    # Patterns to strip from the beginning
    strip_prefixes = [
        r"^explain\s+",
        r"^create\s+(?:a\s+)?(?:\d+[- ]question\s+)?quiz\s+(?:on|about)\s+",
        r"^generate\s+(?:a\s+)?(?:quiz|questions?)\s+(?:on|about)\s+",
        r"^ask\s+(?:students?\s+)?(?:\d+\s+)?(?:mcqs?|questions?)\s+(?:on|about)\s+",
        r"^(?:give\s+)?(?:me\s+)?(?:a\s+)?quiz\s+(?:on|about)\s+",
        r"^(?:tell|teach)\s+(?:me\s+)?about\s+",
        r"^(?:what\s+is|what\s+are)\s+",
        r"^(?:batao|samjhao|explain)\s+",  # Hinglish
    ]

    cleaned = command
    for pattern in strip_prefixes:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

    # Strip trailing "for class X" or "in hinglish" suffixes
    cleaned = re.sub(r"\s+(?:for|ke\s+liye)\s+class\s+\d+\s*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+in\s+(?:hinglish|hindi|english|simple)\s*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+with\s+examples?\s*$", "", cleaned, flags=re.IGNORECASE)

    return cleaned.strip().title() if cleaned.strip() else command.strip()


def safe_json_parse(raw: str) -> Optional[dict]:
    """
    Safely parse a JSON string, returning None on failure.

    Args:
        raw: Raw JSON string (possibly with markdown fences).

    Returns:
        Parsed dict or None if parsing fails.
    """
    try:
        cleaned = clean_json_response(raw)
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError) as e:
        logger.error("JSON parse failed: %s | Raw: %.200s", e, raw)
        return None
