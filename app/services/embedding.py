"""Embedding generation and similarity search using DashScope text-embedding API."""

import logging
import struct
import threading
from typing import Optional

import numpy as np
from openai import OpenAI

from app.config import DASHSCOPE_API_KEY, QWEN_BASE_URL, EMBEDDING_MODEL, RAG_TOP_K
from app.database import get_db

logger = logging.getLogger(__name__)

_EMBEDDING_DIM = 1024


def _get_client() -> OpenAI:
    if not DASHSCOPE_API_KEY:
        raise RuntimeError("未配置 API Key")
    return OpenAI(api_key=DASHSCOPE_API_KEY, base_url=QWEN_BASE_URL)


def generate_embedding(text: str) -> list[float]:
    """Generate embedding vector for text via DashScope API."""
    client = _get_client()
    # Truncate to avoid token limits (~8000 tokens max for embedding model)
    truncated = text[:6000]
    response = client.embeddings.create(model=EMBEDDING_MODEL, input=truncated)
    return response.data[0].embedding


def embedding_to_bytes(vec: list[float]) -> bytes:
    """Serialize embedding vector to bytes for SQLite BLOB storage."""
    return struct.pack(f"{len(vec)}f", *vec)


def bytes_to_embedding(data: bytes) -> np.ndarray:
    """Deserialize bytes back to numpy array."""
    n = len(data) // 4  # float32 = 4 bytes
    return np.array(struct.unpack(f"{n}f", data), dtype=np.float32)


def store_embedding(meeting_id: int, text: str) -> None:
    """Generate and store embedding for a meeting's analysis."""
    try:
        vec = generate_embedding(text)
        blob = embedding_to_bytes(vec)
        conn = get_db()
        conn.execute("UPDATE meetings SET embedding = ? WHERE id = ?", (blob, meeting_id))
        conn.commit()
        conn.close()
        logger.info("Stored embedding for meeting #%d (%d dim)", meeting_id, len(vec))
    except Exception:
        logger.exception("Failed to generate/store embedding for meeting #%d", meeting_id)


def search_similar(query_text: str, exclude_id: Optional[int] = None) -> list[dict]:
    """Find top-K similar past meetings by cosine similarity.

    Returns list of {"id", "title", "analysis", "score"} dicts.
    """
    try:
        query_vec = np.array(generate_embedding(query_text), dtype=np.float32)
    except Exception:
        logger.exception("Failed to generate query embedding for RAG search")
        return []

    conn = get_db()
    rows = conn.execute(
        "SELECT id, title, analysis, meeting_time, location, participants, embedding "
        "FROM meetings WHERE status = 'completed' AND embedding IS NOT NULL"
    ).fetchall()
    conn.close()

    if not rows:
        return []

    results = []
    query_norm = np.linalg.norm(query_vec)
    if query_norm == 0:
        return []

    for row in rows:
        if exclude_id and row["id"] == exclude_id:
            continue
        stored_vec = bytes_to_embedding(row["embedding"])
        stored_norm = np.linalg.norm(stored_vec)
        if stored_norm == 0:
            continue
        score = float(np.dot(query_vec, stored_vec) / (query_norm * stored_norm))
        results.append({
            "id": row["id"],
            "title": row["title"],
            "analysis": row["analysis"],
            "meeting_time": row["meeting_time"],
            "location": row["location"],
            "participants": row["participants"],
            "score": score,
        })

    results.sort(key=lambda x: x["score"], reverse=True)
    top = results[:RAG_TOP_K]

    if top:
        logger.info(
            "RAG: found %d similar meetings (top score: %.3f)",
            len(top), top[0]["score"],
        )
    return top


def backfill_embeddings() -> None:
    """Generate embeddings for all completed meetings that lack one.

    Runs in a background thread so it doesn't block app startup.
    """
    def _run():
        conn = get_db()
        rows = conn.execute(
            "SELECT id, analysis FROM meetings "
            "WHERE status = 'completed' AND analysis IS NOT NULL AND embedding IS NULL"
        ).fetchall()
        conn.close()

        if not rows:
            logger.info("Embedding backfill: no meetings need backfilling")
            return

        logger.info("Embedding backfill: %d meetings to process", len(rows))
        done = 0
        for row in rows:
            store_embedding(row["id"], row["analysis"])
            done += 1
        logger.info("Embedding backfill complete: %d/%d succeeded", done, len(rows))

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
