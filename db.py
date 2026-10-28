import os
import re
import sqlite3
from datetime import datetime

DB_PATH = "recordings.db"
RECORDINGS_DIR = "recordings"


def build_recording_path(
    pdf_name: str, start_page: int, end_page: int, tts_engine: str = "edge"
) -> str:
    """Build a standardized file path inside recordings/ for a PDF, page range, and TTS engine."""
    os.makedirs(RECORDINGS_DIR, exist_ok=True)
    stem = os.path.splitext(pdf_name)[0]
    safe_stem = re.sub(r"[^a-zA-Z0-9_-]+", "_", stem).strip("_")[:50]
    ext = "mp3" if tts_engine == "edge" else "wav"
    filename = f"{safe_stem}_p{start_page}_{end_page}_{tts_engine}.{ext}"
    return os.path.join(RECORDINGS_DIR, filename)


def init_db(db_path: str = DB_PATH) -> None:
    """Initialize the SQLite database and recordings folder."""
    os.makedirs(RECORDINGS_DIR, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS recordings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pdf_name TEXT NOT NULL,
                start_page INTEGER NOT NULL,
                end_page INTEGER NOT NULL,
                audio_path TEXT NOT NULL,
                cleaned_text TEXT NOT NULL,
                created_at TEXT NOT NULL,
                tts_engine TEXT DEFAULT 'edge',
                duration_sec REAL DEFAULT 0.0,
                UNIQUE(pdf_name, start_page, end_page, tts_engine)
            )
            """
        )
        # Ensure new columns exist on existing databases
        cols = [r[1] for r in conn.execute("PRAGMA table_info(recordings)").fetchall()]
        if "tts_engine" not in cols:
            conn.execute("ALTER TABLE recordings ADD COLUMN tts_engine TEXT DEFAULT 'edge'")
        if "duration_sec" not in cols:
            conn.execute("ALTER TABLE recordings ADD COLUMN duration_sec REAL DEFAULT 0.0")


def get_cached_recording(
    pdf_name: str, start_page: int, end_page: int, db_path: str = DB_PATH
) -> dict | None:
    """Look up an existing recording for a given PDF name and page range."""
    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT * FROM recordings
            WHERE pdf_name = ? AND start_page = ? AND end_page = ?
            """,
            (pdf_name, start_page, end_page),
        ).fetchone()

        if row and os.path.exists(row["audio_path"]):
            return dict(row)
    return None


def save_recording(
    pdf_name: str,
    start_page: int,
    end_page: int,
    audio_path: str,
    cleaned_text: str,
    tts_engine: str = "edge",
    duration_sec: float = 0.0,
    db_path: str = DB_PATH,
) -> None:
    """Save or update a recording record in SQLite."""
    init_db(db_path)
    now = datetime.now().isoformat(timespec="seconds")
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO recordings (
                pdf_name, start_page, end_page, audio_path, cleaned_text, created_at, tts_engine, duration_sec
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(pdf_name, start_page, end_page) DO UPDATE SET
                audio_path = excluded.audio_path,
                cleaned_text = excluded.cleaned_text,
                created_at = excluded.created_at,
                tts_engine = excluded.tts_engine,
                duration_sec = excluded.duration_sec
            """,
            (
                pdf_name,
                start_page,
                end_page,
                audio_path,
                cleaned_text,
                now,
                tts_engine,
                round(duration_sec, 2),
            ),
        )


def list_recordings(pdf_name: str | None = None, db_path: str = DB_PATH) -> list[dict]:
    """List saved recordings, optionally filtered by PDF name."""
    init_db(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        if pdf_name:
            rows = conn.execute(
                "SELECT * FROM recordings WHERE pdf_name = ? ORDER BY start_page ASC, end_page ASC",
                (pdf_name,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM recordings ORDER BY created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows if os.path.exists(r["audio_path"])]
