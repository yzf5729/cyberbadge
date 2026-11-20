"""SQLite 存储：多会话、消息、技能开关。"""
from __future__ import annotations

import os
import pathlib
import sqlite3
import time
import uuid
from contextlib import contextmanager

DB_PATH = pathlib.Path(os.environ.get("AGENT_WORKDIR", "./work")).resolve() / "cyberbadge.db"


@contextmanager
def _db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init() -> None:
    with _db() as c:
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions(
              id TEXT PRIMARY KEY, title TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS messages(
              id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
              role TEXT NOT NULL, content TEXT NOT NULL, created REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS skills(name TEXT PRIMARY KEY, enabled INTEGER NOT NULL DEFAULT 1);
            """
        )
        row = c.execute("SELECT COUNT(*) AS n FROM sessions").fetchone()
        if row["n"] == 0:
            now = time.time()
            c.execute("INSERT INTO sessions(id,title,created,updated) VALUES(?,?,?,?)",
                      (uuid.uuid4().hex[:12], "默认对话", now, now))


def list_sessions() -> list[dict]:
    with _db() as c:
        rows = c.execute("SELECT * FROM sessions ORDER BY updated DESC").fetchall()
        return [dict(r) for r in rows]


def create_session(title: str = "新对话") -> dict:
    sid, now = uuid.uuid4().hex[:12], time.time()
    with _db() as c:
        c.execute("INSERT INTO sessions(id,title,created,updated) VALUES(?,?,?,?)", (sid, title, now, now))
    return {"id": sid, "title": title, "created": now, "updated": now}


def delete_session(sid: str) -> bool:
    with _db() as c:
        c.execute("DELETE FROM messages WHERE session_id=?", (sid,))
        cur = c.execute("DELETE FROM sessions WHERE id=?", (sid,))
        return cur.rowcount > 0


def rename_session(sid: str, title: str) -> bool:
    with _db() as c:
        cur = c.execute("UPDATE sessions SET title=? WHERE id=?", (title, sid))
        return cur.rowcount > 0


def get_messages(sid: str, limit: int = 200) -> list[dict]:
    with _db() as c:
        rows = c.execute(
            "SELECT role, content FROM messages WHERE session_id=? ORDER BY id DESC LIMIT ?", (sid, limit)
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


def add_message(sid: str, role: str, content: str) -> None:
    now = time.time()
    with _db() as c:
        c.execute("INSERT INTO messages(session_id,role,content,created) VALUES(?,?,?,?)", (sid, role, content, now))
        c.execute("UPDATE sessions SET updated=? WHERE id=?", (now, sid))
        if role == "user":
            row = c.execute("SELECT title FROM sessions WHERE id=?", (sid,)).fetchone()
            if row and row["title"] in ("默认对话", "新对话"):
                c.execute("UPDATE sessions SET title=? WHERE id=?", (content[:24] or "新对话", sid))


def list_skills() -> list[dict]:
    with _db() as c:
        rows = c.execute("SELECT * FROM skills ORDER BY name").fetchall()
        return [dict(r) for r in rows]


def set_skill(name: str, enabled: bool) -> None:
    with _db() as c:
        c.execute("INSERT INTO skills(name,enabled) VALUES(?,?) ON CONFLICT(name) DO UPDATE SET enabled=excluded.enabled",
                  (name, 1 if enabled else 0))
