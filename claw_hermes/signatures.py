"""Cross-repo signature store for slop classifications.

Persists every recorded verdict in a small SQLite DB at ~/.claw-hermes/signatures.db.
The point isn't analytics — it's the feedback substrate for v0.3 federated learning:
once we have N labeled rows across repos, we can rank which signals correlate with
merged-vs-rejected outcomes and start tuning the heuristic weights per-author.
"""
from __future__ import annotations

import json
import os
import sqlite3
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from claw_hermes.slop import SlopVerdict

DEFAULT_DB_PATH = Path(os.path.expanduser("~/.claw-hermes/signatures.db"))

Source = Literal["manual", "auto"]


@dataclass(frozen=True)
class SignatureRecord:
    id: int
    repo: str
    pr_number: int
    author: str
    label: str
    signals: tuple[str, ...]
    recorded_at: str
    source: str


@dataclass
class SignatureStore:
    db_path: Path = field(default_factory=lambda: DEFAULT_DB_PATH)

    def __post_init__(self) -> None:
        self.db_path = Path(self.db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS signatures ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "repo TEXT NOT NULL, "
                "pr_number INTEGER NOT NULL, "
                "author TEXT NOT NULL, "
                "label TEXT NOT NULL, "
                "signals TEXT NOT NULL, "
                "recorded_at TEXT NOT NULL, "
                "source TEXT NOT NULL"
                ")"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sig_repo ON signatures(repo)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sig_author ON signatures(author)")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def record(
        self,
        verdict: SlopVerdict,
        repo: str,
        pr_number: int,
        author: str,
        source: Source = "manual",
    ) -> int:
        recorded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO signatures "
                "(repo, pr_number, author, label, signals, recorded_at, source) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    repo,
                    int(pr_number),
                    author,
                    verdict.label,
                    json.dumps(list(verdict.signals)),
                    recorded_at,
                    source,
                ),
            )
            return int(cur.lastrowid or 0)

    def recall(
        self,
        repo: str | None = None,
        author: str | None = None,
        limit: int = 50,
    ) -> list[SignatureRecord]:
        clauses: list[str] = []
        params: list[object] = []
        if repo is not None:
            clauses.append("repo = ?")
            params.append(repo)
        if author is not None:
            clauses.append("author = ?")
            params.append(author)
        where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        sql = (
            "SELECT id, repo, pr_number, author, label, signals, recorded_at, source "
            f"FROM signatures{where} ORDER BY id DESC LIMIT ?"
        )
        params.append(int(limit))
        with self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [_row_to_record(r) for r in rows]

    def stats(self) -> dict[str, int]:
        with self._connect() as conn:
            total = conn.execute("SELECT COUNT(*) FROM signatures").fetchone()[0]
            label_rows = conn.execute(
                "SELECT label, COUNT(*) FROM signatures GROUP BY label"
            ).fetchall()
            signal_rows = conn.execute("SELECT signals FROM signatures").fetchall()
        out: dict[str, int] = {"total": int(total)}
        for label, count in label_rows:
            out[f"label:{label}"] = int(count)
        signal_counter: Counter[str] = Counter()
        for (raw,) in signal_rows:
            try:
                for s in json.loads(raw):
                    signal_counter[s] += 1
            except (json.JSONDecodeError, TypeError):
                continue
        for sig, count in signal_counter.items():
            out[f"signal:{sig}"] = int(count)
        return out


def _row_to_record(row: tuple) -> SignatureRecord:
    rid, repo, pr_number, author, label, signals_json, recorded_at, source = row
    try:
        signals = tuple(json.loads(signals_json))
    except (json.JSONDecodeError, TypeError):
        signals = ()
    return SignatureRecord(
        id=int(rid),
        repo=repo,
        pr_number=int(pr_number),
        author=author,
        label=label,
        signals=signals,
        recorded_at=recorded_at,
        source=source,
    )
