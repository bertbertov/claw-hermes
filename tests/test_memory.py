"""SqliteMemoryBroker tests — round-trip, idempotency, FTS recall, lifecycle."""
from __future__ import annotations

from pathlib import Path

import pytest

from claw_hermes.event import Event
from claw_hermes.memory import SqliteMemoryBroker


def _broker(tmp_path: Path) -> SqliteMemoryBroker:
    return SqliteMemoryBroker(tmp_path / "memory.db")


def test_record_and_recall_round_trip(tmp_path: Path):
    broker = _broker(tmp_path)
    ev = Event.new(
        kind="message.inbound",
        actor={"id": "user:albert", "channel": "imessage", "handle": "+971..."},
        session_id="sess_albert_main",
        payload={"text": "did the GLD bot fire?"},
        context={"thread_id": "t-7"},
        trace={"origin": "openclaw.gateway"},
    )
    broker.record_event(ev)
    rows = broker.recent(limit=10)
    assert len(rows) == 1
    assert rows[0] == ev
    broker.close()


def test_idempotent_insert_same_event_id(tmp_path: Path):
    broker = _broker(tmp_path)
    ev = Event.new(kind="message.inbound", payload={"text": "hi"})
    broker.record_event(ev)
    broker.record_event(ev)
    broker.record_event(ev)
    assert broker.count() == 1
    broker.close()


def test_recall_filters_by_kind(tmp_path: Path):
    broker = _broker(tmp_path)
    broker.record_event(Event.new(kind="message.inbound", payload={"text": "a"}))
    broker.record_event(Event.new(kind="github.pr.opened", payload={"text": "b"}))
    broker.record_event(Event.new(kind="message.inbound", payload={"text": "c"}))
    inbound = broker.recall(kind="message.inbound")
    assert len(inbound) == 2
    assert all(e.kind == "message.inbound" for e in inbound)
    broker.close()


def test_recall_filters_by_session_id(tmp_path: Path):
    broker = _broker(tmp_path)
    broker.record_event(Event.new(kind="message.inbound", session_id="A", payload={"text": "1"}))
    broker.record_event(Event.new(kind="message.inbound", session_id="B", payload={"text": "2"}))
    broker.record_event(Event.new(kind="message.inbound", session_id="A", payload={"text": "3"}))
    only_a = broker.recall(session_id="A")
    assert len(only_a) == 2
    assert all(e.session_id == "A" for e in only_a)
    broker.close()


def test_recall_with_fts_query_finds_payload_text(tmp_path: Path):
    broker = _broker(tmp_path)
    broker.record_event(Event.new(kind="message.inbound", payload={"text": "did the GLD bot fire today"}))
    broker.record_event(Event.new(kind="message.inbound", payload={"text": "deploy the trading bot"}))
    broker.record_event(Event.new(kind="message.inbound", payload={"text": "pravilo session at 7am"}))
    hits = broker.recall(query="bot")
    assert len(hits) == 2
    assert all("bot" in e.payload.get("text", "").lower() for e in hits)
    pravilo = broker.recall(query="pravilo")
    assert len(pravilo) == 1
    broker.close()


def test_recall_query_combined_with_kind_filter(tmp_path: Path):
    broker = _broker(tmp_path)
    broker.record_event(Event.new(kind="message.inbound", payload={"text": "ship the bot"}))
    broker.record_event(Event.new(kind="github.pr.opened", payload={"text": "ship the bot"}))
    hits = broker.recall(query="bot", kind="github.pr.opened")
    assert len(hits) == 1
    assert hits[0].kind == "github.pr.opened"
    broker.close()


def test_count_reflects_recorded_events(tmp_path: Path):
    broker = _broker(tmp_path)
    assert broker.count() == 0
    for i in range(5):
        broker.record_event(Event.new(kind="message.inbound", payload={"text": f"msg{i}"}))
    assert broker.count() == 5
    broker.close()


def test_close_is_idempotent(tmp_path: Path):
    broker = _broker(tmp_path)
    broker.record_event(Event.new(kind="message.inbound", payload={"text": "x"}))
    broker.close()
    broker.close()
    broker.close()


def test_using_after_close_raises(tmp_path: Path):
    broker = _broker(tmp_path)
    broker.close()
    with pytest.raises(RuntimeError):
        broker.record_event(Event.new(kind="message.inbound"))


def test_context_manager_closes_broker(tmp_path: Path):
    path = tmp_path / "memory.db"
    with SqliteMemoryBroker(path) as broker:
        broker.record_event(Event.new(kind="message.inbound", payload={"text": "x"}))
        assert broker.count() == 1
    reopened = SqliteMemoryBroker(path)
    assert reopened.count() == 1
    reopened.close()


def test_recent_orders_newest_first(tmp_path: Path):
    broker = _broker(tmp_path)
    a = Event.new(kind="message.inbound", payload={"text": "a"}, ts="2026-01-01T00:00:00Z")
    b = Event.new(kind="message.inbound", payload={"text": "b"}, ts="2026-02-01T00:00:00Z")
    c = Event.new(kind="message.inbound", payload={"text": "c"}, ts="2026-03-01T00:00:00Z")
    broker.record_event(a)
    broker.record_event(b)
    broker.record_event(c)
    rows = broker.recent(limit=10)
    assert [e.ts for e in rows] == [c.ts, b.ts, a.ts]
    broker.close()
