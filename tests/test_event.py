"""Event tests — ULID validity, JSON round-trip, KNOWN_KINDS, monotonic ULIDs."""
from __future__ import annotations

import json
import re

import pytest

from claw_hermes.event import KNOWN_KINDS, Event, _new_ulid, is_known_kind

ULID_RE = re.compile(r"^[0-9A-HJKMNP-TV-Z]{26}$")


def test_event_new_generates_valid_ulid_and_iso_timestamp():
    ev = Event.new(kind="message.inbound", payload={"text": "hi"})
    assert ULID_RE.match(ev.event_id), f"bad ULID: {ev.event_id}"
    assert ev.ts.endswith("Z")
    assert "T" in ev.ts
    assert ev.kind == "message.inbound"
    assert ev.payload == {"text": "hi"}


def test_event_new_defaults_empty_dicts_for_optional_fields():
    ev = Event.new(kind="system.heartbeat")
    assert ev.actor == {}
    assert ev.payload == {}
    assert ev.context == {}
    assert ev.trace == {}
    assert ev.session_id == ""


def test_event_to_json_round_trip_preserves_all_fields():
    original = Event.new(
        kind="github.pr.opened",
        actor={"id": "user:albert", "channel": "github", "handle": "bertbertov"},
        session_id="sess_main",
        payload={"text": "PR #42", "attachments": []},
        context={"thread_id": "t-1", "reply_to": None},
        trace={"origin": "openclaw.gateway", "span_id": "span-x"},
    )
    rebuilt = Event.from_json(original.to_json())
    assert rebuilt == original


def test_to_json_is_compact_no_whitespace_no_trailing_newline():
    ev = Event.new(kind="message.inbound", payload={"text": "hi"})
    s = ev.to_json()
    assert "\n" not in s
    assert ": " not in s
    assert ", " not in s


def test_from_json_rejects_non_object():
    with pytest.raises(ValueError):
        Event.from_json("[]")


def test_from_json_rejects_missing_required_field():
    blob = json.dumps({"event_id": "x", "ts": "t"})
    with pytest.raises(ValueError):
        Event.from_json(blob)


def test_is_known_detects_known_kinds():
    assert Event.new(kind="message.inbound").is_known()
    assert Event.new(kind="github.ci.failed").is_known()
    assert Event.new(kind="system.heartbeat").is_known()
    assert not Event.new(kind="totally.made.up").is_known()


def test_known_kinds_constant_includes_required_set():
    required = {
        "message.inbound", "message.outbound",
        "github.pr.opened", "github.pr.merged", "github.pr.closed",
        "github.ci.failed", "github.ci.passed",
        "github.issue.opened",
        "system.heartbeat",
    }
    assert required.issubset(KNOWN_KINDS)
    assert is_known_kind("message.inbound")


def test_ulids_are_monotonic_within_same_millisecond():
    fixed_ms = 1_700_000_000_123
    ulids = [_new_ulid(now_ms=fixed_ms) for _ in range(50)]
    assert len(set(ulids)) == 50
    for a, b in zip(ulids, ulids[1:]):
        assert b > a, f"ULID regressed: {a} -> {b}"


def test_ulids_are_unique_across_milliseconds():
    a = _new_ulid(now_ms=1_700_000_000_100)
    b = _new_ulid(now_ms=1_700_000_000_200)
    assert a != b
    assert ULID_RE.match(a) and ULID_RE.match(b)


def test_event_is_frozen_dataclass():
    ev = Event.new(kind="message.inbound")
    with pytest.raises(Exception):
        ev.kind = "other"  # type: ignore[misc]
