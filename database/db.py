"""
database/db.py
==============
SQLite database layer for the AI Classroom Co-Pilot.

Manages:
  - Application sessions
  - Concept explanation history
  - Quiz results and scores

Schema is created automatically on first run via init_db().

Author: AI Classroom Co-Pilot Team
"""

import sqlite3
import logging
import os
from datetime import datetime
from typing import Optional, List, Dict, Any

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
logger = logging.getLogger(__name__)

# Database lives inside the project root under database/
DB_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DB_DIR, "classroom.db")


# ---------------------------------------------------------------------------
# Connection Helper
# ---------------------------------------------------------------------------

def _get_connection() -> sqlite3.Connection:
    """
    Open and return a SQLite connection with row factory enabled.

    Returns rows as sqlite3.Row objects (accessible like dicts).
    """
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")   # Better concurrency
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ---------------------------------------------------------------------------
# Schema Initialisation
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
-- Application sessions (one per Streamlit session launch)
CREATE TABLE IF NOT EXISTS sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT NOT NULL UNIQUE,
    school_name TEXT,
    started_at  TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    ended_at    TEXT
);

-- Concept explanations generated for teachers
CREATE TABLE IF NOT EXISTS concept_history (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id     TEXT,
    topic          TEXT NOT NULL,
    grade_level    INTEGER NOT NULL DEFAULT 6,
    input_text     TEXT,
    explanation    TEXT,
    has_diagram    INTEGER NOT NULL DEFAULT 0,
    audio_path     TEXT,
    created_at     TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);

-- Quiz results per teacher session
CREATE TABLE IF NOT EXISTS quiz_results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT,
    topic           TEXT NOT NULL,
    grade_level     INTEGER NOT NULL DEFAULT 6,
    total_questions INTEGER NOT NULL,
    score           INTEGER NOT NULL DEFAULT 0,
    percentage      REAL NOT NULL DEFAULT 0.0,
    completed       INTEGER NOT NULL DEFAULT 0,
    created_at      TEXT NOT NULL DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
);
"""


def init_db() -> None:
    """
    Initialise the SQLite database and create tables if they don't exist.

    Safe to call multiple times — uses CREATE TABLE IF NOT EXISTS.
    """
    try:
        os.makedirs(DB_DIR, exist_ok=True)
        with _get_connection() as conn:
            conn.executescript(SCHEMA_SQL)
            conn.commit()
        logger.info("Database initialised at: %s", DB_PATH)
    except sqlite3.Error as e:
        logger.error("Database initialisation failed: %s", e)
        raise


# ---------------------------------------------------------------------------
# Session Management
# ---------------------------------------------------------------------------

def create_session(session_id: str, school_name: str = "Haryana Govt. School") -> None:
    """
    Record a new application session start.

    Args:
        session_id: Unique Streamlit session identifier.
        school_name: Name of the school (from env var).
    """
    try:
        with _get_connection() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO sessions (session_id, school_name, started_at)
                VALUES (?, ?, datetime('now','localtime'))
                """,
                (session_id, school_name),
            )
            conn.commit()
    except sqlite3.Error as e:
        logger.error("Failed to create session %s: %s", session_id, e)


def close_session(session_id: str) -> None:
    """
    Mark a session as ended.

    Args:
        session_id: Unique session identifier to close.
    """
    try:
        with _get_connection() as conn:
            conn.execute(
                """
                UPDATE sessions
                SET ended_at = datetime('now','localtime')
                WHERE session_id = ?
                """,
                (session_id,),
            )
            conn.commit()
    except sqlite3.Error as e:
        logger.error("Failed to close session %s: %s", session_id, e)


# ---------------------------------------------------------------------------
# Concept History
# ---------------------------------------------------------------------------

def save_concept_session(
    session_id: str,
    topic: str,
    grade_level: int,
    input_text: str,
    explanation: str,
    has_diagram: bool = False,
    audio_path: Optional[str] = None,
) -> Optional[int]:
    """
    Save a concept explanation to the database.

    Args:
        session_id:   Streamlit session ID.
        topic:        The topic that was explained.
        grade_level:  Class/grade number.
        input_text:   Original teacher input (voice or text).
        explanation:  Full explanation text from Gemini.
        has_diagram:  Whether a diagram was generated.
        audio_path:   Path to generated TTS audio file.

    Returns:
        Row ID of the inserted record, or None on failure.
    """
    try:
        with _get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO concept_history
                    (session_id, topic, grade_level, input_text, explanation,
                     has_diagram, audio_path, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))
                """,
                (
                    session_id, topic, grade_level, input_text,
                    explanation, int(has_diagram), audio_path,
                ),
            )
            conn.commit()
            return cursor.lastrowid
    except sqlite3.Error as e:
        logger.error("Failed to save concept session: %s", e)
        return None


def get_recent_concepts(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Retrieve the most recent concept explanations.

    Args:
        limit: Maximum number of records to return.

    Returns:
        List of dicts with keys: id, topic, grade_level, created_at.
    """
    try:
        with _get_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, topic, grade_level, created_at
                FROM concept_history
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]
    except sqlite3.Error as e:
        logger.error("Failed to fetch recent concepts: %s", e)
        return []


# ---------------------------------------------------------------------------
# Quiz Results
# ---------------------------------------------------------------------------

def save_quiz_result(
    session_id: str,
    topic: str,
    grade_level: int,
    total_questions: int,
    score: int,
    completed: bool = True,
) -> Optional[int]:
    """
    Persist quiz result to database after completion.

    Args:
        session_id:      Streamlit session ID.
        topic:           Quiz topic.
        grade_level:     Class/grade number.
        total_questions: Total number of questions.
        score:           Number of correct answers.
        completed:       Whether the quiz was fully completed.

    Returns:
        Row ID of the inserted record, or None on failure.
    """
    percentage = round((score / total_questions * 100), 2) if total_questions > 0 else 0.0
    try:
        with _get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO quiz_results
                    (session_id, topic, grade_level, total_questions,
                     score, percentage, completed, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now','localtime'))
                """,
                (session_id, topic, grade_level, total_questions,
                 score, percentage, int(completed)),
            )
            conn.commit()
            return cursor.lastrowid
    except sqlite3.Error as e:
        logger.error("Failed to save quiz result: %s", e)
        return None


def get_recent_quiz_results(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Retrieve the most recent quiz results.

    Args:
        limit: Maximum number of records to return.

    Returns:
        List of dicts with quiz result data.
    """
    try:
        with _get_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, topic, grade_level, total_questions,
                       score, percentage, created_at
                FROM quiz_results
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]
    except sqlite3.Error as e:
        logger.error("Failed to fetch quiz results: %s", e)
        return []


def get_overall_stats() -> Dict[str, Any]:
    """
    Get aggregate statistics across all sessions.

    Returns:
        Dict with total_concepts, total_quizzes, avg_quiz_score.
    """
    try:
        with _get_connection() as conn:
            concepts = conn.execute(
                "SELECT COUNT(*) as cnt FROM concept_history"
            ).fetchone()["cnt"]

            quiz_stats = conn.execute(
                """
                SELECT COUNT(*) as cnt, AVG(percentage) as avg_pct
                FROM quiz_results WHERE completed = 1
                """
            ).fetchone()

            return {
                "total_concepts": concepts,
                "total_quizzes": quiz_stats["cnt"],
                "avg_quiz_score": round(quiz_stats["avg_pct"] or 0, 1),
            }
    except sqlite3.Error as e:
        logger.error("Failed to fetch stats: %s", e)
        return {"total_concepts": 0, "total_quizzes": 0, "avg_quiz_score": 0}
