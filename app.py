"""
app.py
======
AI Classroom Co-Pilot — Main Entry Point
==========================================
Streamlit multi-page application for Haryana Government Schools.

Provides a smart-board-friendly dashboard with:
  - Live Concept Simplification (Hinglish explanations + diagrams)
  - Voice-Triggered Quiz Generator (MCQs with audio readout)

Run with:
    streamlit run app.py

Author: AI Classroom Co-Pilot Team
"""

import os
import sys
import uuid
import logging
from pathlib import Path

import streamlit as st

# ---------------------------------------------------------------------------
# Path Setup — ensure project root is importable
# ---------------------------------------------------------------------------
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------------------
# Environment & Logging
# — On Streamlit Cloud: reads from st.secrets (set in Advanced Settings)
# — On local machine:   reads from .env file via python-dotenv
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Sync st.secrets → os.environ so all os.getenv() calls work everywhere
try:
    for _k, _v in st.secrets.items():
        if _k not in os.environ:
            os.environ[_k] = str(_v)
except Exception:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# App Configuration
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title=os.getenv("SCHOOL_NAME", "Haryana Govt. Smart Classroom") + " — AI Co-Pilot",
    page_icon="🏫",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": None,
        "Report a bug": None,
        "About": "AI Classroom Co-Pilot v1.0 — Powered by Gemini 2.5 Flash",
    },
)

# ---------------------------------------------------------------------------
# Database Initialisation (runs once per process)
# ---------------------------------------------------------------------------
try:
    from database.db import init_db, create_session, get_overall_stats
    init_db()
except Exception as e:
    st.error(f"Database error: {e}")
    logger.error("DB init failed: %s", e)

# ---------------------------------------------------------------------------
# Session State Setup
# ---------------------------------------------------------------------------

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
    try:
        school = os.getenv("SCHOOL_NAME", "Haryana Govt. School")
        create_session(st.session_state.session_id, school)
    except Exception:
        pass

if "current_page" not in st.session_state:
    st.session_state.current_page = "home"

# ---------------------------------------------------------------------------
# Global CSS — Premium dark classroom theme
# ---------------------------------------------------------------------------

st.markdown("""
<style>
/* =====================================================
   GLOBAL THEME — AI Classroom Co-Pilot
   Dark mode optimised for smart board projection
   ===================================================== */

@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=Space+Grotesk:wght@400;500;600;700&display=swap');

/* Root variables */
:root {
    --primary: #4A90D9;
    --primary-dark: #2c5f8a;
    --accent: #F5A623;
    --accent-green: #50C878;
    --accent-red: #e84040;
    --bg-dark: #0a1628;
    --bg-card: #111f35;
    --bg-card-2: #0d2137;
    --text-primary: #e8f4fd;
    --text-muted: #7fb3d3;
    --border: rgba(74, 144, 217, 0.25);
    --font-main: 'Inter', sans-serif;
    --font-heading: 'Space Grotesk', sans-serif;
}

/* Full app background */
.stApp {
    background: linear-gradient(145deg, #06101f 0%, #0a1628 50%, #0d1f3c 100%);
    font-family: var(--font-main);
    color: var(--text-primary);
}

/* Main content area */
.main .block-container {
    padding: 1.5rem 2rem 2rem 2rem;
    max-width: 1400px;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #06101f 0%, #0a1628 100%);
    border-right: 1px solid var(--border);
}

[data-testid="stSidebar"] .stMarkdown p,
[data-testid="stSidebar"] .stMarkdown h1,
[data-testid="stSidebar"] .stMarkdown h2,
[data-testid="stSidebar"] .stMarkdown h3 {
    color: var(--text-primary) !important;
}

/* Typography */
h1, h2, h3, h4 {
    font-family: var(--font-heading);
    color: var(--text-primary) !important;
}

h1 { font-size: 2rem !important; font-weight: 800 !important; }
h2 { font-size: 1.5rem !important; font-weight: 700 !important; }
h3 { font-size: 1.2rem !important; font-weight: 600 !important; }

p, li, label, .stMarkdown {
    color: var(--text-primary) !important;
}

/* Buttons */
.stButton > button {
    background: linear-gradient(135deg, var(--primary) 0%, var(--primary-dark) 100%);
    color: white !important;
    border: none;
    border-radius: 10px;
    font-family: var(--font-main);
    font-weight: 600;
    font-size: 0.9rem;
    padding: 0.55rem 1.4rem;
    transition: all 0.2s ease;
    box-shadow: 0 4px 12px rgba(74, 144, 217, 0.25);
}
.stButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 6px 18px rgba(74, 144, 217, 0.4);
    background: linear-gradient(135deg, #5aa0e9 0%, var(--primary) 100%);
}
.stButton > button[kind="secondary"] {
    background: rgba(74, 144, 217, 0.12) !important;
    border: 1px solid var(--border) !important;
    color: var(--primary) !important;
}

/* Text inputs */
.stTextInput > div > div > input {
    background: rgba(255, 255, 255, 0.05) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    color: var(--text-primary) !important;
    font-family: var(--font-main) !important;
    padding: 0.6rem 1rem !important;
    transition: border 0.2s;
}
.stTextInput > div > div > input:focus {
    border-color: var(--primary) !important;
    box-shadow: 0 0 0 2px rgba(74, 144, 217, 0.2) !important;
}

/* Selectbox & slider */
.stSelectbox > div > div {
    background: rgba(255, 255, 255, 0.05) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    color: var(--text-primary) !important;
}
.stSlider > div {
    color: var(--text-primary) !important;
}
[data-testid="stSlider"] > div > div > div > div {
    background: var(--primary) !important;
}

/* Radio buttons */
.stRadio > div {
    gap: 8px;
}
.stRadio > div > label {
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    padding: 10px 16px !important;
    cursor: pointer;
    transition: all 0.2s;
    font-family: var(--font-main) !important;
}
.stRadio > div > label:hover {
    background: rgba(74, 144, 217, 0.12) !important;
    border-color: var(--primary) !important;
}

/* Progress bar */
.stProgress > div > div > div {
    background: linear-gradient(90deg, var(--primary), var(--accent-green)) !important;
    border-radius: 10px;
}

/* Expanders */
.streamlit-expanderHeader {
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    color: var(--text-primary) !important;
    font-family: var(--font-main) !important;
}

/* Alert / info boxes */
.stAlert {
    border-radius: 10px !important;
    font-family: var(--font-main) !important;
}

/* Divider */
hr {
    border-color: var(--border) !important;
    margin: 1.2rem 0 !important;
}

/* Metric cards */
[data-testid="stMetric"] {
    background: var(--bg-card) !important;
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 16px 20px !important;
}
[data-testid="stMetricValue"] {
    color: var(--accent) !important;
    font-size: 2rem !important;
    font-weight: 800 !important;
}
[data-testid="stMetricLabel"] {
    color: var(--text-muted) !important;
    font-size: 0.85rem !important;
}

/* Scrollbar */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: var(--primary); }

/* Toggle */
.stToggle > label > div[data-checked="true"] {
    background-color: var(--accent-green) !important;
}

/* ── Hide built-in Streamlit multi-page nav list from main body ── */
/* This removes the "app / concept simplifier / quiz generator"    */
/* navigation block that Streamlit auto-renders for pages/ files.  */
[data-testid="stSidebarNav"],
section[data-testid="stSidebarNav"],
div[data-testid="stSidebarNav"] {
    display: none !important;
}
/* Also hide the nav list if it appears in main content area */
.stPageLink,
[data-testid="stPageLink"],
nav[aria-label="Page navigation"],
div[class*="st-emotion-cache"][class*="e"] > ul,
[data-testid="stMainMenu"] {
    display: none !important;
}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Sidebar Navigation
# ---------------------------------------------------------------------------

with st.sidebar:
    # School branding
    school_name = os.getenv("SCHOOL_NAME", "Haryana Govt. Smart Classroom")

    st.markdown(f"""
    <div style="text-align:center; padding: 16px 8px 24px 8px;">
        <div style="font-size:2.8rem; margin-bottom:6px;">🏫</div>
        <div style="
            font-family: 'Space Grotesk', sans-serif;
            font-size:1.05rem;
            font-weight:700;
            color:#e8f4fd;
            line-height:1.3;
        ">{school_name}</div>
        <div style="
            font-size:0.72rem;
            color:#4A90D9;
            letter-spacing:1.5px;
            text-transform:uppercase;
            margin-top:4px;
        ">AI Classroom Co-Pilot</div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # Navigation links
    st.markdown("**📍 Navigation**")

    pages = {
        "🏠 Home": "home",
        "📚 Concept Simplifier": "concept",
        "🧠 Quiz Generator": "quiz",
    }

    for label, page_key in pages.items():
        is_active = st.session_state.current_page == page_key
        if st.button(
            label,
            key=f"nav_{page_key}",
            use_container_width=True,
            type="primary" if is_active else "secondary",
        ):
            st.session_state.current_page = page_key
            st.rerun()

    st.divider()

    # Settings section
    st.markdown("**⚙️ Settings**")

    whisper_model = os.getenv("WHISPER_MODEL", "base")
    tts_lang = os.getenv("TTS_LANGUAGE", "hi")

    st.markdown(f"""
    <div style="font-size:0.8rem; color:#7fb3d3; line-height:2;">
        🎙️ STT Model: <b style="color:#e8f4fd;">{whisper_model}</b><br>
        🔊 TTS Lang: <b style="color:#e8f4fd;">{tts_lang}</b><br>
        🤖 AI Model: <b style="color:#e8f4fd;">Gemini 2.5 Flash</b>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # API key status
    try:
        from services.gemini_service import check_api_key
        api_valid, _ = check_api_key()
        api_status = "🟢 Connected" if api_valid else "🔴 Not configured"
        api_color = "#50C878" if api_valid else "#e84040"
    except Exception:
        api_status = "⚠️ Check config"
        api_color = "#F5A623"

    st.markdown(f"""
    <div style="font-size:0.8rem; color:{api_color}; font-weight:600;">
        {api_status}
    </div>
    """, unsafe_allow_html=True)

    # Version info
    st.markdown("""
    <div style="
        position:fixed;
        bottom:16px;
        font-size:0.7rem;
        color:#2d4a6a;
        text-align:center;
    ">v1.0.0 &nbsp;|&nbsp; Python 3.11+</div>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Page Router
# ---------------------------------------------------------------------------

page = st.session_state.current_page

# ── HOME DASHBOARD ──────────────────────────────────────────────────────────
if page == "home":

    # Hero header
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, rgba(74,144,217,0.15) 0%, rgba(80,200,120,0.08) 100%);
        border: 1px solid rgba(74,144,217,0.3);
        border-radius: 20px;
        padding: 36px 40px;
        margin-bottom: 28px;
        position: relative;
        overflow: hidden;
    ">
        <div style="
            position:absolute; top:-60px; right:-60px;
            width:200px; height:200px;
            background: radial-gradient(circle, rgba(74,144,217,0.12), transparent);
            border-radius:50%;
        "></div>
        <div style="font-size:0.8rem; color:#4A90D9; letter-spacing:2px; text-transform:uppercase; margin-bottom:8px;">
            🏫 {os.getenv('SCHOOL_NAME', 'Haryana Govt. Smart Classroom')}
        </div>
        <h1 style="
            font-family:'Space Grotesk',sans-serif;
            font-size:2.4rem !important;
            font-weight:900 !important;
            color:#e8f4fd !important;
            margin:0 0 10px 0;
            line-height:1.2;
        ">
            AI Classroom Co-Pilot 🤖
        </h1>
        <p style="font-size:1.05rem; color:#7fb3d3; max-width:600px; margin:0;">
            Empowering teachers with AI. A powerful voice-controlled teaching assistant
            designed for smart board classrooms.
        </p>
    </div>
    """, unsafe_allow_html=True)

    # Stats row
    try:
        stats = get_overall_stats()
    except Exception:
        stats = {"total_concepts": 0, "total_quizzes": 0, "avg_quiz_score": 0}

    col_s1, col_s2, col_s3, col_s4 = st.columns(4)
    with col_s1:
        st.metric("📚 Concepts Explained", stats["total_concepts"])
    with col_s2:
        st.metric("🧠 Quizzes Conducted", stats["total_quizzes"])
    with col_s3:
        st.metric("📈 Avg Quiz Score", f"{stats['avg_quiz_score']}%")
    with col_s4:
        st.metric("🤖 AI Model", "Gemini 2.5")

    st.markdown("---")

    # Feature cards
    st.markdown("### 🚀 Features")
    feat_col1, feat_col2 = st.columns(2)

    with feat_col1:
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #1e3a5f 0%, #0d2137 100%);
            border: 1px solid rgba(74,144,217,0.4);
            border-radius: 16px;
            padding: 28px;
            height: 240px;
        ">
            <div style="font-size:2.2rem; margin-bottom:12px;">📚</div>
            <div style="
                font-family:'Space Grotesk',sans-serif;
                font-size:1.25rem;
                font-weight:700;
                color:#e8f4fd;
                margin-bottom:10px;
            ">Live Concept Simplifier</div>
            <div style="font-size:0.9rem; color:#7fb3d3; line-height:1.6;">
                Speak or type a topic. Gemini AI instantly generates a <b style='color:#4A90D9'>simple Hinglish explanation</b>
                with real-life examples and a visual diagram.
                Audio plays automatically.
            </div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("📚 Open Concept Simplifier →", use_container_width=True, key="go_concept"):
            st.session_state.current_page = "concept"
            st.rerun()

    with feat_col2:
        st.markdown("""
        <div style="
            background: linear-gradient(135deg, #1a3a2a 0%, #0d2118 100%);
            border: 1px solid rgba(80,200,120,0.35);
            border-radius: 16px;
            padding: 28px;
            height: 240px;
        ">
            <div style="font-size:2.2rem; margin-bottom:12px;">🧠</div>
            <div style="
                font-family:'Space Grotesk',sans-serif;
                font-size:1.25rem;
                font-weight:700;
                color:#d4f5e2;
                margin-bottom:10px;
            ">Voice Quiz Generator</div>
            <div style="font-size:0.9rem; color:#6dbf8a; line-height:1.6;">
                Speak a quiz command. AI generates <b style='color:#50C878'>MCQ questions</b>,
                reads them aloud, students select their answers,
                and the final score with correct answers is displayed on screen.
            </div>
        </div>
        """, unsafe_allow_html=True)

        if st.button("🧠 Open Quiz Generator →", use_container_width=True, key="go_quiz"):
            st.session_state.current_page = "quiz"
            st.rerun()

    st.markdown("---")

    # Quick Guide
    st.markdown("### 💡 Quick Guide — How to Use")

    guide_col1, guide_col2 = st.columns(2)

    with guide_col1:
        st.markdown("""
        <div style="
            background: rgba(74,144,217,0.08);
            border-left: 3px solid #4A90D9;
            border-radius: 0 10px 10px 0;
            padding: 16px 20px;
            margin-bottom: 12px;
        ">
            <b style="color:#4A90D9;">📚 Concept Simplifier — Examples:</b><br>
            <div style="color:#b0d0ed; margin-top:8px; font-size:0.88rem; line-height:2;">
                • "Explain photosynthesis for Class 6"<br>
                • "Explain the water cycle in simple Hinglish"<br>
                • "Explain fractions with real-life examples"<br>
                • "Explain gravity for Class 9 students"
            </div>
        </div>
        """, unsafe_allow_html=True)

    with guide_col2:
        st.markdown("""
        <div style="
            background: rgba(80,200,120,0.08);
            border-left: 3px solid #50C878;
            border-radius: 0 10px 10px 0;
            padding: 16px 20px;
            margin-bottom: 12px;
        ">
            <b style="color:#50C878;">🧠 Quiz Generator — Examples:</b><br>
            <div style="color:#a0d8b3; margin-top:8px; font-size:0.88rem; line-height:2;">
                • "Create 5 questions on fractions"<br>
                • "Generate a quiz on photosynthesis for Class 6"<br>
                • "Ask students 10 MCQs on water cycle"<br>
                • "Quiz on Indian history for Class 8"
            </div>
        </div>
        """, unsafe_allow_html=True)

    # System status
    st.markdown("### 🔧 System Status")

    try:
        from services.speech_to_text import is_whisper_available
        from services.text_to_speech import is_gtts_available
        from services.gemini_service import check_api_key as _cak

        w_ok = is_whisper_available()
        g_ok = is_gtts_available()
        api_ok, _ = _cak()

        def _status_dot(ok): return "🟢" if ok else "🔴"

        st.markdown(f"""
        <div style="
            display:flex;
            gap:24px;
            flex-wrap:wrap;
            background:rgba(255,255,255,0.03);
            border:1px solid rgba(74,144,217,0.2);
            border-radius:12px;
            padding:16px 20px;
        ">
            <span style="font-size:0.88rem; color:#b0c8e0;">
                {_status_dot(api_ok)} <b>Gemini API</b>
            </span>
            <span style="font-size:0.88rem; color:#b0c8e0;">
                {_status_dot(w_ok)} <b>Speech-to-Text</b> (faster-whisper)
            </span>
            <span style="font-size:0.88rem; color:#b0c8e0;">
                {_status_dot(g_ok)} <b>Text-to-Speech</b> (gTTS)
            </span>
            <span style="font-size:0.88rem; color:#50C878;">
                🟢 <b>Database</b> (SQLite)
            </span>
        </div>
        """, unsafe_allow_html=True)

        if not api_ok:
            st.warning("⚠️ GEMINI_API_KEY is not configured. Please add your API key to the `.env` file.")

    except Exception as e:
        st.warning(f"System status check failed: {e}")

# ── CONCEPT SIMPLIFIER ───────────────────────────────────────────────────────
elif page == "concept":
    from pages.concept_simplifier import render_concept_page
    render_concept_page()

# ── QUIZ GENERATOR ───────────────────────────────────────────────────────────
elif page == "quiz":
    from pages.quiz_generator import render_quiz_page
    render_quiz_page()
