"""
services/text_to_speech.py
===========================
Text-to-Speech service using gTTS (Google Text-to-Speech).

Converts Hinglish/Hindi text to MP3 audio files.
Audio files are saved to assets/audio/ with UUID filenames.

Author: AI Classroom Co-Pilot Team
"""

import os
import uuid
import logging
import time
import re
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

AUDIO_DIR = Path(__file__).parent.parent / "assets" / "audio"
TTS_LANGUAGE = os.getenv("TTS_LANGUAGE", "hi")
CLEANUP_HOURS = int(os.getenv("AUDIO_CLEANUP_HOURS", "1"))


# ---------------------------------------------------------------------------
# Core TTS Function
# ---------------------------------------------------------------------------

def generate_speech(text: str, lang: Optional[str] = None, slow: bool = False) -> dict:
    """
    Convert text to speech and save as an MP3 file.

    Args:
        text: Text to convert to speech.
        lang: BCP-47 language code ('hi', 'en'). Defaults to env TTS_LANGUAGE.
        slow: If True, speak slowly.

    Returns:
        Dict with: audio_path, audio_bytes, success, error.
    """
    if not text or not text.strip():
        return _error_response("No text provided for speech generation.")

    AUDIO_DIR.mkdir(parents=True, exist_ok=True)
    _cleanup_old_files()
    speech_lang = lang or TTS_LANGUAGE

    try:
        from gtts import gTTS

        clean_text = _prepare_text_for_tts(text)
        logger.info("Generating TTS: lang=%s, length=%d chars", speech_lang, len(clean_text))

        tts = gTTS(text=clean_text, lang=speech_lang, slow=slow)

        filename = f"tts_{uuid.uuid4().hex[:12]}.mp3"
        output_path = AUDIO_DIR / filename
        tts.save(str(output_path))
        audio_bytes = output_path.read_bytes()

        logger.info("TTS saved: %s (%d bytes)", output_path.name, len(audio_bytes))
        return {
            "audio_path": str(output_path),
            "audio_bytes": audio_bytes,
            "success": True,
            "error": None,
        }

    except ImportError:
        return _error_response("gTTS not installed. Run: pip install gTTS")
    except Exception as e:
        logger.error("TTS failed: %s", e, exc_info=True)
        return _error_response(f"Audio generation failed: {str(e)}")


def generate_speech_for_quiz_question(question_text: str, question_number: int, options: list) -> dict:
    """Generate TTS audio for a quiz question including all options."""
    options_text = " ... ".join(options)
    full_text = f"Sawaal number {question_number}. {question_text} Options hain: {options_text}"
    return generate_speech(full_text, lang="hi")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _prepare_text_for_tts(text: str) -> str:
    """Clean text for TTS: strip markdown, emojis, mermaid blocks, truncate."""
    text = re.sub(r"[#*`•►]", " ", text)
    text = re.sub(r"[\U0001F300-\U0001FFFF\U00002600-\U000027BF]", " ", text)
    text = re.sub(r"\[MERMAID_START\].*?\[MERMAID_END\]", "", text, flags=re.DOTALL)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > 1200:
        text = text[:1200].rsplit(" ", 1)[0] + "..."
    return text


def _cleanup_old_files() -> int:
    """Delete MP3 files older than CLEANUP_HOURS."""
    if not AUDIO_DIR.exists():
        return 0
    cutoff = time.time() - (CLEANUP_HOURS * 3600)
    deleted = 0
    for f in AUDIO_DIR.glob("tts_*.mp3"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink()
                deleted += 1
        except OSError:
            pass
    return deleted


def _error_response(message: str) -> dict:
    logger.warning("TTS error: %s", message)
    return {"audio_path": None, "audio_bytes": None, "success": False, "error": message}


def is_gtts_available() -> bool:
    try:
        from gtts import gTTS  # noqa: F401
        return True
    except ImportError:
        return False
