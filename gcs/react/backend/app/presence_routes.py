"""Presence for the GCS frontend: who currently has the page open.

Every open tab holds a /ws/presence websocket for as long as it is open; the
set of open sockets *is* the viewer list, so there is no heartbeat or expiry
to tune. Each change (join or leave) pushes the full list to every viewer,
along with that viewer's own id so the frontend can mark "you".

Purely informational -- nothing here gates or locks vehicle control.

Viewers are identified by the socket's peer address, which is the real client
only while uvicorn serves the frontend directly. Behind a reverse proxy every
viewer would show up as the proxy until forwarded headers are honoured."""

import asyncio
import logging
import socket
import time
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger("rich")

router = APIRouter()

RESOLVE_TIMEOUT_SECONDS = 2.0


def resolve_host(ip: str) -> str:
    """Reverse-DNS name for ip, or ip itself when it has none."""
    try:
        return socket.gethostbyaddr(ip)[0]
    except OSError:
        return ip


async def lookup_host(ip: str) -> str:
    """resolve_host off the event loop, giving up (and returning the bare ip)
    after RESOLVE_TIMEOUT_SECONDS so a dead resolver can't stall a join."""
    try:
        return await asyncio.wait_for(
            asyncio.to_thread(resolve_host, ip), RESOLVE_TIMEOUT_SECONDS
        )
    except TimeoutError:
        return ip


class PresenceRegistry:
    def __init__(self):
        self._viewers: dict[WebSocket, dict] = {}
        self._hosts: dict[str, str] = {}
        # Held across each broadcast so viewers never see lists out of order.
        self._lock = asyncio.Lock()

    async def join(self, websocket: WebSocket):
        ip = websocket.client.host if websocket.client else "unknown"
        if ip not in self._hosts:
            host = await lookup_host(ip)
            if host != ip:
                self._hosts[ip] = host
        async with self._lock:
            self._viewers[websocket] = {
                "id": uuid.uuid4().hex,
                "host": self._hosts.get(ip, ip),
                "ip": ip,
                "connected_at": time.time(),
            }
            await self._broadcast()
        logger.info(f"{ip} is viewing the GCS ({len(self._viewers)} viewers)")

    async def leave(self, websocket: WebSocket):
        async with self._lock:
            viewer = self._viewers.pop(websocket, None)
            if viewer is None:
                return
            await self._broadcast()
        logger.info(f"{viewer['ip']} left the GCS ({len(self._viewers)} viewers)")

    async def _broadcast(self):
        viewers = list(self._viewers.values())
        for websocket, viewer in list(self._viewers.items()):
            try:
                await websocket.send_json({"viewers": viewers, "you": viewer["id"]})
            except (WebSocketDisconnect, RuntimeError) as e:
                # A socket that died mid-broadcast is removed by its own
                # endpoint's leave(); nothing to do for it here.
                logger.debug(f"presence send to {viewer['ip']} failed: {e}")


registry = PresenceRegistry()


@router.websocket("/ws/presence")
async def presence_websocket(websocket: WebSocket):
    await websocket.accept()
    await registry.join(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await registry.leave(websocket)
