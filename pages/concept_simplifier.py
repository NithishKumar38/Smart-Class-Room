"""
pages/concept_simplifier.py
============================
Live Concept Simplification page for the AI Classroom Co-Pilot.

Exported as render_concept_page() to be called from app.py router.
All Streamlit UI code lives inside this function to avoid
set_page_config conflicts with the main app.

Author: AI Classroom Co-Pilot Team
"""

import re
import sys
import logging
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from services.gemini_service import generate_concept_explanation, check_api_key
from services.text_to_speech import generate_speech, is_gtts_available
from services.speech_to_text import transcribe_audio, is_whisper_available
from services.diagram_generator import render_mermaid_html, extract_mermaid, render_diagram_with_fallback
from database.db import save_concept_session
from utils.helpers import parse_grade_from_text, extract_topic_from_command

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Page-specific CSS
# ---------------------------------------------------------------------------

CONCEPT_CSS = """
<style>
.concept-card {
    background: linear-gradient(135deg, #1e3a5f 0%, #0d2137 100%);
    border: 1px solid rgba(74, 144, 217, 0.4);
    border-radius: 16px;
    padding: 28px;
    margin: 12px 0;
    color: #e8f4fd;
    line-height: 1.8;
}
.topic-badge {
    display: inline-block;
    background: rgba(74, 144, 217, 0.25);
    border: 1px solid rgba(74,144,217,0.5);
    color: #7ec8f7;
    padding: 4px 14px;
    border-radius: 20px;
    font-size: 0.85rem;
    font-weight: 600;
    margin-bottom: 16px;
}
.grade-badge {
    display: inline-block;
    background: rgba(245, 166, 35, 0.2);
    border: 1px solid rgba(245,166,35,0.5);
    color: #f5c842;
    padding: 4px 14px;
    border-radius: 20px;
    font-size: 0.85rem;
    font-weight: 600;
    margin-left: 8px;
    margin-bottom: 16px;
}
.explanation-text {
    font-size: 1.05rem;
    color: #dbeeff;
    white-space: pre-wrap;
    word-break: break-word;
}
</style>
"""


# ---------------------------------------------------------------------------
# Session State Init
# ---------------------------------------------------------------------------

def _init_state():
    defaults = {
        "cs_topic": "",
        "cs_grade": 6,
        "cs_result": None,
        "cs_audio_bytes": None,
        "cs_loading": False,
        "cs_history": [],
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


# ---------------------------------------------------------------------------
# Public Entry Point
# ---------------------------------------------------------------------------

def render_concept_page():
    """Render the Concept Simplifier page. Called from app.py router."""

    _init_state()
    st.markdown(CONCEPT_CSS, unsafe_allow_html=True)

    st.markdown("## 📚 Live Concept Simplifier")
    st.markdown(
        "Speak or type a topic — AI will automatically generate a "
        "**simple Hinglish explanation** with a diagram and audio."
    )

    # API key check
    api_ok, api_msg = check_api_key()
    if not api_ok:
        st.error(f"🔑 {api_msg}", icon="🚫")
        return

    st.divider()

    # ── Input Section ───────────────────────────────────────────────────────
    col_input, col_settings = st.columns([3, 1])

    with col_settings:
        st.markdown("**⚙️ Settings**")
        grade_level = st.selectbox(
            "Class / Grade",
            options=list(range(1, 13)),
            index=5,
            key="cs_grade_selector",
        )
        tts_enabled = st.toggle("🔊 Read aloud", value=True, key="cs_tts_toggle")

    with col_input:
        st.markdown("**🎤 Speak or Type Your Topic:**")

        # Microphone recording widget
        if is_whisper_available():
            try:
                from audio_recorder_streamlit import audio_recorder
                audio_bytes_mic = audio_recorder(
                    text="",
                    recording_color="#e84040",
                    neutral_color="#4A90D9",
                    icon_name="microphone",
                    icon_size="2x",
                    key="cs_mic_recorder",
                    pause_threshold=2.5,
                    sample_rate=16000,
                )
                if audio_bytes_mic:
                    with st.spinner("🎧 Listening to your voice..."):
                        stt_result = transcribe_audio(audio_bytes_mic)
                    if stt_result["success"] and stt_result["text"]:
                        st.session_state.cs_topic = stt_result["text"]
                        st.success(f"✅ Heard: *{stt_result['text']}*")
                    elif not stt_result["success"]:
                        st.warning(f"⚠️ {stt_result['error']}")
            except Exception as mic_err:
                logger.debug("Mic widget error: %s", mic_err)
                st.info("🎤 Microphone widget unavailable. Please use the text input below.")
        else:
            st.info("💡 Install `faster-whisper` to enable voice input. Text input is available below.")

        # Text fallback input
        topic_input = st.text_input(
            "Enter Topic / Concept:",
            value=st.session_state.cs_topic,
            placeholder="e.g., Explain photosynthesis for Class 6, explain fractions with examples...",
            key="cs_topic_text_input",
        )

    # Override grade if mentioned in the command text
    if topic_input:
        detected = parse_grade_from_text(topic_input)
        if detected != 6:
            grade_level = detected

    generate_btn = st.button(
        "✨ Generate Explanation",
        type="primary",
        disabled=not topic_input.strip(),
        key="cs_explain_btn",
    )

    # ── Processing Pipeline ─────────────────────────────────────────────────
    if generate_btn and topic_input.strip():
        clean_topic = extract_topic_from_command(topic_input)
        st.session_state.cs_result = None
        st.session_state.cs_audio_bytes = None

        progress = st.progress(0, text="Processing your request...")
        try:
            progress.progress(20, text="🧠 Requesting explanation from Gemini...")
            result = generate_concept_explanation(clean_topic, grade_level)
            progress.progress(60, text="📝 Explanation ready!")

            if result and result.get("explanation"):
                st.session_state.cs_result = result
                st.session_state.cs_grade = grade_level

                if tts_enabled and is_gtts_available():
                    progress.progress(75, text="🔊 Generating audio...")
                    tts_result = generate_speech(result["explanation"], lang="hi")
                    if tts_result["success"]:
                        st.session_state.cs_audio_bytes = tts_result["audio_bytes"]

                progress.progress(90, text="💾 Saving...")
                session_id = st.session_state.get("session_id", "unknown")
                save_concept_session(
                    session_id=session_id,
                    topic=clean_topic,
                    grade_level=grade_level,
                    input_text=topic_input,
                    explanation=result["explanation"],
                    has_diagram=bool(result.get("mermaid_code")),
                )

                st.session_state.cs_history.insert(0, {"topic": clean_topic, "grade": grade_level})
                progress.progress(100, text="✅ Done!")
            else:
                st.error("❌ Could not generate explanation. Please try again.")

        except ValueError as ve:
            st.error(f"🔑 {ve}")
        except Exception as e:
            st.error(f"❌ An error occurred: {str(e)}")
            logger.error("Concept error: %s", e, exc_info=True)
        finally:
            progress.empty()

    # ── Results Display ─────────────────────────────────────────────────────
    result = st.session_state.cs_result

    if result:
        st.divider()
        col_exp, col_diag = st.columns([3, 2])

        with col_exp:
            st.markdown("### 📖 Explanation")
            explanation_html = f"""
            <div class="concept-card">
                <div>
                    <span class="topic-badge">📌 {result['topic']}</span>
                    <span class="grade-badge">🎓 Class {st.session_state.cs_grade}</span>
                </div>
                <div class="explanation-text">{result['explanation'].replace(chr(10), '<br>')}</div>
            </div>
            """
            st.markdown(explanation_html, unsafe_allow_html=True)

            if st.session_state.cs_audio_bytes:
                st.markdown("**🔊 Audio Explanation:**")
                st.audio(st.session_state.cs_audio_bytes, format="audio/mp3", autoplay=True)
            elif tts_enabled:
                st.info("🔊 Internet connection required for audio playback (gTTS).")

        with col_diag:
            st.markdown("### 📊 Diagram")
            mermaid_code = result.get("mermaid_code") or extract_mermaid(result.get("raw_response", ""))

            # Extract key points from explanation for SVG fallback
            _raw = result.get("explanation", "")
            _kp_matches = re.findall(r"•\s*(.+)", _raw)
            if not _kp_matches:
                _kp_matches = re.findall(r"\*\*?(.+?)\*\*?", _raw)[:5]
            key_points = [k.strip() for k in _kp_matches[:5]] or [
                "Step 1", "Step 2", "Step 3"
            ]

            diagram_result = render_diagram_with_fallback(
                mermaid_code=mermaid_code,
                topic=result.get("topic", "Topic"),
                key_points=key_points,
            )

            if diagram_result["type"] in ("mermaid", "mermaid_fixed"):
                st.components.v1.html(
                    diagram_result["html"], height=380, scrolling=False
                )
            elif diagram_result["type"] == "svg" and diagram_result["svg"]:
                st.markdown(
                    f'<div style="border-radius:12px; overflow:hidden; background:#0d2137;">'
                    f'{diagram_result["svg"]}</div>',
                    unsafe_allow_html=True,
                )
            else:
                # Level 4 — Streamlit native text flowchart (always works)
                _topic = result.get('topic', 'Topic')
                _steps = key_points[:5]
                st.markdown(
                    f"""
                    <div style="
                        background: linear-gradient(135deg, #1e3a5f 0%, #0d2137 100%);
                        border: 1px solid rgba(74,144,217,0.4);
                        border-radius: 14px;
                        padding: 20px 16px;
                        font-family: 'Segoe UI', sans-serif;
                        text-align: center;
                    ">
                        <div style="
                            background: #4A90D9;
                            color: white;
                            border-radius: 8px;
                            padding: 8px 16px;
                            font-weight: 700;
                            margin: 0 auto 6px auto;
                            max-width: 220px;
                        ">📌 {_topic}</div>
                        {''.join([
                            f'<div style="color:#F5A623;font-size:1.3rem;">↓</div>'
                            f'<div style="background:#1a3a2a;border:1px solid #50C878;'
                            f'border-radius:8px;padding:7px 14px;color:#d4f5e2;'
                            f'font-size:0.92rem;margin:0 auto 4px auto;max-width:220px;">'
                            f'{s}</div>'
                            for s in _steps
                        ])}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        if st.button("🔄 Regenerate", key="cs_regen_btn"):
            st.session_state.cs_result = None
            st.rerun()

    # ── Session History ─────────────────────────────────────────────────────
    if st.session_state.cs_history:
        st.divider()
        st.markdown("### 🕒 Today's Topics")
        for item in st.session_state.cs_history[:5]:
            st.markdown(f"- **{item['topic']}** *(Class {item['grade']})*")
