"""MemoryBroker — the canonical event store.

v0.2 ships a SQLite-backed default. v0.3 will swap the implementation for a
direct wrapper over Hermes' FTS5 + Honcho store. The Protocol below is the
contract the federation layer commits to today.
"""
from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Iterable, Protocol

from claw_hermes.event import Event

DEFAULT_DB_PATH = Path(os.path.expanduser("~/.claw-hermes/memory.db"))


class MemoryBroker(Protocol):
    def record_event(self, event: Event) -> None: ...
    def recall(
        self,
        query: str | None = None,
        *,
        kind: str | None = None,
        session_id: str | None = None,
        limit: int = 50,
    ) -> list[Event]: ...
    def recent(self, limit: int = 50) -> list[Event]: ...
    def count(self) -> int: ...
    def close(self) -> None: ...


_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    event_id   TEXT PRIMARY KEY,
    ts         TEXT NOT NULL,
    kind       TEXT NOT NULL,
    session_id TEXT NOT NULL,
    actor      TEXT NOT NULL,
    payload    TEXT NOT NULL,
    context    TEXT NOT NULL,
    trace      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_kind       ON events(kind);
CREATE INDEX IF NOT EXISTS idx_events_session    ON events(session_id);
CREATE INDEX IF NOT EXISTS idx_events_ts         ON events(ts);
CREATE VIRTUAL TABLE IF NOT EXISTS events_fts USING fts5(
    event_id UNINDEXED,
    text,
    tokenize = 'unicode61'
);
"""


class SqliteMemoryBroker:
    def __init__(self, path: Path | str | None = None) -> None:
        self._path = Path(path) if path else DEFAULT_DB_PATH
        self._conn: sqlite3.Connection | None = None
        self._closed = False

    def _connect(self) -> sqlite3.Connection:
        if self._closed:
            raise RuntimeError("SqliteMemoryBroker is closed")
        if self._conn is not None:
            return self._conn
        self._path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._path), isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript(_SCHEMA)
        self._conn = conn
        return conn

    @property
    def path(self) -> Path:
        return self._path

    def record_event(self, event: Event) -> None:
        conn = self._connect()
        text = self._extract_text(event)
        with conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO events "
                "(event_id, ts, kind, session_id, actor, payload, context, trace) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event.event_id,
                    event.ts,
                    event.kind,
                    event.session_id,
                    json.dumps(event.actor, separators=(",", ":")),
                    json.dumps(event.payload, separators=(",", ":")),
                    json.dumps(event.context, separators=(",", ":")),
                    json.dumps(event.trace, separators=(",", ":")),
                ),
            )
            if cur.rowcount > 0 and text:
                conn.execute(
                    "INSERT INTO events_fts(event_id, text) VALUES (?, ?)",
                    (event.event_id, text),
                )

    def recall(
        self,
        query: str | None = None,
        *,
        kind: str | None = None,
        session_id: str | None = None,
        limit: int = 50,
    ) -> list[Event]:
        conn = self._connect()
        params: list[object] = []
        if query:
            sql = (
                "SELECT e.event_id, e.ts, e.kind, e.session_id, e.actor, "
                "       e.payload, e.context, e.trace "
                "FROM events_fts f JOIN events e ON e.event_id = f.event_id "
                "WHERE events_fts MATCH ?"
            )
            params.append(query)
            if kind:
                sql += " AND e.kind = ?"
                params.append(kind)
            if session_id:
                sql += " AND e.session_id = ?"
                params.append(session_id)
            sql += " ORDER BY e.ts DESC LIMIT ?"
            params.append(int(limit))
        else:
            sql = (
                "SELECT event_id, ts, kind, session_id, actor, payload, context, trace "
                "FROM events WHERE 1=1"
            )
            if kind:
                sql += " AND kind = ?"
                params.append(kind)
            if session_id:
                sql += " AND session_id = ?"
                params.append(session_id)
            sql += " ORDER BY ts DESC LIMIT ?"
            params.append(int(limit))
        rows = conn.execute(sql, params).fetchall()
        return [self._row_to_event(r) for r in rows]

    def recent(self, limit: int = 50) -> list[Event]:
        return self.recall(limit=limit)

    def count(self) -> int:
        conn = self._connect()
        row = conn.execute("SELECT COUNT(*) FROM events").fetchone()
        return int(row[0]) if row else 0

    def close(self) -> None:
        if self._closed:
            return
        if self._conn is not None:
            try:
                self._conn.close()
            finally:
                self._conn = None
        self._closed = True

    def __enter__(self) -> SqliteMemoryBroker:
        self._connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()

    @staticmethod
    def _extract_text(event: Event) -> str:
        parts: list[str] = []
        text = event.payload.get("text") if isinstance(event.payload, dict) else None
        if isinstance(text, str) and text:
            parts.append(text)
        title = event.payload.get("title") if isinstance(event.payload, dict) else None
        if isinstance(title, str) and title:
            parts.append(title)
        return "\n".join(parts)

    @staticmethod
    def _row_to_event(row: Iterable) -> Event:
        event_id, ts, kind, session_id, actor, payload, context, trace = tuple(row)
        return Event(
            event_id=event_id,
            ts=ts,
            kind=kind,
            actor=json.loads(actor) if actor else {},
            session_id=session_id,
            payload=json.loads(payload) if payload else {},
            context=json.loads(context) if context else {},
            trace=json.loads(trace) if trace else {},
        )


__all__ = ["MemoryBroker", "SqliteMemoryBroker", "DEFAULT_DB_PATH"]
