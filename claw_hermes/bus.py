"""Event bus skeleton — NDJSON over WebSocket between Gateway and Core.

Server emits a `system.heartbeat` Event every 30s. Malformed frames are logged
and dropped (the bus must never crash on a single bad payload). Wire format is
one Event per WebSocket text frame, no trailing newline.
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Awaitable, Callable

import websockets
from websockets.asyncio.client import ClientConnection, connect as ws_connect
from websockets.asyncio.server import ServerConnection, serve as ws_serve

from claw_hermes.event import Event

log = logging.getLogger(__name__)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 18790
HEARTBEAT_INTERVAL_S = 30.0

EventHandler = Callable[[Event], Awaitable[None]]


@dataclass
class Connection:
    _ws: ClientConnection

    async def send(self, event: Event) -> None:
        await self._ws.send(event.to_json())

    async def recv(self) -> Event:
        frame = await self._ws.recv()
        if isinstance(frame, bytes):
            frame = frame.decode("utf-8")
        return Event.from_json(frame)

    async def close(self) -> None:
        await self._ws.close()


class EventBus:
    def __init__(self, *, heartbeat_interval_s: float = HEARTBEAT_INTERVAL_S) -> None:
        self._heartbeat_interval_s = heartbeat_interval_s

    async def serve(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        on_event: EventHandler | None = None,
    ) -> websockets.asyncio.server.Server:
        async def handler(ws: ServerConnection) -> None:
            heartbeat = asyncio.create_task(self._heartbeat_loop(ws))
            try:
                async for frame in ws:
                    if isinstance(frame, bytes):
                        try:
                            frame = frame.decode("utf-8")
                        except UnicodeDecodeError:
                            log.warning("bus: dropped non-utf8 binary frame")
                            continue
                    try:
                        event = Event.from_json(frame)
                    except (json.JSONDecodeError, ValueError) as e:
                        log.warning("bus: dropped malformed frame: %s", e)
                        continue
                    if on_event is not None:
                        try:
                            await on_event(event)
                        except Exception:  # noqa: BLE001
                            log.exception("bus: on_event handler raised")
            finally:
                heartbeat.cancel()
                try:
                    await heartbeat
                except (asyncio.CancelledError, Exception):  # noqa: BLE001
                    pass

        return await ws_serve(handler, host, port)

    async def _heartbeat_loop(self, ws: ServerConnection) -> None:
        try:
            while True:
                await asyncio.sleep(self._heartbeat_interval_s)
                hb = Event.new(kind="system.heartbeat", trace={"origin": "bus.server"})
                try:
                    await ws.send(hb.to_json())
                except Exception:  # noqa: BLE001
                    return
        except asyncio.CancelledError:
            return

    async def connect(self, url: str) -> Connection:
        ws = await ws_connect(url)
        return Connection(_ws=ws)


__all__ = ["EventBus", "Connection", "DEFAULT_HOST", "DEFAULT_PORT", "HEARTBEAT_INTERVAL_S"]
