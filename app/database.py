import sqlite3
import json
from datetime import datetime
from pathlib import Path
from app.config import DATABASE_PATH


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DATABASE_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS meetings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            filename TEXT NOT NULL,
            audio_path TEXT NOT NULL,
            duration REAL,
            language TEXT,
            transcript TEXT,
            segments TEXT,
            analysis TEXT,
            error_message TEXT,
            status TEXT NOT NULL DEFAULT 'uploaded',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
    """)
    # Add error_message column if upgrading from older schema
    try:
        conn.execute("SELECT error_message FROM meetings LIMIT 1")
    except Exception:
        conn.execute("ALTER TABLE meetings ADD COLUMN error_message TEXT")
    conn.close()


def create_meeting(title: str, filename: str, audio_path: str) -> int:
    conn = get_db()
    now = datetime.now().isoformat()
    cursor = conn.execute(
        "INSERT INTO meetings (title, filename, audio_path, status, created_at, updated_at) VALUES (?, ?, ?, 'uploaded', ?, ?)",
        (title, filename, audio_path, now, now),
    )
    conn.commit()
    meeting_id = cursor.lastrowid
    conn.close()
    return meeting_id


def update_meeting(meeting_id: int, **kwargs):
    conn = get_db()
    kwargs["updated_at"] = datetime.now().isoformat()
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values())
    values.append(meeting_id)
    conn.execute(f"UPDATE meetings SET {sets} WHERE id = ?", values)
    conn.commit()
    conn.close()


def get_meeting(meeting_id: int) -> dict | None:
    conn = get_db()
    row = conn.execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
    conn.close()
    if row is None:
        return None
    d = dict(row)
    if d.get("segments"):
        d["segments"] = json.loads(d["segments"])
    return d


def list_meetings() -> list[dict]:
    conn = get_db()
    rows = conn.execute("SELECT id, title, filename, duration, language, status, created_at FROM meetings ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_meeting(meeting_id: int):
    conn = get_db()
    row = conn.execute("SELECT audio_path FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
    if row:
        path = Path(row["audio_path"])
        if path.exists():
            path.unlink()
    conn.execute("DELETE FROM meetings WHERE id = ?", (meeting_id,))
    conn.commit()
    conn.close()
