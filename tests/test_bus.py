"""Bus tests — start the server, send Events from a client, assert intact + ordered.

All tests use ephemeral ports on 127.0.0.1. No real network beyond loopback.
"""
from __future__ import annotations

import asyncio
import socket

from websockets.asyncio.client import connect as ws_connect

from claw_hermes.bus import EventBus
from claw_hermes.event import Event


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def _start_server(received: list[Event], port: int):
    eb = EventBus(heartbeat_interval_s=3600.0)
    server = await eb.serve(
        host="127.0.0.1",
        port=port,
        on_event=lambda ev: _append(received, ev),
    )
    return server


async def _append(bucket: list[Event], ev: Event) -> None:
    bucket.append(ev)


async def test_bus_round_trip_three_events_arrive_in_order():
    received: list[Event] = []
    port = _free_port()
    server = await _start_server(received, port)
    try:
        eb = EventBus()
        conn = await eb.connect(f"ws://127.0.0.1:{port}")
        sent = [
            Event.new(kind="message.inbound", session_id="s1", payload={"text": "first"}),
            Event.new(kind="message.inbound", session_id="s1", payload={"text": "second"}),
            Event.new(kind="github.pr.opened", session_id="s1", payload={"text": "third"}),
        ]
        for ev in sent:
            await conn.send(ev)
        await conn.close()
        for _ in range(50):
            if len(received) >= 3:
                break
            await asyncio.sleep(0.02)
        assert len(received) == 3
        assert [e.event_id for e in received] == [e.event_id for e in sent]
        assert [e.payload["text"] for e in received] == ["first", "second", "third"]
    finally:
        server.close()
        await server.wait_closed()


async def test_bus_drops_malformed_frame_without_crashing():
    received: list[Event] = []
    port = _free_port()
    server = await _start_server(received, port)
    try:
        async with ws_connect(f"ws://127.0.0.1:{port}") as ws:
            await ws.send("this is not json")
            await ws.send("{}")
            good = Event.new(kind="message.inbound", payload={"text": "good"})
            await ws.send(good.to_json())
            for _ in range(50):
                if received:
                    break
                await asyncio.sleep(0.02)
        assert len(received) == 1
        assert received[0].event_id == good.event_id
        assert received[0].payload["text"] == "good"
    finally:
        server.close()
        await server.wait_closed()


async def test_bus_heartbeat_event_emitted_to_client():
    port = _free_port()
    eb = EventBus(heartbeat_interval_s=0.05)
    server = await eb.serve(host="127.0.0.1", port=port, on_event=None)
    try:
        async with ws_connect(f"ws://127.0.0.1:{port}") as ws:
            frame = await asyncio.wait_for(ws.recv(), timeout=2.0)
            ev = Event.from_json(frame if isinstance(frame, str) else frame.decode("utf-8"))
            assert ev.kind == "system.heartbeat"
            assert ev.is_known()
    finally:
        server.close()
        await server.wait_closed()


async def test_bus_connection_recv_returns_event():
    port = _free_port()
    eb = EventBus(heartbeat_interval_s=0.05)
    server = await eb.serve(host="127.0.0.1", port=port, on_event=None)
    try:
        client = EventBus()
        conn = await client.connect(f"ws://127.0.0.1:{port}")
        try:
            ev = await asyncio.wait_for(conn.recv(), timeout=2.0)
            assert ev.kind == "system.heartbeat"
        finally:
            await conn.close()
    finally:
        server.close()
        await server.wait_closed()


async def test_bus_multiple_independent_connections():
    received: list[Event] = []
    port = _free_port()
    server = await _start_server(received, port)
    try:
        eb = EventBus()
        c1 = await eb.connect(f"ws://127.0.0.1:{port}")
        c2 = await eb.connect(f"ws://127.0.0.1:{port}")
        e1 = Event.new(kind="message.inbound", payload={"text": "from c1"})
        e2 = Event.new(kind="message.inbound", payload={"text": "from c2"})
        await c1.send(e1)
        await c2.send(e2)
        await c1.close()
        await c2.close()
        for _ in range(50):
            if len(received) >= 2:
                break
            await asyncio.sleep(0.02)
        assert len(received) == 2
        ids = {e.event_id for e in received}
        assert e1.event_id in ids
        assert e2.event_id in ids
    finally:
        server.close()
        await server.wait_closed()
