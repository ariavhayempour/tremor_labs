from fastapi import APIRouter, WebSocket

router = APIRouter()
WS_TRY_AGAIN_LATER = 1013


@router.websocket("/ws")
async def ws(websocket: WebSocket) -> None:
    await websocket.accept()
    await websocket.close(code=WS_TRY_AGAIN_LATER, reason="stream not implemented")
