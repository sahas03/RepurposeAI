"""
In-process WebSocket connection registry.

Connections are grouped by `channel` (e.g. "experiments:<id>", "jobs:<id>",
"notifications:<user_id>"). This class only knows about connections held by
*this* process - cross-process delivery (e.g. a Celery worker pushing a
progress event) is handled by the Redis pub/sub relay in handlers.py.
"""
import asyncio
import json
import logging
from collections import defaultdict

from fastapi import WebSocket

logger = logging.getLogger("app.websocket")


class ConnectionManager:
    def __init__(self):
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._lock = asyncio.Lock()

    async def connect(self, channel: str, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self._connections[channel].add(websocket)
        logger.info("WebSocket connected to channel=%s", channel)

    async def disconnect(self, channel: str, websocket: WebSocket) -> None:
        async with self._lock:
            self._connections[channel].discard(websocket)
            if not self._connections[channel]:
                self._connections.pop(channel, None)

    async def broadcast_local(self, channel: str, event: dict) -> None:
        connections = list(self._connections.get(channel, ()))
        if not connections:
            return
        payload = json.dumps(event, default=str)
        for ws in connections:
            try:
                await ws.send_text(payload)
            except Exception:
                await self.disconnect(channel, ws)

    def channel_connection_count(self, channel: str) -> int:
        return len(self._connections.get(channel, ()))


manager = ConnectionManager()
