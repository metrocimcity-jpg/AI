"""WebSocket metadata stream. Token is a query param because browsers cannot set headers."""

from __future__ import annotations

import asyncio

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.security import decode_token
from app.db.models import User

router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    state = websocket.app.state.ctx
    await websocket.accept()
    if state.config.auth_required:
        token = websocket.query_params.get("token")
        if not token:
            await websocket.close(code=4401)
            return
        try:
            payload = decode_token(token, state.config.secret_key)
        except jwt.PyJWTError:
            await websocket.close(code=4401)
            return
        session = state.sessions()
        try:
            user = session.get(User, str(payload.get("sub")))
            if user is None:
                await websocket.close(code=4401)
                return
        finally:
            session.close()
    sub = state.broadcaster.subscribe()
    try:
        async def reader() -> None:
            while True:
                message = await websocket.receive_json()
                if message.get("type") == "subscribe":
                    ids = message.get("camera_ids")
                    sub.camera_ids = set(ids) if ids else None
                    sub.frames = bool(message.get("frames", True))

        async def writer() -> None:
            while True:
                message = await sub.queue.get()
                await websocket.send_json(message)

        await asyncio.gather(reader(), writer())
    except WebSocketDisconnect:
        return
    except Exception:
        return
    finally:
        state.broadcaster.unsubscribe(sub)
