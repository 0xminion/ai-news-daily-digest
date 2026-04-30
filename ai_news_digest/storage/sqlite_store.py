"""SQLite state backend replacing topic_memory.json and file-locking.

Schema:
- runs: pipeline execution tracking
- topic_memory: daily topic count snapshots
- entities: extracted named entities per run
- daily_reports: archived daily digests with FTS
- weekly_reports: archived weekly digests
"""
from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ai_news_digest.config.yaml_loader import get_data_dir

_DB_PATH: Path | None = None
_db_lock = threading.Lock()


def _db_path() -> Path:
    global _DB_PATH
    if _DB_PATH is None:
        _DB_PATH = get_data_dir() / "state" / "digest.db"
        _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return _DB_PATH


def _conn() -> sqlite3.Connection:
    db = _db_path()
    db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS runs (
            run_id TEXT PRIMARY KEY,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            status TEXT DEFAULT 'running'
        );
        CREATE TABLE IF NOT EXISTS topic_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT,
            saved_at TEXT NOT NULL,
            snapshot TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS entities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL,
            name TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_entities_run ON entities(run_id);
        CREATE INDEX IF NOT EXISTS idx_entities_name ON entities(name);
        CREATE TABLE IF NOT EXISTS daily_reports (
            run_id TEXT PRIMARY KEY,
            saved_at TEXT NOT NULL,
            digest_text TEXT NOT NULL,
            highlights_json TEXT,
            research_json TEXT,
            topics_json TEXT,
            article_count INTEGER,
            provider TEXT,
            model TEXT,
            filepath TEXT
        );
        CREATE TABLE IF NOT EXISTS weekly_reports (
            run_id TEXT PRIMARY KEY,
            saved_at TEXT NOT NULL,
            digest_text TEXT NOT NULL,
            highlights_json TEXT,
            topics_json TEXT,
            provider TEXT,
            model TEXT,
            filepath TEXT
        );
        CREATE VIRTUAL TABLE IF NOT EXISTS report_fts USING fts5(
            run_id UNINDEXED,
            digest_text,
            content='daily_reports',
            content_rowid='rowid'
        );
        CREATE TRIGGER IF NOT EXISTS daily_reports_ai AFTER INSERT ON daily_reports BEGIN
            INSERT INTO report_fts(rowid, digest_text)
            VALUES (new.rowid, new.digest_text);
        END;
        CREATE TRIGGER IF NOT EXISTS daily_reports_ad AFTER DELETE ON daily_reports BEGIN
            INSERT INTO report_fts(report_fts, rowid, digest_text)
            VALUES ('delete', old.rowid, old.digest_text);
        END;
        """
    )
    conn.commit()


def _ensure_schema() -> None:
    with _db_lock:
        with _conn() as conn:
            _init_schema(conn)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------


def start_run() -> str:
    _ensure_schema()
    run_id = uuid.uuid4().hex[:16]
    with _db_lock:
        with _conn() as conn:
            conn.execute(
                "INSERT INTO runs (run_id, started_at, status) VALUES (?, ?, ?)",
                (run_id, _now_iso(), "running"),
            )
            conn.commit()
    return run_id


def end_run(run_id: str, status: str = "success") -> None:
    with _db_lock:
        with _conn() as conn:
            conn.execute(
                "UPDATE runs SET ended_at = ?, status = ? WHERE run_id = ?",
                (_now_iso(), status, run_id),
            )
            conn.commit()


# ---------------------------------------------------------------------------
# Topic memory
# ---------------------------------------------------------------------------


def load_topic_memory() -> dict:
    _ensure_schema()
    with _db_lock:
        with _conn() as conn:
            rows = conn.execute(
                "SELECT snapshot FROM topic_memory ORDER BY saved_at DESC LIMIT 60"
            ).fetchall()
    history = []
    for row in rows:
        try:
            history.append(json.loads(row["snapshot"]))
        except Exception:
            pass
    return {"history": list(reversed(history))}


def save_topic_memory(run_id: str, snapshot: dict) -> None:
    _ensure_schema()
    with _db_lock:
        with _conn() as conn:
            conn.execute(
                "INSERT INTO topic_memory (run_id, saved_at, snapshot) VALUES (?, ?, ?)",
                (run_id, snapshot.get("saved_at", _now_iso()), json.dumps(snapshot, ensure_ascii=False)),
            )
            conn.commit()


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------


def migrate_from_json(state_dir: Path) -> None:
    _ensure_schema()
    topic_path = Path(state_dir) / "topic_memory.json"
    if topic_path.exists():
        try:
            data = json.loads(topic_path.read_text(encoding="utf-8"))
            history = data.get("history", [])
            if history:
                with _db_lock:
                    with _conn() as conn:
                        existing = conn.execute(
                            "SELECT COUNT(*) FROM topic_memory"
                        ).fetchone()[0]
                        if existing == 0:
                            for snap in history:
                                conn.execute(
                                    "INSERT INTO topic_memory (run_id, saved_at, snapshot) VALUES (?, ?, ?)",
                                    ("migrated", snap.get("saved_at", _now_iso()), json.dumps(snap, ensure_ascii=False)),
                                )
                            conn.commit()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------


def record_entities(run_id: str, entities: list[dict]) -> None:
    _ensure_schema()
    with _db_lock:
        with _conn() as conn:
            for e in entities:
                conn.execute(
                    "INSERT INTO entities (run_id, name, entity_type, created_at) VALUES (?, ?, ?, ?)",
                    (run_id, e.get("name", ""), e.get("type", ""), _now_iso()),
                )
            conn.commit()


def get_entity_trends(min_mention_count: int = 2, lookback_runs: int = 5) -> list[dict]:
    _ensure_schema()
    with _db_lock:
        with _conn() as conn:
            rows = conn.execute(
                """
                SELECT name, entity_type, COUNT(*) as cnt, MIN(run_id) as first_run
                FROM entities
                WHERE run_id IN (
                    SELECT run_id FROM runs ORDER BY started_at DESC LIMIT ?
                )
                GROUP BY name, entity_type
                HAVING cnt >= ?
                ORDER BY cnt DESC
                """,
                (lookback_runs, min_mention_count),
            ).fetchall()
    return [
        {
            "name": row["name"],
            "entity_type": row["entity_type"],
            "mention_count": row["cnt"],
            "first_seen_run_id": row["first_run"],
        }
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Archive
# ---------------------------------------------------------------------------


def save_daily_report(
    run_id: str,
    saved_at: str,
    digest_text: str,
    highlights_json: str = "",
    research_json: str = "",
    topics_json: str = "",
    article_count: int = 0,
    provider: str = "",
    model: str = "",
    filepath: str = "",
) -> None:
    _ensure_schema()
    with _db_lock:
        with _conn() as conn:
            conn.execute(
                """INSERT INTO daily_reports
                   (run_id, saved_at, digest_text, highlights_json, research_json, topics_json, article_count, provider, model, filepath)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(run_id) DO UPDATE SET
                   saved_at=excluded.saved_at, digest_text=excluded.digest_text,
                   highlights_json=excluded.highlights_json, research_json=excluded.research_json,
                   topics_json=excluded.topics_json, article_count=excluded.article_count,
                   provider=excluded.provider, model=excluded.model, filepath=excluded.filepath""",
                (run_id, saved_at, digest_text, highlights_json, research_json, topics_json, article_count, provider, model, filepath),
            )
            conn.commit()


def save_weekly_report(
    run_id: str,
    saved_at: str,
    digest_text: str,
    highlights_json: str = "",
    topics_json: str = "",
    provider: str = "",
    model: str = "",
    filepath: str = "",
) -> None:
    _ensure_schema()
    with _db_lock:
        with _conn() as conn:
            conn.execute(
                """INSERT INTO weekly_reports
                   (run_id, saved_at, digest_text, highlights_json, topics_json, provider, model, filepath)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(run_id) DO UPDATE SET
                   saved_at=excluded.saved_at, digest_text=excluded.digest_text,
                   highlights_json=excluded.highlights_json, topics_json=excluded.topics_json,
                   provider=excluded.provider, model=excluded.model, filepath=excluded.filepath""",
                (run_id, saved_at, digest_text, highlights_json, topics_json, provider, model, filepath),
            )
            conn.commit()


def list_recent_reports(limit: int = 30) -> list[dict]:
    _ensure_schema()
    with _db_lock:
        with _conn() as conn:
            rows = conn.execute(
                "SELECT * FROM daily_reports ORDER BY saved_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
    return [dict(row) for row in rows]


def search_archive(query: str, limit: int = 20) -> list[dict]:
    _ensure_schema()
    with _db_lock:
        with _conn() as conn:
            rows = conn.execute(
                """SELECT d.* FROM daily_reports d
                   JOIN report_fts f ON d.rowid = f.rowid
                   WHERE report_fts MATCH ?
                   ORDER BY rank
                   LIMIT ?""",
                (query, limit),
            ).fetchall()
    return [dict(row) for row in rows]
