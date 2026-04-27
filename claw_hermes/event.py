"""Unified Event type — produced and consumed by both Hermes and OpenClaw.

Wire format is NDJSON over WebSocket (one Event per text frame, no trailing newline).
event_id is a 26-char Crockford-base32 ULID — 48-bit ms timestamp + 80 bits of
randomness, monotonic within the same millisecond. ULID generation is in-process
stdlib only (`os.urandom` + `time.time_ns`).
"""
from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

KNOWN_KINDS: frozenset[str] = frozenset({
    "message.inbound",
    "message.outbound",
    "github.pr.opened",
    "github.pr.merged",
    "github.pr.closed",
    "github.ci.failed",
    "github.ci.passed",
    "github.issue.opened",
    "system.heartbeat",
})

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


@dataclass
class _UlidState:
    last_ms: int = -1
    last_rand: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)


_ULID_STATE = _UlidState()


def _encode_crockford(value: int, length: int) -> str:
    out = ["0"] * length
    for i in range(length - 1, -1, -1):
        out[i] = _CROCKFORD[value & 0x1F]
        value >>= 5
    return "".join(out)


def _new_ulid(now_ms: int | None = None) -> str:
    """Generate a 26-char Crockford-base32 ULID, monotonic within the same ms."""
    ms = int(time.time() * 1000) if now_ms is None else now_ms
    with _ULID_STATE.lock:
        if ms == _ULID_STATE.last_ms:
            rand = (_ULID_STATE.last_rand + 1) & ((1 << 80) - 1)
        else:
            rand = int.from_bytes(os.urandom(10), "big")
        _ULID_STATE.last_ms = ms
        _ULID_STATE.last_rand = rand
    ts_part = _encode_crockford(ms & ((1 << 48) - 1), 10)
    rand_part = _encode_crockford(rand, 16)
    return ts_part + rand_part


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class Event:
    event_id: str
    ts: str
    kind: str
    actor: dict[str, Any]
    session_id: str
    payload: dict[str, Any]
    context: dict[str, Any]
    trace: dict[str, Any]

    @classmethod
    def new(
        cls,
        kind: str,
        *,
        actor: dict[str, Any] | None = None,
        session_id: str = "",
        payload: dict[str, Any] | None = None,
        context: dict[str, Any] | None = None,
        trace: dict[str, Any] | None = None,
        event_id: str | None = None,
        ts: str | None = None,
        now_ms: int | None = None,
    ) -> Event:
        return cls(
            event_id=event_id or _new_ulid(now_ms=now_ms),
            ts=ts or _utc_now_iso(),
            kind=kind,
            actor=dict(actor or {}),
            session_id=session_id,
            payload=dict(payload or {}),
            context=dict(context or {}),
            trace=dict(trace or {}),
        )

    def to_json(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"), sort_keys=False)

    @classmethod
    def from_json(cls, s: str) -> Event:
        raw = json.loads(s)
        if not isinstance(raw, dict):
            raise ValueError("Event payload must be a JSON object")
        try:
            return cls(
                event_id=str(raw["event_id"]),
                ts=str(raw["ts"]),
                kind=str(raw["kind"]),
                actor=dict(raw.get("actor") or {}),
                session_id=str(raw.get("session_id", "")),
                payload=dict(raw.get("payload") or {}),
                context=dict(raw.get("context") or {}),
                trace=dict(raw.get("trace") or {}),
            )
        except KeyError as e:
            raise ValueError(f"Event missing required field: {e.args[0]}") from e

    def is_known(self) -> bool:
        return self.kind in KNOWN_KINDS


def is_known_kind(kind: str) -> bool:
    return kind in KNOWN_KINDS


__all__ = ["Event", "KNOWN_KINDS", "is_known_kind"]
