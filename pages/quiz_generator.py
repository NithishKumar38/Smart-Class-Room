"""
pages/quiz_generator.py
========================
Voice-Triggered Quiz Generator page for the AI Classroom Co-Pilot.

Exported as render_quiz_page() to be called from app.py router.

Author: AI Classroom Co-Pilot Team
"""

import sys
import logging
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from services.gemini_service import generate_quiz, check_api_key
from services.text_to_speech import generate_speech_for_quiz_question, is_gtts_available
from services.speech_to_text import transcribe_audio, is_whisper_available
from database.db import save_quiz_result
from utils.helpers import parse_grade_from_text, extract_topic_from_command

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Page-specific CSS
# ---------------------------------------------------------------------------

QUIZ_CSS = """
<style>
.quiz-header {
    background: linear-gradient(135deg, #1a3a2a 0%, #0d2118 100%);
    border: 1px solid rgba(80, 200, 120, 0.35);
    border-radius: 16px;
    padding: 24px 28px;
    margin-bottom: 20px;
    color: #d4f5e2;
}
.question-card {
    background: linear-gradient(135deg, #1e3a5f 0%, #0d2137 100%);
    border: 1px solid rgba(74, 144, 217, 0.35);
    border-radius: 14px;
    padding: 22px 26px;
    margin: 12px 0;
}
.question-num {
    color: #F5A623;
    font-size: 0.75rem;
    font-weight: 800;
    letter-spacing: 2px;
    text-transform: uppercase;
}
.question-text {
    color: #dbeeff;
    font-size: 1.1rem;
    font-weight: 600;
    margin: 8px 0 16px 0;
}
.score-card {
    background: linear-gradient(135deg, #1a3a2a 0%, #0d3320 100%);
    border: 2px solid rgba(80, 200, 120, 0.5);
    border-radius: 20px;
    padding: 32px;
    text-align: center;
    color: #d4f5e2;
}
.score-number {
    font-size: 4rem;
    font-weight: 900;
    color: #50C878;
}
.explanation-box {
    background: rgba(245,166,35,0.1);
    border-left: 3px solid #F5A623;
    padding: 10px 14px;
    border-radius: 6px;
    font-size: 0.9rem;
    color: #f5d98a;
    margin-top: 10px;
}
</style>
"""


# ---------------------------------------------------------------------------
# Session State Init
# ---------------------------------------------------------------------------

def _init_quiz_state():
    defaults = {
        "qz_topic": "",
        "qz_num_questions": 5,
        "qz_grade": 6,
        "qz_data": None,
        "qz_answers": {},
        "qz_submitted": False,
        "qz_score": 0,
        "qz_loading": False,
        "qz_audio_enabled": True,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def _calculate_score(quiz_data: dict, answers: dict) -> tuple:
    questions = quiz_data.get("questions", [])
    score = 0
    results = []
    for i, q in enumerate(questions):
        user_ans = answers.get(i, None)
        correct = q.get("correct_answer", "")
        is_correct = user_ans == correct
        if is_correct:
            score += 1
        results.append({
            "question": q.get("question", ""),
            "user_answer": user_ans,
            "correct_answer": correct,
            "is_correct": is_correct,
            "explanation": q.get("explanation", ""),
            "options": q.get("options", []),
        })
    return score, results


def _score_emoji(pct: float) -> str:
    if pct >= 90: return "🏆"
    if pct >= 70: return "⭐"
    if pct >= 50: return "👍"
    return "💪"


def _reset_quiz():
    for key in ["qz_data", "qz_answers", "qz_submitted", "qz_score", "qz_topic"]:
        st.session_state.pop(key, None)
    _init_quiz_state()
    st.rerun()


# ---------------------------------------------------------------------------
# Public Entry Point
# ---------------------------------------------------------------------------

def render_quiz_page():
    """Render the Quiz Generator page. Called from app.py router."""

    _init_quiz_state()
    st.markdown(QUIZ_CSS, unsafe_allow_html=True)

    st.markdown("## 🧠 Voice-Triggered Quiz Generator")
    st.markdown(
        "Speak or type a quiz command — AI will generate **MCQ questions** "
        "and display them on screen for students to answer."
    )

    api_ok, api_msg = check_api_key()
    if not api_ok:
        st.error(f"🔑 {api_msg}", icon="🚫")
        return

    if st.session_state.qz_data:
        if st.button("🔄 Start New Quiz", key="qz_reset_top", type="secondary"):
            _reset_quiz()

    st.divider()

    # ── PHASE 1: Quiz Generation ────────────────────────────────────────────
    if not st.session_state.qz_data:

        col_cmd, col_opts = st.columns([3, 1])

        with col_opts:
            st.markdown("**⚙️ Quiz Settings**")
            num_q = st.slider("Questions", min_value=3, max_value=15, value=5, key="qz_num_slider")
            grade_sel = st.selectbox("Class / Grade", list(range(1, 13)), index=5, key="qz_grade_sel")
            audio_q = st.toggle("🔊 Questions aloud", value=True, key="qz_audio_toggle")

        with col_cmd:
            st.markdown("**🎤 Speak or Type Your Quiz Command:**")

            if is_whisper_available():
                try:
                    from audio_recorder_streamlit import audio_recorder
                    audio_mic = audio_recorder(
                        text="",
                        recording_color="#e84040",
                        neutral_color="#50C878",
                        icon_name="microphone",
                        icon_size="2x",
                        key="qz_mic_recorder",
                        pause_threshold=2.5,
                        sample_rate=16000,
                    )
                    if audio_mic:
                        with st.spinner("🎧 Listening to your command..."):
                            stt_res = transcribe_audio(audio_mic)
                        if stt_res["success"] and stt_res["text"]:
                            st.session_state.qz_topic = stt_res["text"]
                            st.success(f"✅ Heard: *{stt_res['text']}*")
                        elif not stt_res["success"]:
                            st.warning(f"⚠️ {stt_res['error']}")
                except Exception as e:
                    logger.debug("Mic error: %s", e)
                    st.info("🎤 Microphone unavailable. Please use the text input below.")
            else:
                st.info("💡 Install `faster-whisper` to enable voice input.")

            cmd_input = st.text_input(
                "Enter quiz command:",
                value=st.session_state.qz_topic,
                placeholder="e.g., Create 5 questions on photosynthesis for Class 6...",
                key="qz_cmd_input",
            )

        if cmd_input:
            detected_grade = parse_grade_from_text(cmd_input)
            if detected_grade != 6:
                grade_sel = detected_grade

        gen_btn = st.button(
            "🎯 Generate Quiz",
            type="primary",
            disabled=not cmd_input.strip(),
            key="qz_gen_btn",
        )

        if gen_btn and cmd_input.strip():
            clean_topic = extract_topic_from_command(cmd_input)
            progress = st.progress(0, text="Generating your quiz...")
            try:
                progress.progress(30, text="🧠 Generating questions with Gemini...")
                result = generate_quiz(topic=clean_topic, num_questions=num_q, grade_level=grade_sel)
                progress.progress(90, text="✅ Quiz ready!")

                if result["success"] and result["quiz_data"]:
                    st.session_state.qz_data = result["quiz_data"]
                    st.session_state.qz_grade = grade_sel
                    st.session_state.qz_num_questions = num_q
                    st.session_state.qz_topic = clean_topic
                    st.session_state.qz_audio_enabled = audio_q
                    st.session_state.qz_answers = {}
                    st.session_state.qz_submitted = False
                    progress.progress(100, text="Done!")
                    st.rerun()
                else:
                    st.error(f"❌ {result.get('error', 'Quiz generation failed. Please try again.')}")
            except Exception as e:
                st.error(f"❌ Error: {str(e)}")
                logger.error("Quiz gen error: %s", e, exc_info=True)
            finally:
                progress.empty()

    # ── PHASE 2: Active Quiz ─────────────────────────────────────────────────
    elif st.session_state.qz_data and not st.session_state.qz_submitted:

        quiz_data = st.session_state.qz_data
        questions = quiz_data.get("questions", [])
        total = len(questions)

        st.markdown(f"""
        <div class="quiz-header">
            <div style="font-size:1.4rem; font-weight:800; margin-bottom:6px;">
                🧠 {quiz_data.get('title', 'Classroom Quiz')}
            </div>
            <div style="color:#a0d8b3; font-size:0.9rem;">
                📚 {st.session_state.qz_topic} &nbsp;|&nbsp;
                🎓 Class {st.session_state.qz_grade} &nbsp;|&nbsp;
                ❓ {total} Questions
            </div>
        </div>
        """, unsafe_allow_html=True)

        answered = len(st.session_state.qz_answers)
        st.progress(answered / total if total else 0, text=f"✅ {answered}/{total} attempted")

        for i, q in enumerate(questions):
            q_text = q.get("question", f"Question {i+1}")
            options = q.get("options", [])
            q_num = i + 1

            st.markdown(f"""
            <div class="question-card">
                <div class="question-num">Question {q_num} of {total}</div>
                <div class="question-text">{q_text}</div>
            </div>
            """, unsafe_allow_html=True)

            # Audio playback per question
            if st.session_state.qz_audio_enabled and is_gtts_available():
                if st.button(f"🔊 Play Q{q_num}", key=f"qz_audio_{i}"):
                    with st.spinner("Audio..."):
                        tts_res = generate_speech_for_quiz_question(q_text, q_num, options)
                    if tts_res["success"]:
                        st.audio(tts_res["audio_bytes"], format="audio/mp3", autoplay=True)

            # Answer radio
            current = st.session_state.qz_answers.get(i, None)
            selected = st.radio(
                f"Q{q_num} answer:",
                options=options,
                index=options.index(current) if current in options else None,
                key=f"qz_radio_{i}",
                label_visibility="collapsed",
            )
            if selected:
                st.session_state.qz_answers[i] = selected

            st.markdown("---")

        all_done = len(st.session_state.qz_answers) == total
        col1, col2 = st.columns([1, 3])
        with col1:
            submit = st.button("📊 Submit Quiz", type="primary", disabled=not all_done,
                               use_container_width=True, key="qz_submit_btn")
        if not all_done:
            with col2:
                st.warning(f"⚠️ {total - answered} question(s) remaining. Please answer all questions before submitting.")

        if submit:
            score, _ = _calculate_score(quiz_data, st.session_state.qz_answers)
            st.session_state.qz_score = score
            st.session_state.qz_submitted = True
            save_quiz_result(
                session_id=st.session_state.get("session_id", "unknown"),
                topic=st.session_state.qz_topic,
                grade_level=st.session_state.qz_grade,
                total_questions=total,
                score=score,
                completed=True,
            )
            st.rerun()

    # ── PHASE 3: Results ─────────────────────────────────────────────────────
    elif st.session_state.qz_submitted and st.session_state.qz_data:

        quiz_data = st.session_state.qz_data
        questions = quiz_data.get("questions", [])
        total = len(questions)
        score = st.session_state.qz_score
        pct = round(score / total * 100, 1) if total else 0
        emoji = _score_emoji(pct)

        st.markdown(f"""
        <div class="score-card">
            <div style="font-size:3rem;">{emoji}</div>
            <div class="score-number">{score}/{total}</div>
            <div style="font-size:1.2rem; color:#a0d8b3;">Score: {pct}%</div>
            <div style="margin-top:12px; color:#6dbf8a;">
                {'Excellent work! Well done! 🌟' if pct >= 70 else 'Keep practicing — you can do better! 💪'}
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### 📋 Detailed Results")

        _, results = _calculate_score(quiz_data, st.session_state.qz_answers)

        for i, res in enumerate(results):
            icon = "✅" if res["is_correct"] else "❌"
            with st.expander(f"{icon} Q{i+1}: {res['question'][:70]}...", expanded=False):
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"**👤 Your Answer:** {res['user_answer'] or 'Not answered'}")
                with c2:
                    st.markdown(f"**✅ Correct Answer:** {res['correct_answer']}")
                if res.get("explanation"):
                    st.markdown(f"""
                    <div class="explanation-box">💡 <b>Explanation:</b> {res['explanation']}</div>
                    """, unsafe_allow_html=True)

        st.markdown("---")
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            if st.button("🔄 Start New Quiz", type="primary", use_container_width=True, key="qz_new"):
                _reset_quiz()
        with col_r2:
            if st.button("📚 Concept Simplifier", use_container_width=True, key="qz_go_concept"):
                st.session_state.current_page = "concept"
                st.rerun()
