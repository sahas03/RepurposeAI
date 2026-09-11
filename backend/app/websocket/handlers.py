"""
WebSocket routes + the Redis pub/sub relay that lets Celery workers (running in
a separate process) push live events to browser clients connected to the API
process.

Event shape (sent for every job/experiment/analysis update):
{
    "event": "started" | "progress" | "completed" | "failed" | "notification",
    "job_id": "...",
    "status": "RUNNING",
    "progress": 65,
    "message": "Analyzing drug-target relationships"
}
"""
import asyncio
import json
import logging
from datetime import datetime, timezone

import redis
import redis.asyncio as aioredis
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.core.config import settings
from app.core.security import decode_token
from app.websocket.manager import manager

logger = logging.getLogger("app.websocket")

ws_router = APIRouter(tags=["WebSockets"])

_sync_redis_client: redis.Redis | None = None


def _get_sync_redis() -> redis.Redis:
    global _sync_redis_client
    if _sync_redis_client is None:
        _sync_redis_client = redis.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
    return _sync_redis_client


def publish_ws_event(channel: str, event: dict) -> None:
    """
    Best-effort publish, callable from sync request handlers *and* Celery
    tasks. Never raises - a missing/unreachable Redis must not break the
    underlying analysis or API request.
    """
    event = {"timestamp": datetime.now(timezone.utc).isoformat(), **event}
    try:
        _get_sync_redis().publish(f"ws:{channel}", json.dumps(event, default=str))
    except Exception as exc:
        logger.warning("Could not publish WebSocket event on channel=%s: %s", channel, exc)


class RedisRelay:
    """Subscribes to ws:* on Redis and re-broadcasts to local WebSocket connections."""

    def __init__(self):
        self._task: asyncio.Task | None = None
        self._client: aioredis.Redis | None = None

    async def start(self) -> None:
        self._task = asyncio.create_task(self._run())

    async def _run(self) -> None:
        while True:
            try:
                self._client = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
                pubsub = self._client.pubsub()
                await pubsub.psubscribe("ws:*")
                logger.info("WebSocket Redis relay subscribed to ws:*")
                async for message in pubsub.listen():
                    if message["type"] != "pmessage":
                        continue
                    raw_channel: str = message["channel"].decode() if isinstance(message["channel"], bytes) else message["channel"]
                    channel = raw_channel.removeprefix("ws:")
                    try:
                        event = json.loads(message["data"])
                    except (TypeError, ValueError):
                        continue
                    await manager.broadcast_local(channel, event)
            except asyncio.CancelledError:
                return
            except Exception as exc:
                logger.warning("WebSocket Redis relay disconnected (%s); retrying in 5s", exc)
                await asyncio.sleep(5)

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
        if self._client:
            await self._client.aclose()


redis_relay = RedisRelay()


async def _authenticate_ws(websocket: WebSocket, token: str | None) -> str | None:
    """Returns the authenticated user id, or None (and closes the socket) if invalid."""
    if not token:
        await websocket.close(code=4401, reason="Missing token")
        return None
    try:
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise ValueError("wrong token type")
        return payload["sub"]
    except Exception:
        await websocket.close(code=4401, reason="Invalid token")
        return None


@ws_router.websocket("/ws/experiments/{experiment_id}")
async def ws_experiment(websocket: WebSocket, experiment_id: str, token: str | None = Query(default=None)):
    if await _authenticate_ws(websocket, token) is None:
        return
    channel = f"experiments:{experiment_id}"
    await manager.connect(channel, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(channel, websocket)


@ws_router.websocket("/ws/analyses/{analysis_id}")
async def ws_analysis(websocket: WebSocket, analysis_id: str, token: str | None = Query(default=None)):
    if await _authenticate_ws(websocket, token) is None:
        return
    channel = f"analyses:{analysis_id}"
    await manager.connect(channel, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(channel, websocket)


@ws_router.websocket("/ws/jobs/{job_id}")
async def ws_job(websocket: WebSocket, job_id: str, token: str | None = Query(default=None)):
    if await _authenticate_ws(websocket, token) is None:
        return
    channel = f"jobs:{job_id}"
    await manager.connect(channel, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(channel, websocket)


@ws_router.websocket("/ws/notifications")
async def ws_notifications(websocket: WebSocket, token: str | None = Query(default=None)):
    user_id = await _authenticate_ws(websocket, token)
    if user_id is None:
        return
    channel = f"notifications:{user_id}"
    await manager.connect(channel, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await manager.disconnect(channel, websocket)
