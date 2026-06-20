"""
services/speech_to_text.py
===========================
Speech-to-Text service using Faster-Whisper.

Supports Hindi, English, and Hinglish audio input.
Designed for CPU-only classroom computers (base model default).

The model is loaded once and cached to avoid re-loading on every call.
Audio bytes (from audio-recorder-streamlit) are saved to a temp WAV file,
transcribed, and the temp file is cleaned up automatically.

Author: AI Classroom Co-Pilot Team
"""

import os
import logging
import tempfile
import wave
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model Configuration
# ---------------------------------------------------------------------------

# Read model size from environment — default to 'base' for CPU-only machines
WHISPER_MODEL_SIZE = os.getenv("WHISPER_MODEL", "base")

# Supported language codes for detection hints
SUPPORTED_LANGUAGES = {"hi", "en"}    # Hindi, English (Hinglish is handled as Hindi)

# Module-level cached model instance
_whisper_model = None


# ---------------------------------------------------------------------------
# Model Loading (Singleton)
# ---------------------------------------------------------------------------

def _get_whisper_model():
    """
    Load and cache the Faster-Whisper model.

    Uses a module-level singleton so the model is only loaded once
    per application lifecycle, saving ~2–3 seconds on each call.

    Returns:
        Loaded WhisperModel instance.

    Raises:
        ImportError: If faster-whisper is not installed.
        RuntimeError: If model loading fails.
    """
    global _whisper_model

    if _whisper_model is not None:
        return _whisper_model

    try:
        from faster_whisper import WhisperModel
        logger.info("Loading Whisper model: %s (CPU mode)", WHISPER_MODEL_SIZE)

        _whisper_model = WhisperModel(
            model_size_or_path=WHISPER_MODEL_SIZE,
            device="cpu",
            compute_type="int8",   # int8 is fastest on CPU with minimal accuracy loss
        )
        logger.info("Whisper model loaded successfully.")
        return _whisper_model

    except ImportError as e:
        logger.error("faster-whisper not installed: %s", e)
        raise ImportError(
            "faster-whisper is not installed. Run: pip install faster-whisper"
        ) from e
    except Exception as e:
        logger.error("Failed to load Whisper model '%s': %s", WHISPER_MODEL_SIZE, e)
        raise RuntimeError(f"Whisper model load failed: {e}") from e


# ---------------------------------------------------------------------------
# Core Transcription Function
# ---------------------------------------------------------------------------

def transcribe_audio(
    audio_bytes: bytes,
    language_hint: Optional[str] = None,
) -> dict:
    """
    Transcribe audio bytes to text using Faster-Whisper.

    Supports Hindi, English, and Hinglish audio.
    Uses automatic language detection if no hint is provided.

    Args:
        audio_bytes:   Raw audio bytes from browser microphone recording.
                       Expected format: WebM or WAV bytes from streamlit widget.
        language_hint: Optional ISO language code ('hi' or 'en').
                       If None, Whisper auto-detects the language.

    Returns:
        Dict with keys:
          - 'text' (str): Transcribed text, cleaned and stripped.
          - 'language' (str): Detected language code.
          - 'confidence' (float): Average segment probability (0.0–1.0).
          - 'success' (bool): Whether transcription succeeded.
          - 'error' (str | None): Error message if failed.

    Note:
        Audio bytes are written to a temporary file and deleted after transcription.
    """
    if not audio_bytes:
        return _error_response("No audio data received.")

    tmp_path = None
    try:
        # Write audio bytes to a temp file for Whisper to read
        with tempfile.NamedTemporaryFile(
            suffix=".wav",
            delete=False,
            prefix="classroom_audio_",
        ) as tmp_file:
            tmp_path = tmp_file.name
            tmp_file.write(audio_bytes)

        logger.info("Transcribing audio file: %s (%d bytes)", tmp_path, len(audio_bytes))

        model = _get_whisper_model()

        # Set language — None triggers auto-detection
        transcribe_lang = language_hint if language_hint in SUPPORTED_LANGUAGES else None

        segments, info = model.transcribe(
            tmp_path,
            language=transcribe_lang,
            beam_size=5,
            best_of=5,
            temperature=0.0,        # Greedy decoding for determinism
            vad_filter=True,        # Filter out silence/noise
            vad_parameters={
                "min_silence_duration_ms": 500,
            },
            word_timestamps=False,  # Not needed, saves processing time
        )

        # Collect all segment texts
        segment_list = list(segments)
        if not segment_list:
            return _error_response(
                "No speech detected. Please speak clearly near the microphone."
            )

        full_text = " ".join(seg.text.strip() for seg in segment_list)
        avg_confidence = sum(
            getattr(seg, "avg_logprob", 0) for seg in segment_list
        ) / len(segment_list) if segment_list else 0.0

        detected_lang = info.language if hasattr(info, "language") else "unknown"
        logger.info(
            "Transcription complete: lang=%s, text='%s'",
            detected_lang, full_text[:80],
        )

        return {
            "text": _clean_transcript(full_text),
            "language": detected_lang,
            "confidence": round(min(1.0, max(0.0, avg_confidence + 1)), 2),
            "success": True,
            "error": None,
        }

    except ImportError as e:
        return _error_response(f"STT library not available: {e}")
    except Exception as e:
        logger.error("Transcription error: %s", e, exc_info=True)
        return _error_response(f"Transcription failed: {str(e)}")
    finally:
        # Always clean up the temp file
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


# ---------------------------------------------------------------------------
# Private Helpers
# ---------------------------------------------------------------------------

def _clean_transcript(text: str) -> str:
    """
    Clean raw Whisper transcript output.

    Removes repeated phrases, excessive whitespace, and known
    hallucination artifacts from Whisper.

    Args:
        text: Raw transcript string.

    Returns:
        Cleaned transcript string.
    """
    if not text:
        return ""

    import re

    # Remove common Whisper hallucinations
    hallucinations = [
        r"\[Music\]", r"\[Applause\]", r"\[BLANK_AUDIO\]",
        r"\[music\]", r"\[applause\]", r"\(Music\)",
    ]
    for pattern in hallucinations:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    # Normalize whitespace
    text = " ".join(text.split())

    return text.strip()


def _error_response(message: str) -> dict:
    """
    Build a standardised error response dict.

    Args:
        message: Human-readable error description.

    Returns:
        Error response dict.
    """
    logger.warning("STT error: %s", message)
    return {
        "text": "",
        "language": "unknown",
        "confidence": 0.0,
        "success": False,
        "error": message,
    }


def is_whisper_available() -> bool:
    """
    Check if faster-whisper is installed and importable.

    Returns:
        True if available, False otherwise.
    """
    try:
        import faster_whisper  # noqa: F401
        return True
    except ImportError:
        return False
