import asyncio
import contextlib

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from tremorlab.stream.broadcaster import Broadcaster

router = APIRouter()


async def _send_loop(websocket: WebSocket, broadcaster: Broadcaster) -> None:
    q = broadcaster.subscribe()
    try:
        await websocket.send_json(broadcaster.source_message())
        while True:
            await websocket.send_json(await q.get())
    finally:
        broadcaster.unsubscribe(q)


async def _until_disconnect(websocket: WebSocket) -> None:
    while (await websocket.receive())["type"] != "websocket.disconnect":
        pass


@router.websocket("/ws")
async def ws(websocket: WebSocket) -> None:
    """Server → client stream of the broadcaster's messages (shapes in docs/contracts.md)."""
    broadcaster: Broadcaster = websocket.app.state.broadcaster
    await websocket.accept()
    tasks = [
        asyncio.create_task(_send_loop(websocket, broadcaster)),
        asyncio.create_task(_until_disconnect(websocket)),
    ]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for task in tasks:
            task.cancel()
        for task in tasks:
            with contextlib.suppress(asyncio.CancelledError, WebSocketDisconnect, RuntimeError):
                await task
